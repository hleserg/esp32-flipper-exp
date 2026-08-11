"""Generate a scoped toy brute-force blob.

We do NOT blind-sweep the 24-bit Princeton space (that would toggle garage
doors, outlets and alarms that also use PT2262). Instead we sweep only the
variable low byte of the THREE code families actually observed in captured
toys, at each family's own TE:

    8B02 xx  @ TE 362   (Sextoy1-4 family)
    00FF xx  @ TE 391   (Sway Vibes family)
    AA55 xx  @ TE 240   (Sinful Bullet family)

That reaches sibling models/buttons of the same chip families while staying far
narrower than a blind sweep. Output is one 433.92 OOK RAW blob.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from subtool import (render_princeton, normalize, clamp_gaps, duration,
                     write_raw, DEVICE_GAP)

OUTDIR = r"C:\projects\FlipperZero-Subghz-DB\subghz\Sextoy_ALL"

FAMILIES = [
    ("8B02", 362, "Sextoy1-4"),   # prefix (top 16 bits), TE, note
    ("00FF", 391, "Sway Vibes"),
    ("AA55", 240, "Sinful Bullet"),
]
REPEATS = 2
INTER_GAP = DEVICE_GAP // 3   # 8.3 ms between codes


def frame_for(prefix, low, te):
    key = "00 00 00 00 00 %02X %02X %02X" % (
        (int(prefix, 16) >> 8) & 0xFF, int(prefix, 16) & 0xFF, low)
    sub = {"TE": te, "Bit": 24, "Key": key, "path": "brute"}
    return clamp_gaps(normalize(render_princeton(sub)))


def main():
    total = 0
    for prefix, te, note in FAMILIES:
        pulses = []
        for low in range(0x00, 0x100):
            frame = frame_for(prefix, low, te)
            for r in range(REPEATS):
                if pulses:
                    pulses.append(-INTER_GAP)
                pulses.extend(frame)
        path = os.path.join(OUTDIR, "TOYS_BRUTE_%s.sub" % prefix)
        n, dur = write_raw(path, pulses, [
            "Scoped toy brute: %sxx @ TE %d (%s family), low byte 00-FF x%d"
            % (prefix, te, note, REPEATS),
            "433.92 OOK. NOT a blind 24-bit sweep - only this observed family.",
        ])
        total += dur
        print("TOYS_BRUTE_%s.sub  256 codes  pulses=%d  airtime=%.1fs"
              % (prefix, n, dur / 1_000_000))
    print("total brute airtime %.1fs across 3 files" % (total / 1_000_000))


if __name__ == "__main__":
    main()
