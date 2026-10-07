from otree.api import *

doc = """
Start of session: confirms the participant's station number (the room label they typed)
and asks the two demographic questions in the IRB application, gender and major.
Answers are stored only with the station number. Major uses broad groups so that
small cells cannot identify anyone; the options match the paper backup form.
"""


class C(BaseConstants):
    NAME_IN_URL = 'demographics'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 1
    GENDERS = ['Woman', 'Man', 'Non-binary', 'Prefer to self-describe', 'Prefer not to say']
    MAJORS = [
        'Economics',
        'Other social sciences (for example, political science or psychology)',
        'Natural sciences and mathematics',
        'Humanities',
        'Fine arts',
        'Undeclared or undecided',
        'Prefer not to say',
    ]


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    pass


class Player(BasePlayer):
    gender = models.StringField(
        label='What is your gender?', choices=C.GENDERS, widget=widgets.RadioSelect
    )
    gender_self = models.StringField(
        label='If you chose "Prefer to self-describe," you may describe it here (optional):',
        blank=True,
    )
    major = models.StringField(
        label='Which group best describes your major? If you have more than one major, '
        'choose the one you consider your main field.',
        choices=C.MAJORS,
        widget=widgets.RadioSelect,
    )
    # True if the experimenter skipped this participant past the page
    skipped = models.BooleanField(initial=False)


class Demographics(Page):
    form_model = 'player'
    form_fields = ['gender', 'gender_self', 'major']

    @staticmethod
    def error_message(player: Player, values):
        if values['gender_self'] and values['gender'] != 'Prefer to self-describe':
            return 'Leave the description box empty unless you chose "Prefer to self-describe."'

    @staticmethod
    def before_next_page(player: Player, timeout_happened):
        # A forced advance fills unanswered fields with '', so record them as missing instead
        if timeout_happened:
            player.gender = player.major = None
            player.gender_self = ''
            player.skipped = True


page_sequence = [Demographics]
