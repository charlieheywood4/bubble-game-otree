from otree.api import Bot, Submission, SubmissionMustFail, expect
from . import *
import random


class PlayerBot(Bot):
    def play_round(self):
        r = self.round_number
        if r == 1:
            yield Instructions
            # one wrong answer must be rejected before the correct set goes through
            yield SubmissionMustFail(Comprehension, dict(CQ_ANSWERS, cq1=0))
            yield Comprehension, CQ_ANSWERS
        if game_in_part(r) == 1:
            yield PartIntro

        # one player per group lets the timer run out in round 4
        if r == 4 and self.player.id_in_group == 1:
            yield Submission(Decision, {}, timeout_happened=True)
        else:
            yield Decision, {f'buy_{i}': random.random() < 0.6 for i in range(len(C.PRICES))}
        yield Result

        p = self.player
        if p.timed_out:
            expect([getattr(p, f'buy_{i}') for i in range(len(C.PRICES))], [False] * len(C.PRICES))
        # interface follows the treatment, and everyone switches between parts
        t = p.participant.treatment
        expect(t[0] != t[1], True)
        if p.part:
            expect(p.interface, C.LETTER[t[p.part - 1]])
        # payoffs follow the rules
        expect(p.offered_price, 'in', C.PRICES)
        if p.position == 1:
            expect(p.offered_price, C.START_PRICE)
        if p.outcome == 'Did not buy':
            expect(p.earn, C.EARN_NOACTION)
        elif p.outcome == 'Bought and resold':
            expect(p.earn, p.resold_at - p.offered_price)
        else:
            expect(p.earn, C.EARN_STUCK)
        # only the session's paid game counts
        expect(p.payoff, p.earn if p.round_number == p.session.paid_round else 0)
        # positions 1-5 are each used once per group
        expect(sorted(q.position for q in p.group.get_players()), [1, 2, 3, 4, 5])
