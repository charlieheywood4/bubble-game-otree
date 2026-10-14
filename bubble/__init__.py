from otree.api import *
import random

doc = """
Bubble Game (Moinas and Pouget 2013), adapted from Huber (github.com/chr-huber/bg).
Groups of 5 in a random line. The first trader is offered the asset at $3. A purchase
doubles the price for the next trader; a refusal passes the asset on at the same price.
Not buying pays $5, reselling pays the next buyer's price minus yours, and being stuck pays $0.
Round 1 is an unpaid practice game; rounds 2-6 are part 1 and rounds 7-11 are part 2.
Each participant sees one interface per part (plain, hedonic, or directive), and every
participant switches interface between parts (six treatment groups).
"""


class C(BaseConstants):
    NAME_IN_URL = 'bubble'
    PLAYERS_PER_GROUP = 5
    PRACTICE_ROUNDS = 1
    GAMES_PER_PART = 5
    NUM_ROUNDS = PRACTICE_ROUNDS + 2 * GAMES_PER_PART

    START_PRICE = 3
    MULTIPLE = 2
    PRICES = [3, 6, 12, 24, 48]
    EARN_NOACTION = cu(5)
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

    # directive interface
    xp_gained = models.IntegerField(initial=0)
    new_badges = models.StringField(initial='')

    # comprehension check (round 1 only)
    cq1 = cq_field('If you are offered the asset at $3, what is your position in line?',
                   ['First', 'Second', 'Third', 'I cannot be sure'])
    cq2 = cq_field('The trader before you is offered the asset at $12 and does not buy. At what price is it offered to you?',
                   ['$6', '$12', '$24', 'It is not offered to you'])
    cq3 = cq_field('If you are offered the asset at $48, what is your position in line?',
                   ['First', 'Third', 'Fifth (last)', 'I cannot be sure'])
    cq4 = cq_field('You buy the asset at $6 and the next trader buys it from you at $12. What do you earn in that game?',
                   ['$0', '$5', '$6', '$12'])
    cq5 = cq_field('You decide not to buy the asset. What do you earn in that game?',
                   ['$0', '$3', '$5', 'It depends on the price'])
    cq6 = cq_field('When will you learn what happened in each game?',
                   ['Right after each game', 'At the end of the session'])
    cq_attempts = models.IntegerField(initial=0)
    # True if the experimenter skipped this participant past the check (Advance slowest participants)
    cq_skipped = models.BooleanField(initial=False)


CQ_ANSWERS = dict(cq1=3, cq2=1, cq3=2, cq4=2, cq5=2, cq6=0)


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
        if n % C.PLAYERS_PER_GROUP:
            raise ValueError(f'Number of participants must be a multiple of {C.PLAYERS_PER_GROUP}')
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

    # New random groups and a new random line every game
    subsession.group_randomly()
    part = part_of(subsession.round_number)
    for g in subsession.get_groups():
        positions = random.sample(range(1, C.PLAYERS_PER_GROUP + 1), C.PLAYERS_PER_GROUP)
        for p, pos in zip(g.get_players(), positions):
            p.position = pos
            p.part = part
            p.treatment = p.participant.treatment
            p.interface = interface_of(p.participant, part)
            p.prices_desc = prices_desc(p.participant, part)
            p.is_paid_round = subsession.round_number == session.paid_round


def set_outcomes(group: Group):
    line = sorted(group.get_players(), key=lambda p: p.position)
    price = C.START_PRICE
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
        elif p.position == C.PLAYERS_PER_GROUP:
            p.outcome, p.earn = 'Bought, last in line', C.EARN_STUCK
        else:
            p.outcome, p.earn = 'Bought, not resold', C.EARN_STUCK
        if p.is_paid_round:
            p.payoff = p.earn
        if p.part > 0:
            p.participant.games = p.participant.games + [dict(
                part=p.part, game=game_in_part(p.round_number), round=p.round_number,
                position=p.position, offered=p.offered_price, outcome=p.outcome,
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
        return dict(resale_rows=rows, last_price=C.PRICES[-1])


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
    form_fields = [f'buy_{i}' for i in range(len(C.PRICES))]

    @staticmethod
    def get_timeout_seconds(player: Player):
        if not player.session.config.get('timers', True):
            return None
        return C.PRACTICE_SECONDS if player.part == 0 else C.DECISION_SECONDS

    @staticmethod
    def vars_for_template(player: Player):
        order = list(range(len(C.PRICES)))
        if player.prices_desc:
            order.reverse()
        rows = [dict(field=f'buy_{i}', price=C.PRICES[i]) for i in order]
        return dict(rows=rows, game=game_in_part(player.round_number), xp=xp_info(player.participant))

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        player.timed_out = timeout_happened
        # unanswered prices count as "don't buy"
        for i in range(len(C.PRICES)):
            if player.field_maybe_none(f'buy_{i}') is None:
                setattr(player, f'buy_{i}', False)
        if player.interface == 'directive':
            pt = player.participant
            dec = [getattr(player, f'buy_{i}') for i in range(len(C.PRICES))]
            buys = sum(dec)
            player.xp_gained = buys * C.XP_PER_BUY
            pt.xp += player.xp_gained
            pt.streak = pt.streak + 1 if buys else 0
            have = pt.badges.split(',') if pt.badges else []
            earned = dict(bold=dec[3] or dec[4], roller=dec[4],
                          hot=pt.streak >= C.HOT_STREAK, allin=buys == len(C.PRICES))
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
        buys = sum(getattr(player, f'buy_{i}') for i in range(len(C.PRICES)))
        return dict(
            message=result_message(player), game=game_in_part(player.round_number),
            icon=icon, cheer=cheer, buys=buys, n_prices=len(C.PRICES),
            xp=xp_info(player.participant), shelf=badge_shelf(player.participant),
            new_badges=[b for b in C.BADGES if b['key'] in fresh],
            last_round=player.round_number == C.NUM_ROUNDS,
        )

    @staticmethod
    def js_vars(player: Player):
        return dict(confetti=player.interface == 'hedonic')


page_sequence = [Instructions, Comprehension, PartIntro, Decision, ResultsWaitPage, Result]
