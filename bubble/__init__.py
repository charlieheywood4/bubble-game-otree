from otree.api import *
import random

doc = """
Bubble Game (Moinas and Pouget 2013), adapted from Huber (github.com/chr-huber/bg).
Participants are split into groups of 3 to 5 that are as equal in size as possible
(6 -> 3+3, 7 -> 3+4, ... 10 -> 5+5, 13 -> 4+4+5), re-drawn every game, each in a random line.
Prices shift with group size so the last trader can always be offered $48: a group of 5
starts at $3, a group of 4 at $6, a group of 3 at $12. A purchase doubles the price for the
next trader; a refusal passes the asset on at the same price.
Not buying pays $2, reselling pays the next buyer's price minus yours, and being stuck pays $0.
Everyone also gets a $3 show-up fee (participation_fee in settings.py), paid on top of the paid game.
The smallest resale profit ($3) beats sitting out ($2), so a purchase that is resold always pays more.
Round 1 is an unpaid practice game; rounds 2-6 are part 1 and rounds 7-11 are part 2.
Each participant sees one interface per part (plain, hedonic, or directive), and every
participant switches interface between parts (six treatment groups).
"""


class C(BaseConstants):
    NAME_IN_URL = 'bubble'
    PLAYERS_PER_GROUP = None  # groups of 3-5, set in creating_session
    MIN_GROUP, MAX_GROUP = 3, 5
    PRACTICE_ROUNDS = 1
    GAMES_PER_PART = 5
    NUM_ROUNDS = PRACTICE_ROUNDS + 2 * GAMES_PER_PART

    MULTIPLE = 2
    PRICES = [3, 6, 12, 24, 48]  # a group of n uses the top n prices
    EARN_NOACTION = cu(2)
    EARN_STUCK = cu(0)

    # Six treatment groups: every ordered pair of two different interfaces
    GROUP_KEYS = ['PH', 'PD', 'HP', 'HD', 'DP', 'DH']
    LETTER = dict(P='plain', H='hedonic', D='directive')
    LABELS = dict(plain='Plain', hedonic='Hedonic gamified', directive='Directive gamified')

    XP_PER_BUY = 10
    XP_PER_LEVEL = 100
    HOT_STREAK = 3
    BADGES = [
        dict(key='bold', icon='💪', name='Bold Move', desc='Buy at $24 or more'),
        dict(key='roller', icon='💎', name='High Roller', desc='Buy at $48'),
        dict(key='hot', icon='🔥', name='Hot Hand', desc='Buy in 3 games in a row'),
        dict(key='allin', icon='🚀', name='All In', desc='Buy at every price in a game'),
    ]

    DECISION_SECONDS = 45
    PRACTICE_SECONDS = 90


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


def buy_field(price):
    return models.BooleanField(
        label=f'${price}', choices=[[True, 'Buy'], [False, "Don't buy"]],
        widget=widgets.RadioSelectHorizontal,
    )


def cq_field(label, choices):
    return models.IntegerField(
        label=label, choices=list(enumerate(choices)), widget=widgets.RadioSelect
    )


class Player(BasePlayer):
    # decisions: buy_k is the choice at PRICES[k]
    buy_0 = buy_field(3)
    buy_1 = buy_field(6)
    buy_2 = buy_field(12)
    buy_3 = buy_field(24)
    buy_4 = buy_field(48)
    timed_out = models.BooleanField(initial=False)

    # treatment info, copied into every round for the data export
    part = models.IntegerField()
    interface = models.StringField()
    treatment = models.StringField()
    prices_desc = models.BooleanField()

    # outcome
    position = models.IntegerField()
    offered_price = models.IntegerField()
    bought = models.BooleanField()
    resold_at = models.IntegerField()
    outcome = models.StringField()
    earn = models.CurrencyField()
    is_paid_round = models.BooleanField(initial=False)
    group_size = models.IntegerField()

    # directive interface
    xp_gained = models.IntegerField(initial=0)
    new_badges = models.StringField(initial='')

    # comprehension check (round 1 only)
    cq1 = cq_field('If you are offered the asset at the lowest price in your game, what is your position in line?',
                   ['First', 'Second', 'Third', 'I cannot be sure'])
    cq2 = cq_field('The trader before you is offered the asset at $12 and does not buy. At what price is it offered to you?',
                   ['$6', '$12', '$24', 'It is not offered to you'])
    cq3 = cq_field('If you are offered the asset at $48, what is your position in line?',
                   ['First', 'Second', 'Last in line', 'I cannot be sure'])
    cq4 = cq_field('You buy the asset at $12 and the next trader buys it from you at $24. What do you earn in that game?',
                   ['$0', '$2', '$12', '$24'])
    cq5 = cq_field('You decide not to buy the asset. What do you earn in that game?',
                   ['$0', '$2', '$3', 'It depends on the price'])
    cq6 = cq_field('When will you learn what happened in each game?',
                   ['Right after each game', 'At the end of the session'])
    cq_attempts = models.IntegerField(initial=0)
    # True if the experimenter skipped this participant past the check (Advance slowest participants)
    cq_skipped = models.BooleanField(initial=False)


CQ_ANSWERS = dict(cq1=3, cq2=1, cq3=2, cq4=2, cq5=1, cq6=0)


# ---------------- helpers ----------------
def part_of(round_number):
    if round_number <= C.PRACTICE_ROUNDS:
        return 0
    return 1 if round_number <= C.PRACTICE_ROUNDS + C.GAMES_PER_PART else 2


def game_in_part(round_number):
    if round_number <= C.PRACTICE_ROUNDS:
        return round_number
    return (round_number - C.PRACTICE_ROUNDS - 1) % C.GAMES_PER_PART + 1


def interface_of(participant, part):
    return 'plain' if part == 0 else C.LETTER[participant.treatment[part - 1]]


def prices_desc(participant, part):
    # Practice is lowest first; parts 1 and 2 alternate from the participant's starting direction
    return part > 0 and ((part == 1) == participant.desc_first)


def group_sizes(n):
    """Split n people into the fewest groups of 3-5 whose sizes differ by at most one."""
    k = -(-n // C.MAX_GROUP)  # ceiling
    base, extra = divmod(n, k)
    return [base + 1] * extra + [base] * (k - extra)


def ladder(size):
    # the top `size` prices, so the last trader can always be offered the highest price
    return C.PRICES[len(C.PRICES) - size:]


def shown_fields(player):
    return [f'buy_{i}' for i in range(len(C.PRICES) - player.group_size, len(C.PRICES))]


def xp_info(participant):
    xp = participant.xp
    return dict(level=xp // C.XP_PER_LEVEL + 1, into=xp % C.XP_PER_LEVEL, xp=xp)


def badge_shelf(participant):
    have = participant.badges.split(',') if participant.badges else []
    return [dict(b, on=b['key'] in have) for b in C.BADGES]


# ---------------- session setup ----------------
def creating_session(subsession: Subsession):
    session = subsession.session
    if subsession.round_number == 1:
        n = len(session.get_participants())
        if n < C.MIN_GROUP:
            raise ValueError(f'A session needs at least {C.MIN_GROUP} participants')
        session.group_sizes = sorted(set(group_sizes(n)))
        # One paid game for the whole session, drawn now and revealed at the end
        fixed = session.config.get('paid_game') or 0
        game = fixed if 1 <= fixed <= 2 * C.GAMES_PER_PART else random.randint(1, 2 * C.GAMES_PER_PART)
        session.paid_round = C.PRACTICE_ROUNDS + game
        # Rotate through the six groups; the starting price direction flips every six participants
        offset = session.config.get('rotation_offset') or 0
        for p in session.get_participants():
            i = p.id_in_session - 1 + offset
            p.treatment = C.GROUP_KEYS[i % len(C.GROUP_KEYS)]
            p.desc_first = (i // len(C.GROUP_KEYS)) % 2 == 0
            p.xp, p.badges, p.streak = 0, '', 0
            p.games = []
            p.finlit_score = None

    # New random groups (as equal in size as possible) and a new random line every game
    players = subsession.get_players()
    random.shuffle(players)
    sizes = group_sizes(len(players))
    random.shuffle(sizes)
    matrix, start = [], 0
    for size in sizes:
        matrix.append(players[start:start + size])
        start += size
    subsession.set_group_matrix(matrix)
    part = part_of(subsession.round_number)
    for g in subsession.get_groups():
        members = g.get_players()
        positions = random.sample(range(1, len(members) + 1), len(members))
        for p, pos in zip(members, positions):
            p.position = pos
            p.group_size = len(members)
            p.part = part
            p.treatment = p.participant.treatment
            p.interface = interface_of(p.participant, part)
            p.prices_desc = prices_desc(p.participant, part)
            p.is_paid_round = subsession.round_number == session.paid_round


def set_outcomes(group: Group):
    line = sorted(group.get_players(), key=lambda p: p.position)
    price = ladder(len(line))[0]
    for p in line:
        p.offered_price = price
        p.bought = bool(p.field_maybe_none(f'buy_{C.PRICES.index(price)}'))
        if p.bought:
            price *= C.MULTIPLE
    for k, p in enumerate(line):
        # the holder resells to the next trader in line who buys, whoever that is
        nxt = next((q for q in line[k + 1:] if q.bought), None)
        if not p.bought:
            p.outcome, p.earn = 'Did not buy', C.EARN_NOACTION
        elif nxt:
            p.outcome, p.earn, p.resold_at = 'Bought and resold', cu(nxt.offered_price - p.offered_price), nxt.offered_price
        elif p.position == p.group_size:
            p.outcome, p.earn = 'Bought, last in line', C.EARN_STUCK
        else:
            p.outcome, p.earn = 'Bought, not resold', C.EARN_STUCK
        if p.is_paid_round:
            p.payoff = p.earn
        if p.part > 0:
            p.participant.games = p.participant.games + [dict(
                part=p.part, game=game_in_part(p.round_number), round=p.round_number,
                position=p.position, size=p.group_size, offered=p.offered_price, outcome=p.outcome,
                earn=int(p.earn), interface=p.interface,
            )]


def result_message(p: Player):
    price = f'${p.offered_price}'
    if p.outcome == 'Did not buy':
        return f'You were offered the asset at {price} and did not buy.'
    if p.outcome == 'Bought and resold':
        return f'You bought the asset at {price} and a later trader bought it from you at ${p.resold_at}.'
    if p.outcome == 'Bought, last in line':
        return f'You bought the asset at {price}, but you were last in line, so no one could buy it from you.'
    return f'You bought the asset at {price}, but no one after you bought it.'


# ---------------- pages ----------------
class Instructions(Page):
    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player: Player):
        rows = [dict(buy=p, sell=p * C.MULTIPLE, earn=p * C.MULTIPLE - p) for p in C.PRICES[:-1]]
        sizes = player.session.group_sizes
        starts = [dict(size=s, start=ladder(s)[0]) for s in sorted(sizes, reverse=True)]
        names = {3: 'three', 4: 'four', 5: 'five'}
        size_text = ' or '.join(names[s] for s in sizes)
        return dict(resale_rows=rows, last_price=C.PRICES[-1], fee=player.session.participation_fee,
                    starts=starts, size_text=size_text, one_size=len(sizes) == 1)


class Comprehension(Page):
    form_model = 'player'
    form_fields = list(CQ_ANSWERS)

    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1

    @staticmethod
    def error_message(player: Player, values):
        player.cq_attempts += 1
        wrong = {k: 'Not quite. Please review the rules and try again.'
                 for k, a in CQ_ANSWERS.items() if values[k] != a}
        return wrong or None

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        # A forced advance fills unanswered fields with 0, which would look like real answers.
        # Record them as missing instead. oTree also runs error_message once on that empty
        # submission, so undo the attempt it counted.
        if timeout_happened:
            for k in CQ_ANSWERS:
                setattr(player, k, None)
            player.cq_skipped = True
            player.cq_attempts = max(0, player.cq_attempts - 1)


class PartIntro(Page):
    @staticmethod
    def is_displayed(player: Player):
        return game_in_part(player.round_number) == 1

    @staticmethod
    def vars_for_template(player: Player):
        return dict(label=C.LABELS[player.interface], shelf=badge_shelf(player.participant))

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        # points and badges start from zero in each part
        pt = player.participant
        pt.xp, pt.badges, pt.streak = 0, '', 0


class Decision(Page):
    form_model = 'player'

    @staticmethod
    def get_form_fields(player: Player):
        # only the prices that can be offered in this game's group
        return shown_fields(player)

    @staticmethod
    def get_timeout_seconds(player: Player):
        if not player.session.config.get('timers', True):
            return None
        return C.PRACTICE_SECONDS if player.part == 0 else C.DECISION_SECONDS

    @staticmethod
    def vars_for_template(player: Player):
        fields = shown_fields(player)
        if player.prices_desc:
            fields = fields[::-1]
        rows = [dict(field=f, price=C.PRICES[int(f[-1])]) for f in fields]
        return dict(rows=rows, game=game_in_part(player.round_number), xp=xp_info(player.participant),
                    start=ladder(player.group_size)[0])

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        player.timed_out = timeout_happened
        # unanswered prices count as "don't buy"; prices this group can't reach stay blank
        fields = shown_fields(player)
        for f in fields:
            if player.field_maybe_none(f) is None:
                setattr(player, f, False)
        if player.interface == 'directive':
            pt = player.participant
            dec = {f: getattr(player, f) for f in fields}
            buys = sum(dec.values())
            player.xp_gained = buys * C.XP_PER_BUY
            pt.xp += player.xp_gained
            pt.streak = pt.streak + 1 if buys else 0
            have = pt.badges.split(',') if pt.badges else []
            # $24 and $48 are offered in every group size
            earned = dict(bold=dec['buy_3'] or dec['buy_4'], roller=dec['buy_4'],
                          hot=pt.streak >= C.HOT_STREAK, allin=buys == len(fields))
            fresh = [b['key'] for b in C.BADGES if earned[b['key']] and b['key'] not in have]
            pt.badges = ','.join(have + fresh)
            player.new_badges = ','.join(fresh)


class ResultsWaitPage(WaitPage):
    after_all_players_arrive = set_outcomes
    title_text = 'Please wait'
    body_text = 'Waiting for the other traders in your group to make their choices.'


class Result(Page):
    @staticmethod
    def vars_for_template(player: Player):
        cheers = [('🎉', 'Locked in!'), ('✨', 'Nice, choices saved!'), ('🥳', "You're all set!"), ('🎈', 'Done and dusted!')]
        icon, cheer = random.choice(cheers)
        fresh = player.new_badges.split(',') if player.new_badges else []
        buys = sum(getattr(player, f) for f in shown_fields(player))
        return dict(
            message=result_message(player), game=game_in_part(player.round_number),
            icon=icon, cheer=cheer, buys=buys, n_prices=player.group_size,
            xp=xp_info(player.participant), shelf=badge_shelf(player.participant),
            new_badges=[b for b in C.BADGES if b['key'] in fresh],
            last_round=player.round_number == C.NUM_ROUNDS,
        )

    @staticmethod
    def js_vars(player: Player):
        return dict(confetti=player.interface == 'hedonic')


page_sequence = [Instructions, Comprehension, PartIntro, Decision, ResultsWaitPage, Result]
