from otree.api import *

doc = """
End of session: the "Big Five" financial literacy questions (Lusardi and Mitchell),
then the reveal of the session's paid game. The survey comes before the reveal so
earnings cannot affect answers. Answers are unpaid; "Do not know" is scored as incorrect.
"""


class C(BaseConstants):
    NAME_IN_URL = 'survey'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1
    PRACTICE_ROUNDS = 1  # must match the bubble app


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


def fl_field(label, choices):
    return models.IntegerField(label=label, choices=list(enumerate(choices)), widget=widgets.RadioSelect)


class Player(BasePlayer):
    fl_interest = fl_field(
        'Suppose you had $100 in a savings account and the interest rate was 2% per year. After 5 years, how much do you think you would have in the account if you left the money to grow?',
        ['More than $102', 'Exactly $102', 'Less than $102', 'Do not know'])
    fl_inflation = fl_field(
        'Imagine that the interest rate on your savings account was 1% per year and inflation was 2% per year. After 1 year, how much would you be able to buy with the money in this account?',
        ['More than today', 'Exactly the same', 'Less than today', 'Do not know'])
    fl_risk = fl_field(
        'Is this statement true or false? "Buying a single company\'s stock usually provides a safer return than a stock mutual fund."',
        ['True', 'False', 'Do not know'])
    fl_mortgage = fl_field(
        'Is this statement true or false? "A 15-year mortgage typically requires higher monthly payments than a 30-year mortgage, but the total interest paid over the life of the loan will be less."',
        ['True', 'False', 'Do not know'])
    fl_bonds = fl_field(
        'If interest rates rise, what will typically happen to bond prices?',
        ['They will rise', 'They will fall', 'They will stay the same',
         'There is no relationship between bond prices and the interest rate', 'Do not know'])
    finlit_score = models.IntegerField()
    # True if the experimenter skipped this participant past the questions
    finlit_skipped = models.BooleanField(initial=False)


FL_ANSWERS = dict(fl_interest=0, fl_inflation=2, fl_risk=1, fl_mortgage=0, fl_bonds=1)


class FinLit(Page):
    form_model = 'player'
    form_fields = list(FL_ANSWERS)

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        if timeout_happened:
            # A forced advance fills unanswered questions with 0, which is the correct answer
            # to two of them. Record the answers and score as missing instead.
            for k in FL_ANSWERS:
                setattr(player, k, None)
            player.finlit_skipped = True
            player.finlit_score = None
        else:
            player.finlit_score = sum(getattr(player, k) == a for k, a in FL_ANSWERS.items())
        player.participant.finlit_score = player.field_maybe_none('finlit_score')


class PaymentReveal(Page):
    @staticmethod
    def vars_for_template(player: Player):
        games = player.participant.games
        paid_round = player.session.paid_round
        paid = next(g for g in games if g['round'] == paid_round)
        return dict(games=games, paid=paid, n=len(games), total=player.participant.payoff_plus_participation_fee())

    @staticmethod
    def js_vars(player: Player):
        games = player.participant.games
        return dict(pick=[g['round'] for g in games].index(player.session.paid_round))


page_sequence = [FinLit, PaymentReveal]
