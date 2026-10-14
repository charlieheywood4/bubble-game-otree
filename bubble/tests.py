from otree.api import Bot, Submission, expect
from . import *
import random


def p_group_ids(player):
    return sorted(q.participant.id_in_session for q in player.group.get_players())


class PlayerBot(Bot):
    def play_round(self):
        r = self.round_number
        if r == 1:
            yield Instructions
            # answers are recorded whether right or wrong; this bot gets the first one wrong
            qs = comprehension_questions(self.player.group_size)
            answers = {q['name']: q['answer'] for q in qs}
            answers['cq1'] = 0
            yield Comprehension, answers
            expect(self.player.cq_correct, len(qs) - 1)
        # groups are fixed for the session
        expect(p_group_ids(self.player), p_group_ids(self.player.in_round(1)))
        if game_in_part(r) == 1:
            yield PartIntro

        # one player per group lets the timer run out in round 4
        if r == 4 and self.player.id_in_group == 1:
            yield Submission(Decision, {}, timeout_happened=True)
        else:
            yield Decision, {f: random.random() < 0.6 for f in shown_fields(self.player)}
        yield Result

        p = self.player
        if p.timed_out:
            expect([getattr(p, f) for f in shown_fields(p)], [False] * p.group_size)
        # prices this group cannot reach are left blank
        hidden = [f'buy_{i}' for i in range(len(C.PRICES) - p.group_size)]
        expect([p.field_maybe_none(f) for f in hidden], [None] * len(hidden))
        # interface follows the treatment, and everyone switches between parts
        t = p.participant.treatment
        expect(t[0] != t[1], True)
        if p.part:
            expect(p.interface, C.LETTER[t[p.part - 1]])
        # payoffs follow the rules
        expect(p.offered_price, 'in', ladder(p.group_size))
        if p.position == 1:
            expect(p.offered_price, ladder(p.group_size)[0])
        if p.outcome == 'Did not buy':
            expect(p.earn, C.EARN_NOACTION)
        elif p.outcome == 'Bought and resold':
            expect(p.earn, p.resold_at - p.offered_price)
        else:
            expect(p.earn, C.EARN_STUCK)
        # only the session's paid game counts
        expect(p.payoff, p.earn if p.round_number == p.session.paid_round else 0)
        # groups are 3-5 people, as equal as possible, and positions 1..n are each used once
        members = p.group.get_players()
        expect(sorted(q.position for q in members), list(range(1, len(members) + 1)))
        sizes = [len(g.get_players()) for g in p.subsession.get_groups()]
        expect(min(sizes) >= C.MIN_GROUP and max(sizes) <= C.MAX_GROUP and max(sizes) - min(sizes) <= 1, True)
        expect(sorted(sizes), sorted(group_sizes(len(p.subsession.get_players()))))
