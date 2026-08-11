"""Parse the firmware universal .ir libraries into ordered JS code tables.

Output: for each function we want, a list of [protocol, address, command] with the
most-likely brands first, then everything else, deduplicated. `infrared.sendSignal`
takes the protocol name string plus integer address/command, so that is what we emit.
"""
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))

# protocol+address signatures of the globally most common brands, best first.
# address is the little-endian integer of the .ir "address:" bytes.
BRAND_RANK = [
    ("Samsung32", 0x07),   # Samsung
    ("NEC", 0x04),         # LG (NEC addr 04)
    ("NECext", 0x04),      # LG variants
    ("SIRC", 0x01),        # Sony
    ("SIRC15", 0x01),
    ("SIRC20", 0x01),
    ("Kaseikyo", None),    # Panasonic
    ("RC6", 0x00),         # Philips
    ("RC5", 0x00),         # Philips / generic
    ("NECext", 0x20DF),    # LG NECext (0xDF 0x20)
    ("NEC", 0x00),         # Vizio / generic NEC
    ("NECext", 0x08),      # Toshiba / Insignia
    ("RCA", None),         # RCA
]


def parse_ir(path):
    """Yield dicts {name, protocol, address, command} for parsed entries."""
    entry = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if line.startswith("#"):
            if entry.get("type") == "parsed" and "protocol" in entry:
                yield entry
            entry = {}
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        entry[k.strip()] = v.strip()
    if entry.get("type") == "parsed" and "protocol" in entry:
        yield entry


def le_int(hexbytes):
    vals = [int(x, 16) for x in hexbytes.split()]
    n = 0
    for i, b in enumerate(vals):
        n |= b << (8 * i)
    return n


def rank(proto, addr):
    for i, (p, a) in enumerate(BRAND_RANK):
        if p == proto and (a is None or a == addr):
            return i
    return len(BRAND_RANK)


def codes_for(path, names):
    """Ordered, de-duplicated [proto, addr, cmd] for the given signal names."""
    want = set(n.lower() for n in names)
    rows, seen = [], set()
    for i, e in enumerate(parse_ir(path)):
        if e["name"].lower() not in want:
            continue
        proto = e["protocol"]
        addr = le_int(e["address"])
        cmd = le_int(e["command"])
        key = (proto, addr, cmd)
        if key in seen:
            continue
        seen.add(key)
        rows.append((rank(proto, addr), i, proto, addr, cmd))
    rows.sort(key=lambda r: (r[0], r[1]))       # brand rank, then file order
    return [[p, a, c] for _, _, p, a, c in rows]


def main():
    tv = os.path.join(HERE, "tv.ir")
    au = os.path.join(HERE, "audio.ir")

    tables = {
        # silence: power-off + mute for both TVs and audio
        "TV_POWER":   codes_for(tv, ["Power", "POWER", "Power_off", "Off"]),
        "TV_MUTE":    codes_for(tv, ["Mute"]),
        "TV_VOL_DN":  codes_for(tv, ["Vol_dn", "Vol_down", "Volume_down"]),
        "TV_VOL_UP":  codes_for(tv, ["Vol_up", "Vol_UP", "Volume_up"]),
        "AUDIO_POWER": codes_for(au, ["Power", "POWER", "Off"]),
        "AUDIO_MUTE":  codes_for(au, ["Mute"]),
        "AUDIO_VOL_DN": codes_for(au, ["Vol_dn", "Vol_down", "Volume_down", "VOL-"]),
        "AUDIO_VOL_UP": codes_for(au, ["Vol_up", "Volume_up", "VOL+"]),
    }
    for k, v in tables.items():
        print("%-13s %4d codes  (first: %s)" % (k, len(v), v[0] if v else "-"))

    with open(os.path.join(HERE, "ir_tables.json"), "w") as fh:
        json.dump(tables, fh)
    return tables


if __name__ == "__main__":
    main()
