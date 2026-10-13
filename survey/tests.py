from otree.api import Bot, Submission, expect
from . import *


class PlayerBot(Bot):
    def play_round(self):
        yield FinLit, FL_ANSWERS
        expect(self.player.finlit_score, 5)
        pt = self.participant
        expect(len(pt.games), 10)
        paid = [g for g in pt.games if g['round'] == self.session.paid_round]
        expect(len(paid), 1)
        expect(pt.payoff, paid[0]['earn'])
        # the show-up fee is added on top of the paid game
        expect(pt.payoff_plus_participation_fee(), paid[0]['earn'] + 3)
        yield Submission(PaymentReveal, check_html=False)
