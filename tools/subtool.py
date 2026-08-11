"""Parse Flipper .sub files, render every protocol down to OOK pulse trains,
then splice per-function pulse trains into one combined RAW .sub per button.

Protocol rendering follows the firmware encoders:
  Princeton -> lib/subghz/protocols/princeton.c  (bit1 = 3TE high + TE low,
               bit0 = TE high + 3TE low, stop bit TE high, guard = TE*guard_time)
  BinRAW    -> lib/subghz/protocols/bin_raw.c + blocks/encoder.c
               (73 significant bits are right-aligned in the byte array, so skip
               full_bytes*8 - Bit bits; then equal-value runs -> run_len * TE,
               bit value 1 = carrier on)
"""
import re
import os
from collections import Counter

# --- limits -----------------------------------------------------------------
MAX_PULSE = 5000      # us; a positive longer than this is not a real OOK mark here
GAP_CLAMP = 12000     # us; any internal gap is capped to this (leaves room for
                      # Princeton's own guard time of TE*30 ~ 11 ms)
FRAME_GAP = 3000      # us; gaps at least this long separate repeats of a frame
DEVICE_GAP = 25000    # us; silence inserted between two different devices
VALUES_PER_LINE = 512 # firmware writes RAW_Data in chunks; match that shape


# --- parsing ----------------------------------------------------------------
def parse_sub(path):
    """Return dict of the .sub header plus 'raw' = list of ints for RAW files."""
    out = {"raw": [], "path": path}
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            if key == "RAW_Data":
                out["raw"].extend(int(x) for x in val.split())
            else:
                out[key] = val
    return out


def hexbytes(s):
    return [int(x, 16) for x in s.split()]


# --- protocol -> pulses -----------------------------------------------------
def render_princeton(sub):
    te = int(sub["TE"])
    nbit = int(sub["Bit"])
    guard = int(sub.get("Guard_Time", 30))
    data = 0
    for b in hexbytes(sub["Key"]):
        data = (data << 8) | b
    pulses = []
    for i in range(nbit - 1, -1, -1):
        if (data >> i) & 1:
            pulses += [3 * te, -te]
        else:
            pulses += [te, -3 * te]
    pulses += [te, -te * guard]           # stop bit + guard time
    return pulses


def render_binraw(sub):
    te = int(sub["TE"])
    nbit = int(sub["Bit_RAW"] if "Bit_RAW" in sub else sub["Bit"])
    data = hexbytes(sub["Data_RAW"])
    full_bytes = (nbit + 7) // 8
    bias = full_bytes * 8 - nbit          # significant bits are right-aligned
    bits = []
    for i in range(bias, bias + nbit):
        bits.append((data[i // 8] >> (7 - i % 8)) & 1)
    pulses, run, cur = [], 0, bits[0]
    for b in bits:
        if b == cur:
            run += 1
        else:
            pulses.append(run * te if cur else -run * te)
            cur, run = b, 1
    pulses.append(run * te if cur else -run * te)
    return pulses


def render(sub):
    proto = sub.get("Protocol", "")
    if proto == "RAW":
        return list(sub["raw"])
    if proto == "Princeton":
        return render_princeton(sub)
    if proto == "BinRAW":
        return render_binraw(sub)
    raise ValueError("unsupported protocol %r in %s" % (proto, sub["path"]))


# --- pulse train hygiene ----------------------------------------------------
def normalize(pulses):
    """Drop zeros and merge adjacent same-sign values so signs strictly alternate."""
    out = []
    for p in pulses:
        if p == 0:
            continue
        if out and (out[-1] > 0) == (p > 0):
            out[-1] += p
        else:
            out.append(p)
    return out


def trim(pulses):
    """Cut leading/trailing dead air and anything that cannot be a real mark."""
    start = 0
    while start < len(pulses) and not (0 < pulses[start] <= MAX_PULSE):
        start += 1
    end = len(pulses)
    while end > start and not (0 < pulses[end - 1] <= MAX_PULSE):
        end -= 1
    return pulses[start:end]


def split_frames(pulses):
    """Split a capture into frames at long gaps, dropping impossible marks."""
    frames, cur = [], []
    for p in pulses:
        if p > MAX_PULSE:                 # oversized "mark" = recorder artefact
            if cur:
                frames.append(cur)
            cur = []
        elif p < 0 and -p >= FRAME_GAP:
            if cur:
                frames.append(cur)
            cur = []
        else:
            cur.append(p)
    if cur:
        frames.append(cur)
    return [normalize(trim(f)) for f in frames if len(normalize(trim(f))) >= 8]


def cluster_score(pulses):
    """Fraction of marks covered by the 4 most common pulse widths (25% tolerance).

    Real OOK uses a handful of symbol widths; a noise capture spreads uniformly.
    """
    marks = [p for p in pulses if p > 0]
    if len(marks) < 12:
        return 0.0, len(marks)
    marks_sorted = sorted(marks)
    clusters = []
    for m in marks_sorted:
        for c in clusters:
            if abs(m - c[0]) <= 0.25 * c[0]:
                c[1] += 1
                break
        else:
            clusters.append([m, 1])
    clusters.sort(key=lambda c: -c[1])
    top = sum(c[1] for c in clusters[:4])
    return top / len(marks), len(marks)


def duration(pulses):
    return sum(abs(p) for p in pulses)


def clamp_gaps(pulses):
    return [p if p > 0 else max(p, -GAP_CLAMP) for p in pulses]


def frames_match(a, b, tol=0.30, floor=120):
    """True if two frames are the same transmission recorded twice."""
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if (x > 0) != (y > 0):
            return False
        if abs(abs(x) - abs(y)) > max(floor, tol * abs(x)):
            return False
    return True


def split_frames_by_preamble(pulses):
    """Split where a mark is much longer than the rest: many remotes delimit
    repeats with a long preamble burst instead of a long gap."""
    marks = sorted(p for p in pulses if p > 0)
    if len(marks) < 20:
        return []
    median = marks[len(marks) // 2]
    limit = max(2.5 * median, 800)
    frames, cur = [], []
    for p in pulses:
        if p > limit:
            if len(cur) >= 8:
                frames.append(cur)
            cur = [p]
        else:
            cur.append(p)
    if len(cur) >= 8:
        frames.append(cur)
    return [normalize(trim(f)) for f in frames if len(normalize(trim(f))) >= 8]


def _largest_group(frames, min_pulses):
    frames = [f for f in frames if len(f) >= min_pulses]
    best = []
    for f in frames:
        group = [g for g in frames if frames_match(f, g)]
        if len(group) > len(best):
            best = group
    return best


def best_repeat_group(pulses, min_pulses=16):
    """Largest set of mutually identical frames in a capture, and its medoid.

    A real remote sends the same frame several times; receiver noise never
    repeats.  This is the test that separates a usable capture from junk.
    Both delimiters are tried (long gap, long preamble mark) and the strategy
    that finds more repeats wins.
    """
    best = []
    for frames in (split_frames(pulses), split_frames_by_preamble(pulses)):
        group = _largest_group(frames, min_pulses)
        if len(group) > len(best) or (len(group) == len(best) and group and
                                      len(group[0]) > len(best[0])):
            best = group
    if not best:
        return None, 0
    medoid = max(best, key=lambda f: cluster_score(f)[0])
    return medoid, len(best)


def pick_frames(pulses, repeats=2, min_pulses=16):
    """Return one clean frame from a capture, repeated `repeats` times."""
    frame, n = best_repeat_group(pulses, min_pulses)
    if frame is None or n < 2:
        return []
    out = []
    for i in range(repeats):
        if i:
            out.append(-DEVICE_GAP // 3)
        out.extend(clamp_gaps(frame))
    return normalize(out)


# --- writing ----------------------------------------------------------------
HEADER = ("Filetype: Flipper SubGhz RAW File\n"
          "Version: 1\n"
          "Frequency: 433920000\n"
          "Preset: FuriHalSubGhzPresetOok650Async\n"
          "Protocol: RAW\n")


def write_raw(path, pulses, comment_lines=()):
    pulses = normalize(pulses)
    assert all(p != 0 for p in pulses)
    for a, b in zip(pulses, pulses[1:]):
        assert (a > 0) != (b > 0), "sign alternation broken"
    with open(path, "w", newline="\n") as fh:
        fh.write(HEADER)
        for c in comment_lines:
            fh.write("# %s\n" % c)
        for i in range(0, len(pulses), VALUES_PER_LINE):
            chunk = pulses[i:i + VALUES_PER_LINE]
            fh.write("RAW_Data: " + " ".join(str(x) for x in chunk) + "\n")
    return len(pulses), duration(pulses)
