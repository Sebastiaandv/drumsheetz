from common import FILLS_44, SUB

SONG = {
    "title": "50 Ways to Leave Your Lover", "artist": "Paul Simon", "subtitle": SUB,
    "bpm": 104, "meter": (4, 4), "feel": "Gadd-groove in de coupletten, backbeat in het refrein",
    "sections": [
        {"label": "Intro", "bars": 2, "groove": "gadd", "crash": False},
        {"label": "Couplet 1", "bars": 16, "groove": "gadd", "crash": False, "fill": "short"},
        {"label": "Refrein", "bars": 16, "groove": "chorus", "fill": "tom"},
        {"label": "Couplet 2", "bars": 16, "groove": "gadd", "crash": False, "fill": "short"},
        {"label": "Refrein", "bars": 16, "groove": "chorus", "fill": "tom"},
        {"label": "Couplet 3", "bars": 16, "groove": "gadd", "crash": False, "fill": "short"},
        {"label": "Outro", "bars": 16, "groove": "chorus", "text": "herhalen tot fade", "end": True},
    ],
}

GROOVES = {
    "gadd":   {"HH": "x-x-x-x-x-x---x-", "SD": "-g-g-g-g-g-gXg-g", "BD": "x-------x-------"},
    "chorus": {"HH": "x-x-x-x-x-x-x-x-", "SD": "----x-------x---", "BD": "x-------x-x-----"},
}

FILLS = dict(FILLS_44,
    short={"SD": "------------XgXX", "BD": "x-------x-------"},
    tom={"SD": "--------xx------", "T1": "----------xx----", "T2": "------------xx--", "FT": "--------------xx",
         "BD": "x-------x-------"},
)
