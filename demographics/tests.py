from otree.api import Bot, Submission, SubmissionMustFail, expect
from . import *
import random


def test_codes(n, case):
    """Room codes the bots pretend to have typed. 'codes': two valid groups, uneven where
    possible (8 -> 5+3); 'bad_codes': one oversized group, so the game must fall back to
    random groups; 'no_codes': no label at all, as in a demo session."""
    if case == 'bad_codes':
        return ['1' + chr(65 + i) for i in range(n)] if n > 5 else [None] * n
    if case == 'no_codes':
        return [None] * n
    g1 = n if n <= 5 else min(5, n - 3)
    return ['1' + chr(65 + i) for i in range(g1)] + ['2' + chr(65 + i) for i in range(n - g1)]


class PlayerBot(Bot):
    cases = ['codes', 'bad_codes', 'no_codes']

    def play_round(self):
        n = len(self.session.get_participants())
        code = test_codes(n, self.case)[self.participant.id_in_session - 1]
        # bots have no code when they arrive, so in a real (non-demo) session the game first
        # stops them on the CodeRequired page; the bot then continues as if advanced
        blocked = needs_code(self.player)
        expect(blocked, not self.session.is_demo)
        if code:
            self.participant.label = code
        if blocked:
            yield Submission(CodeRequired, check_html=False)
        # a description without choosing "Prefer to self-describe" is rejected
        yield SubmissionMustFail(Demographics, dict(gender='Man', gender_self='x', major='Economics'))
        gender = random.choice(C.GENDERS)
        major = random.choice(C.MAJORS)
        yield Demographics, dict(gender=gender, gender_self='', major=major)
        expect(self.player.major, major)
