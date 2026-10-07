from otree.api import Bot, SubmissionMustFail, expect
from . import *
import random


class PlayerBot(Bot):
    def play_round(self):
        # a description without choosing "Prefer to self-describe" is rejected
        yield SubmissionMustFail(Demographics, dict(gender='Man', gender_self='x', major='Economics'))
        gender = random.choice(C.GENDERS)
        major = random.choice(C.MAJORS)
        yield Demographics, dict(gender=gender, gender_self='', major=major)
        expect(self.player.major, major)
