from otree.api import *
import random

doc = """
Bubble Game (Moinas and Pouget 2013), adapted from Huber (github.com/chr-huber/bg).
At the start of the session, participants are split into groups of 3 to 5 that are as equal in
size as possible (6 -> 3+3, 7 -> 3+4, 9 -> 4+5, 10 -> 5+5, 13 -> 4+4+5), and they stay in the
same group for every game, with a new random place in line each game.
Prices shift with group size so the last trader can always be offered $36: a group of 5 starts
at $2.25, a group of 4 at $4.50, a group of 3 at $9. A purchase doubles the price for the next
trader; a refusal passes the asset on at the same price.
Not buying pays $2, reselling pays the next buyer's price minus yours, and being stuck pays $0.
Everyone also gets a $3 show-up fee (participation_fee in settings.py), paid on top of the paid game.
The smallest resale profit ($2.25) beats sitting out ($2), so a purchase that is resold always pays more.
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
    PRICES = [2.25, 4.5, 9, 18, 36]  # a group of n uses the top n prices
    EARN_NOACTION = cu(2)
    EARN_STUCK = cu(0)

    # Six treatment groups: every ordered pair of two different interfaces
    GROUP_KEYS = ['PH', 'PD', 'HP', 'HD', 'DP', 'DH']
    LETTER = dict(P='plain', H='hedonic', D='directive')
    LABELS = dict(plain='Plain', hedonic='Hedonic gamified', directive='Directive gamified')

    XP_PER_BUY = 10
    XP_PER_LEVEL = 100
    HOT_STREAK = 3
    # $18 and $36 are offered in every group size
    BADGES = [
        dict(key='bold', icon='💪', name='Bold Move', desc='Buy at $18 or more'),
        dict(key='roller', icon='💎', name='High Roller', desc='Buy at $36'),
        dict(key='hot', icon='🔥', name='Hot Hand', desc='Buy in 3 games in a row'),
        dict(key='allin', icon='🚀', name='All In', desc='Buy at every price in a game'),
    ]

    DECISION_SECONDS = 45
    PRACTICE_SECONDS = 90


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


def money(x):
    """$9, $18, but $2.25 and $4.50."""
    x = float(x)
    return f'${int(x)}' if x == int(x) else f'${x:,.2f}'


def buy_field(price):
    return models.BooleanField(
        label=money(price), choices=[[True, 'Buy'], [False, "Don't buy"]],
        widget=widgets.RadioSelectHorizontal,
    )


class Player(BasePlayer):
    # decisions: buy_k is the choice at PRICES[k]; prices the group can't reach stay blank
    buy_0 = buy_field(2.25)
    buy_1 = buy_field(4.5)
    buy_2 = buy_field(9)
    buy_3 = buy_field(18)
    buy_4 = buy_field(36)
    timed_out = models.BooleanField(initial=False)

    # treatment info, copied into every round for the data export
    part = models.IntegerField()
    interface = models.StringField()
    treatment = models.StringField()
    prices_desc = models.BooleanField()

    # outcome
    group_size = models.IntegerField()
    position = models.IntegerField()
    offered_price = models.CurrencyField()
    bought = models.BooleanField()
    resold_at = models.CurrencyField()
    outcome = models.StringField()
    earn = models.CurrencyField()
    is_paid_round = models.BooleanField(initial=False)

    # directive interface
    xp_gained = models.IntegerField(initial=0)
    new_badges = models.StringField(initial='')

    # comprehension check (round 1 only). Answers are option numbers on the participant's
    # screen; the questions depend on their group size, see comprehension_questions().
    cq1 = models.IntegerField(min=0, max=9)
    cq2 = models.IntegerField(min=0, max=9)
    cq3 = models.IntegerField(min=0, max=9)
    cq4 = models.IntegerField(min=0, max=9)
    cq5 = models.IntegerField(min=0, max=9)
    cq6 = models.IntegerField(min=0, max=9)
    cq_correct = models.IntegerField()
    # True if the experimenter skipped this participant past the check (Advance slowest participants)
    cq_skipped = models.BooleanField(initial=False)


CQ_FIELDS = ['cq1', 'cq2', 'cq3', 'cq4', 'cq5', 'cq6']
POSITIONS = ['First', 'Second', 'Third', 'Fourth', 'Fifth']


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


def comprehension_questions(size):
    """The six questions for a group of `size`, with answers and explanations."""
    lad = ladder(size)
    low, top = money(lad[0]), money(lad[-1])
    buy, sell = lad[1], lad[2]
    positions = POSITIONS[:size]
    last = POSITIONS[size - 1].lower()
    return [
        dict(name='cq1', text=f'If you are offered the asset at {low}, what is your position in line?',
             options=positions + ['I cannot be sure'], answer=size,
             explain=f'I cannot be sure. The price only doubles when someone buys, so if no one ahead of you has bought, '
                     f'the asset is still {low} and you could be anywhere from first to {last}.'),
        dict(name='cq2', text='The trader before you is offered the asset at $9 and does not buy. At what price is it offered to you?',
             options=['$4.50', '$9', '$18', 'It is not offered to you'], answer=1,
             explain='$9. The price only doubles when a trader buys, so if the trader before you does not buy, '
                     'you are offered the same price they were.'),
        dict(name='cq3', text=f'If you are offered the asset at {top}, what is your position in line?',
             options=positions + ['I cannot be sure'], answer=size - 1,
             explain=f'{POSITIONS[size - 1]}, last in line. The price reaches {top} only after {size - 1} traders have bought, '
                     f'so {size - 1} people are ahead of you and no one is left to buy from you.'),
        dict(name='cq4', text=f'You buy the asset at {money(buy)} and the next trader buys it from you at {money(sell)}. '
                              f'What do you earn in that game?',
             options=['$0', '$2', money(sell - buy), money(sell)], answer=2,
             explain=f'{money(sell - buy)}. You earn the later trader\'s price minus your price, '
                     f'and {money(sell)} minus {money(buy)} is {money(sell - buy)}.'),
        dict(name='cq5', text='You decide not to buy the asset. What do you earn in that game?',
             options=['$0', '$2', '$3', 'It depends on the price'], answer=1,
             explain='$2. Not buying always pays a sure $2, no matter what anyone else does.'),
        dict(name='cq6', text='When will you learn what happened in each game?',
             options=['Right after each game', 'At the end of the session'], answer=0,
             explain='Right after each game. Your screen shows the result of each game as soon as that game ends.'),
    ]


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
        # Random groups, as equal in size as possible, kept for the whole session
        players = subsession.get_players()
        random.shuffle(players)
        sizes = group_sizes(n)
        random.shuffle(sizes)
        matrix, start = [], 0
        for size in sizes:
            matrix.append(players[start:start + size])
            start += size
        subsession.set_group_matrix(matrix)
    else:
        subsession.group_like_round(1)

    # A new random place in line every game
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
            p.outcome, p.earn, p.resold_at = 'Bought and resold', nxt.offered_price - p.offered_price, nxt.offered_price
        elif p.position == p.group_size:
            p.outcome, p.earn = 'Bought, last in line', C.EARN_STUCK
        else:
            p.outcome, p.earn = 'Bought, not resold', C.EARN_STUCK
        if p.is_paid_round:
            p.payoff = p.earn
        if p.part > 0:
            p.participant.games = p.participant.games + [dict(
                part=p.part, game=game_in_part(p.round_number), round=p.round_number,
                position=p.position, size=p.group_size, offered=float(p.offered_price),
                outcome=p.outcome, earn=float(p.earn), interface=p.interface,
            )]


def result_message(p: Player):
    price = money(p.offered_price)
    if p.outcome == 'Did not buy':
        return f'You were offered the asset at {price} and did not buy.'
    if p.outcome == 'Bought and resold':
        return f'You bought the asset at {price} and a later trader bought it from you at {money(p.resold_at)}.'
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
        lad = ladder(player.group_size)
        fee = player.session.config['participation_fee']
        rows = [dict(buy=money(p), sell=money(p * C.MULTIPLE), earn=money(p * C.MULTIPLE - p)) for p in lad[:-1]]
        names = {3: 'three', 4: 'four', 5: 'five'}
        return dict(
            resale_rows=rows, last_price=money(lad[-1]), start=money(lad[0]),
            prices=', '.join(money(p) for p in lad[:-1]) + ', and ' + money(lad[-1]),
            size_word=names[player.group_size], last_word=POSITIONS[player.group_size - 1].lower(),
            fee=money(fee), sit_out=money(C.EARN_NOACTION),
            max_earn=money(lad[-2]), max_total=money(lad[-2] + fee), n_games=2 * C.GAMES_PER_PART,
        )


class Comprehension(Page):
    form_model = 'player'
    form_fields = CQ_FIELDS

    @staticmethod
    def is_displayed(player: Player):
        return player.round_number == 1

    @staticmethod
    def vars_for_template(player: Player):
        qs = comprehension_questions(player.group_size)
        return dict(questions=[dict(q, last=i == len(qs) - 1) for i, q in enumerate(qs)], n=len(qs))

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        if timeout_happened:
            # A forced advance fills unanswered fields with 0, which would look like real
            # answers. Record them as missing instead.
            for k in CQ_FIELDS:
                setattr(player, k, None)
            player.cq_skipped = True
            return
        qs = comprehension_questions(player.group_size)
        player.cq_correct = sum(getattr(player, q['name']) == q['answer'] for q in qs)


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
        # only the prices that can be offered in this group
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
        rows = [dict(field=f, price=money(C.PRICES[int(f[-1])])) for f in fields]
        return dict(rows=rows, game=game_in_part(player.round_number), xp=xp_info(player.participant),
                    sit_out=money(C.EARN_NOACTION))

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
            message=result_message(player), game=game_in_part(player.round_number), earned=money(player.earn),
            icon=icon, cheer=cheer, buys=buys, n_prices=player.group_size,
            xp=xp_info(player.participant), shelf=badge_shelf(player.participant),
            new_badges=[b for b in C.BADGES if b['key'] in fresh],
            last_round=player.round_number == C.NUM_ROUNDS,
        )

    @staticmethod
    def js_vars(player: Player):
        return dict(confetti=player.interface == 'hedonic')


page_sequence = [Instructions, Comprehension, PartIntro, Decision, ResultsWaitPage, Result]
