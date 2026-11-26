from common import FILLS_44, SUB

SONG = {
    "title": "One Love", "artist": "Bob Marley & The Wailers", "subtitle": SUB,
    "bpm": 76, "meter": (4, 4), "feel": "Reggae one drop · 8sten licht geswingd",
    "sections": [
        {"label": "Intro", "bars": 4, "groove": "od", "crash": False, "fill": "drag"},
        {"label": "Refrein", "bars": 8, "groove": "od", "crash": False, "fill": "drag"},
        {"label": "Couplet 1", "bars": 8, "groove": "od", "crash": False, "fill": "drag"},
        {"label": "Refrein", "bars": 8, "groove": "od", "crash": False, "fill": "drag"},
        {"label": "Couplet 2", "bars": 8, "groove": "od", "crash": False, "fill": "drag"},
        {"label": "Refrein", "bars": 8, "groove": "od", "crash": False, "fill": "drag"},
        {"label": "Couplet 3", "bars": 8, "groove": "od", "crash": False, "fill": "drag"},
        {"label": "Outro", "bars": 8, "groove": "od", "crash": False, "text": "tot fade", "end": True},
    ],
}

GROOVES = {
    "od": {"HH": "x-x-x-x-x-x-x-x-", "RS": "--------c-------", "BD": "--------x-------"},
}
FILLS = dict(FILLS_44,
    drag={"SD": "------------xxx-", "T2": "---------------x", "BD": "--------x-------"},
)
