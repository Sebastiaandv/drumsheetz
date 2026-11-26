"""Gedeelde fills en slotslagen (4/4, 16den-raster: 16 tekens per maat).
x = slag, X = accent, g = ghost, o = open hihat (in HH-rij), - = rust."""

SUB = "Drum lead sheet"

FILLS_44 = {
    # 16den op tel 4
    "sd4": {"SD": "------------xxxx", "BD": "x-------x-------"},
    # 8sten oppikker op 4 en
    "pick8": {"SD": "------------x-x-", "BD": "x-------x-------"},
    # snare tel 4, floor tom op 4-en
    "bal4": {"SD": "------------xx--", "FT": "--------------xx", "BD": "x-------x-------"},
    # dalende toms over tel 3-4
    "tom34": {"SD": "--------xx------", "T1": "----------xx----", "T2": "------------xx--",
              "FT": "--------------xx", "BD": "x-------x-------"},
    # snare 16den over tel 3-4 met crescendo-accenten
    "sd34": {"SD": "--------xxxxxXxX", "BD": "x-------x-------"},
    # hele maat rond de toms
    "tomfull": {"SD": "xxxx------------", "T1": "----xxxx--------", "T2": "--------xxxx----",
                "FT": "------------xxxx", "BD": "x---x---x---x---"},
    # zachte ballad-oppikker: rim + floor tom
    "soft4": {"RS": "------------c---", "FT": "--------------x-", "BD": "x-------x-------"},
}

HIT = {"CR": "x---------------", "BD": "x---------------"}          # slotslag
STOP = {"CR": "x---------------", "BD": "x---------------"}
