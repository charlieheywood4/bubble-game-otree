from os import environ

SESSION_CONFIGS = [
    dict(
        name='bubble_study',
        display_name='Bubble Game study (groups of 5)',
        app_sequence=['bubble', 'survey'],
        num_demo_participants=5,
        # 0 = draw the paid game at random when the session is created; 1-10 fixes it
        paid_game=0,
        # Number of participants already assigned in earlier sessions, so the six
        # treatment groups and price directions keep rotating across sessions.
        rotation_offset=0,
        timers=True,
        doc="""
        Participants must be a multiple of 5.
        paid_game: 0 draws the paid game at random (1-10 fixes it for testing).
        rotation_offset: how many participants earlier sessions have already assigned,
        so treatment groups keep rotating evenly across sessions.
        timers: 45 seconds per decision (90 for practice) when on.
        """,
    ),
]

SESSION_CONFIG_DEFAULTS = dict(
    real_world_currency_per_point=1.00, participation_fee=0.00, doc=""
)

PARTICIPANT_FIELDS = [
    'treatment',     # e.g. 'PD' = plain in part 1, directive in part 2
    'desc_first',    # True if part 1 lists prices highest first
    'xp', 'badges', 'streak',  # directive interface state, reset at the start of each part
    'games',         # list of per-game results, used for the end-of-session reveal
    'finlit_score',
]
SESSION_FIELDS = ['paid_round']

ROOMS = [
    # Participants type their computer number (1-40) when they open the room link,
    # so the Payments page lists cash owed by computer.
    dict(name='econ_lab', display_name='Economics lab', participant_label_file='_rooms/econ_lab.txt'),
]

LANGUAGE_CODE = 'en'
REAL_WORLD_CURRENCY_CODE = 'USD'
USE_POINTS = False
REAL_WORLD_CURRENCY_DECIMAL_PLACES = 0

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = environ.get('OTREE_ADMIN_PASSWORD')

DEMO_PAGE_INTRO_HTML = """
Bubble Game experiment with plain, hedonic, and directive interfaces.
"""

# Set OTREE_SECRET_KEY on the server (oTree Hub: site settings > config vars).
# The fallback is only for running on your own computer.
SECRET_KEY = environ.get('OTREE_SECRET_KEY', 'local-development-only')
