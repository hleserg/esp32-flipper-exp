"""Verify the generated blobs: structural validity + every source frame present."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from subtool import (parse_sub, normalize, duration, frames_match, MAX_PULSE,
                     GAP_CLAMP, DEVICE_GAP)
import build

ok = True


def fail(msg):
    global ok
    ok = False
    print("  FAIL:", msg)


def contains_frame(blob, frame):
    """Is `frame` present verbatim somewhere in the concatenated blob?"""
    n = len(frame)
    for i in range(len(blob) - n + 1):
        if frames_match(blob[i:i + n], frame):
            return True
    return False


for fname, (label, members) in build.BLOBS.items():
    path = os.path.join(build.OUT, fname + ".sub")
    sub = parse_sub(path)
    blob = sub["raw"]
    print("%s (%s)  %d pulses  %.0f ms" % (fname, label, len(blob), duration(blob) / 1000))

    if sub.get("Filetype") != "Flipper SubGhz RAW File":
        fail("bad Filetype %r" % sub.get("Filetype"))
    if int(sub["Frequency"]) != 433920000:
        fail("frequency %s" % sub["Frequency"])
    if sub["Preset"] != "FuriHalSubGhzPresetOok650Async":
        fail("preset %s" % sub["Preset"])
    if sub["Protocol"] != "RAW":
        fail("protocol %s" % sub["Protocol"])
    if len(label) > 16:
        fail("label %r longer than 16 chars" % label)

    if any(p == 0 for p in blob):
        fail("zero-length entry")
    bad = [i for i, (a, b) in enumerate(zip(blob, blob[1:])) if (a > 0) == (b > 0)]
    if bad:
        fail("sign alternation broken at %d place(s), first at index %d" % (len(bad), bad[0]))
    if blob[0] < 0:
        fail("blob starts with a gap")
    if blob[-1] < 0:
        fail("blob ends with a gap")

    worst_mark = max(p for p in blob if p > 0)
    worst_gap = -min(p for p in blob if p < 0)
    if worst_mark > MAX_PULSE:
        fail("mark of %d us exceeds MAX_PULSE" % worst_mark)
    if worst_gap > DEVICE_GAP:
        fail("gap of %d us exceeds DEVICE_GAP" % worst_gap)
    print("   longest mark %d us, longest gap %d us" % (worst_mark, worst_gap))

    for name in members:
        part = build.load(name)
        # one repetition of that device's frame, without the joining gap
        frame = []
        for p in part:
            if p < 0 and -p >= DEVICE_GAP // 3:
                break
            frame.append(p)
        if not contains_frame(blob, frame):
            fail("%s: frame not found in blob" % name)
    print("   %d/%d source frames located inside the blob"
          % (sum(1 for _ in members), len(members)))

# map file
mp = os.path.join(build.MAP_DIR, "SEXTOY_ALL.txt")
lines = [l.strip() for l in open(mp) if l.strip()]
print("\nmap:", os.path.normpath(mp))
if lines[0] != "Filetype: Flipper SubRem Map file":
    fail("map header %r" % lines[0])
if lines[1] != "Version: 1":
    fail("map version %r" % lines[1])
for key in ("UP", "DOWN", "LEFT", "RIGHT", "OK"):
    row = [l for l in lines if l.startswith(key + ":")]
    if not row:
        fail("map missing %s" % key)
        continue
    p = row[0].split(": ", 1)[1]
    if " " in p or not all(c.isalnum() or c in "._-/" for c in p):
        fail("map path %r has characters the app rejects" % p)
    local = os.path.join(build.ROOT, p.replace("/ext/subghz/", "").replace("/", os.sep))
    if not os.path.exists(local):
        fail("map path %s does not resolve to a generated file" % p)

print("\nALL CHECKS PASSED" if ok else "\nTHERE WERE FAILURES")
sys.exit(0 if ok else 1)
