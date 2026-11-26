from common import SUB

# 6/8: 6 tekens per maat (8sten)
SONG = {
    "title": "Somebody To Love", "artist": "Queen", "subtitle": SUB,
    "bpm": 55, "meter": (6, 8), "feel": "Gospel in 6/8 · tel in twee",
    "sections": [
        {"label": "Intro", "bars": 4, "groove": None, "text": "a cappella koor · tacet"},
        {"label": "Couplet 1", "bars": 16, "groove": "v", "crash": True, "fill": "trip"},
        {"label": "Refrein", "bars": 8, "groove": "ch", "crash": True, "fill": "tom"},
        {"label": "Couplet 2", "bars": 16, "groove": "v", "crash": True, "fill": "trip"},
        {"label": "Refrein", "bars": 8, "groove": "ch", "crash": True, "fill": "tom"},
        {"label": "Gitaarsolo", "bars": 16, "groove": "ch", "crash": True, "fill": "tom"},
        {"label": "Couplet 3", "bars": 16, "groove": "v", "crash": True, "fill": "trip"},
        {"label": "Breakdown", "bars": 16, "groove": "clap", "crash": True,
         "text": "stop-time · koor en handclaps", "fill": "trip"},
        {"label": "Opbouw", "bars": 8, "groove": "ch", "crash": True, "fill": "tom"},
        {"label": "Outro", "bars": 16, "groove": "ch", "crash": True, "text": "koor-vamp · tot fade", "end": True},
    ],
}

GROOVES = {
    "v":    {"HH": "xxxxxx", "SD": "---x--", "BD": "x----x"},
    "ch":   {"RD": "xxxxxx", "SD": "---x--", "BD": "x-x--x"},
    "clap": {"SD": "---x--", "BD": "x-----"},
}
FILLS = {
    "trip": {"SD": "---xxx", "BD": "x-----"},
    "tom":  {"SD": "xx----", "T1": "--xx--", "FT": "----xx", "BD": "x--x--"},
}
