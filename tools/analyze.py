import os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from subtool import *

ROOT = r"C:\projects\FlipperZero-Subghz-DB\subghz"

# ---- self-test: Princeton round trip ---------------------------------------
def decode_princeton(pulses, te, nbit):
    bits = []
    i = 0
    while i + 1 < len(pulses) and len(bits) < nbit:
        hi, lo = pulses[i], -pulses[i + 1]
        bits.append(1 if hi > 2 * te else 0)
        i += 2
    v = 0
    for b in bits:
        v = (v << 1) | b
    return v

for p in [r"Misc\Sextoy\Sinful Bullet Vibrator\Sinful_power.sub",
          r"Misc\Sextoy\Sway Vibes 3\Sway_vib_mode.sub",
          r"Misc\Sextoy\Sextoy1.sub"]:
    s = parse_sub(os.path.join(ROOT, p))
    pulses = render(s)
    te, nbit = int(s["TE"]), int(s["Bit"])
    got = decode_princeton(pulses, te, nbit)
    want = int(s["Key"].replace(" ", ""), 16)
    print("PRINCETON %-40s key=%06X decoded=%06X %s  dur=%.1fms" %
          (os.path.basename(p), want, got, "OK" if got == want else "MISMATCH",
           duration(pulses) / 1000))

s = parse_sub(os.path.join(ROOT, "WeVibe Unit 2", "WeVibe_on.sub"))
pl = render(s)
te, nb = int(s["TE"]), int(s["Bit_RAW"])
print("BINRAW    WeVibe_on  bits=%d te=%d  rendered_dur=%d expected=%d %s" %
      (nb, te, duration(pl), nb * te, "OK" if duration(pl) == nb * te else "MISMATCH"))
print()

# ---- structure report over every candidate ---------------------------------
files = sorted(glob.glob(os.path.join(ROOT, "Misc", "Sextoy", "**", "*.sub"), recursive=True))
files += sorted(glob.glob(os.path.join(ROOT, "WeVibe Unit 2", "*.sub")))
print("%-52s %-9s %5s %6s %6s %7s %6s" %
      ("file", "proto", "freq", "raw_us", "score", "frames", "keep_us"))
for f in files:
    if "Bp_" in f and not (f.endswith("Bp_off.sub") or "_1.sub" in f):
        continue
    s = parse_sub(f)
    try:
        pl = render(s)
    except Exception as e:
        print("SKIP", f, e); continue
    freq = int(s["Frequency"])
    raw_us = duration(pl)
    keep = pick_frames(normalize(trim(normalize(pl))), repeats=1)
    sc, nm = cluster_score(keep) if keep else (0.0, 0)
    rel = os.path.relpath(f, ROOT)
    print("%-52s %-9s %5d %6d %6.2f %7d %6d" %
          (rel[-52:], s.get("Protocol"), freq // 1000000, raw_us // 1000,
           sc, len(split_frames(normalize(trim(normalize(pl))))), duration(keep) // 1000))
