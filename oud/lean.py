from common import FILLS_44, HIT, SUB

SONG = {
    "title": "Lean on Me", "artist": "Bill Withers", "subtitle": SUB,
    "bpm": 76, "meter": (4, 4), "feel": "Gospel-soul, recht en eenvoudig",
    "sections": [
        {"label": "Intro", "bars": 4, "groove": None, "text": "piano · tacet"},
        {"label": "Couplet 1", "bars": 8, "groove": "v", "crash": False, "fill": "pick8"},
        {"label": "Refrein", "bars": 8, "groove": "v", "crash": False, "fill": "bal4"},
        {"label": "Couplet 2", "bars": 8, "groove": "v", "crash": False, "fill": "pick8"},
        {"label": "Refrein", "bars": 8, "groove": "v", "crash": False, "fill": "sd34"},
        {"label": "Brug", "bars": 16, "groove": "br", "crash": True, "text": "handclaps · drijvend",
         "fill": "sd34"},
        {"label": "Couplet 3", "bars": 8, "groove": "v", "crash": True, "fill": "pick8"},
        {"label": "Refrein", "bars": 8, "groove": "v", "crash": False, "fill": "sd34"},
        {"label": "Brug", "bars": 8, "groove": "br", "crash": True, "fill": "sd34"},
        {"label": "Outro", "end": True, "seq": [
            {"groove": "v", "bars": 7, "crash": True, "text": "refrein-vamp"},
            {"groove": "hit", "bars": 1},
        ]},
    ],
}

GROOVES = {
    "v":  {"HH": "x-x-x-x-x-x-x-x-", "SD": "----x-------x---", "BD": "x-------x-------"},
    "br": {"HH": "xxxxxxxxxxxxxxxx", "SD": "----x-------x---", "BD": "x---x---x---x---"},
    "hit": HIT,
}
FILLS = FILLS_44
