"""Build the universal sex-toy remote: five combined RAW blobs + a SubRem map."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from subtool import (parse_sub, render, normalize, trim, duration,
                     pick_frames, clamp_gaps, write_raw, DEVICE_GAP)

ROOT = r"C:\projects\FlipperZero-Subghz-DB\subghz"
OUT = os.path.join(ROOT, "Sextoy_ALL")
MAP_DIR = os.path.join(ROOT, "..", "subghz_remote")   # mirrors /ext/subghz_remote
SD = "/ext/subghz/Sextoy_ALL"

S = "Misc/Sextoy/"
# device label -> source file
SRC = {
    "sextoy1":      S + "Sextoy1.sub",
    "sextoy2":      S + "Sextoy2.sub",
    "sextoy3":      S + "Sextoy3.sub",
    "sextoy4":      S + "Sextoy4.sub",
    "sinful_pwr":   S + "Sinful Bullet Vibrator/Sinful_power.sub",
    "sinful_lvl":   S + "Sinful Bullet Vibrator/Sinful_level.sub",
    "sway_pwr":     S + "Sway Vibes 3/Sway_vib_on_off.sub",
    "sway_mode":    S + "Sway Vibes 3/Sway_vib_mode.sub",
    "wevibe_on":    "WeVibe Unit 2/WeVibe_on.sub",
    "wevibe_off":   "WeVibe Unit 2/WeVibe_off.sub",
    "lovebox_on":   S + "LoveBox_Vibrating_Egg/Lovebox_on.sub",
    "lovebox_up":   S + "LoveBox_Vibrating_Egg/Lovebox_up.sub",
    "lovebox_down": S + "LoveBox_Vibrating_Egg/Lovebox_down.sub",
    "lovebox_lf":   S + "LoveBox_Vibrating_Egg/Lovebox_lfrec.sub",
    "lovebox_mf":   S + "LoveBox_Vibrating_Egg/Lovebox_mfrec.sub",
    "egg_pwr":      S + "Egg Vibrator/Egg_vib_power.sub",
    "egg_int":      S + "Egg Vibrator/Egg_vib_intensity.sub",
    "egg_mode":     S + "Egg Vibrator/Egg_vib_mode.sub",
    "nu_on":        S + "Nu_Sensuelle_Vibrating_Mini-Plug/Bp_01_1.sub",
    "nu_mode":      S + "Nu_Sensuelle_Vibrating_Mini-Plug/Bp_02_1.sub",
    "nu_off":       S + "Nu_Sensuelle_Vibrating_Mini-Plug/Bp_off.sub",
    "vib_on_mode":  S + "other_Egg_Vibrator/Vib_Toy_ON_and_Mode.sub",
    "vib_off":      S + "other_Egg_Vibrator/Vib_Toy_OFF.sub",
    "plug_on":      S + "James_Anal_Plug/Plug_on_button.sub",
    "plug_off":     S + "James_Anal_Plug/Plug_off.sub",
    "plug_mode":    S + "James_Anal_Plug/Plug_frec_change.sub",
    "rabbit_pwr":   S + "Sexrabbit_Vibrator/Power_Toggle_Long_Press.sub",
}

BLOBS = {
    # file           label (<=16 chars)   members, in transmit order
    "ALL_PWR":  ("PWR ALL", [
        "sextoy1", "sextoy2", "sextoy3", "sextoy4",   # same device, 4 unknown buttons
        "sinful_pwr", "sway_pwr", "wevibe_on", "lovebox_on",
        "egg_pwr", "nu_on", "vib_on_mode", "plug_on", "rabbit_pwr"]),
    "ALL_UP":   ("PWR + / LVL UP", [
        "sinful_lvl", "lovebox_up", "egg_int"]),
    "ALL_DOWN": ("PWR - / LVL DN", [
        "lovebox_down", "sinful_lvl", "egg_int"]),
    "ALL_MODE": ("MODE / PATTERN", [
        "sway_mode", "egg_mode", "lovebox_lf", "lovebox_mf",
        "nu_mode", "vib_on_mode", "plug_mode"]),
    "ALL_OFF":  ("OFF ALL", [
        "wevibe_off", "nu_off", "vib_off", "plug_off"]),
}

RAW_REPEATS = 2      # a captured frame is re-sent this many times
KEY_REPEATS = 3      # a decoded protocol frame is cheap, send it more often
# Sextoy1-4 are four buttons of one device; two repeats each keeps PWR short.
REPEAT_OVERRIDE = {"sextoy1": 2, "sextoy2": 2, "sextoy3": 2, "sextoy4": 2}


def load(name):
    """Render one source file down to a clean, repeated pulse train."""
    sub = parse_sub(os.path.join(ROOT, SRC[name].replace("/", os.sep)))
    assert int(sub["Frequency"]) == 433920000, \
        "%s is not 433.92 MHz - cannot share a blob" % SRC[name]
    assert sub["Preset"].startswith("FuriHalSubGhzPresetOok"), \
        "%s is not OOK - cannot share a blob" % SRC[name]

    if sub["Protocol"] == "RAW":
        pulses = normalize(trim(normalize(render(sub))))
        out = pick_frames(pulses, repeats=REPEAT_OVERRIDE.get(name, RAW_REPEATS))
        assert out, "%s: no repeated frame found" % SRC[name]
        return out

    # Princeton / BinRAW: already an exact frame. Keep whatever inter-frame guard
    # the encoder emits (Princeton ends with TE*30) instead of trimming it away.
    frame = clamp_gaps(normalize(render(sub)))
    while frame and frame[0] < 0:
        frame.pop(0)
    out = []
    for i in range(REPEAT_OVERRIDE.get(name, KEY_REPEATS)):
        if i and out[-1] > 0:
            out.append(-DEVICE_GAP // 3)
        out.extend(frame)
    while out and out[-1] < 0:
        out.pop()
    return normalize(out)


def main():
    os.makedirs(OUT, exist_ok=True)
    report = []
    for fname, (label, members) in BLOBS.items():
        pulses, comments = [], ["%s - combined transmit blob" % label]
        for name in members:
            if pulses:
                pulses.append(-DEVICE_GAP)
            part = load(name)
            comments.append("%-13s %-52s %4d pulses %6.1f ms"
                            % (name, SRC[name], len(part), duration(part) / 1000))
            pulses.extend(part)
        n, dur = write_raw(os.path.join(OUT, fname + ".sub"), pulses, comments)
        report.append((fname, label, len(members), n, dur / 1000))

    os.makedirs(MAP_DIR, exist_ok=True)
    with open(os.path.join(MAP_DIR, "SEXTOY_ALL.txt"), "w", newline="\n") as fh:
        fh.write("Filetype: Flipper SubRem Map file\nVersion: 1\n")
        for key, lblkey, fname in (("UP", "ULABEL", "ALL_UP"),
                                   ("DOWN", "DLABEL", "ALL_DOWN"),
                                   ("LEFT", "LLABEL", "ALL_MODE"),
                                   ("RIGHT", "RLABEL", "ALL_OFF"),
                                   ("OK", "OKLABEL", "ALL_PWR")):
            fh.write("%s: %s/%s.sub\n" % (key, SD, fname))
            fh.write("%s: %s\n" % (lblkey, BLOBS[fname][0]))

    print("%-10s %-16s %8s %8s %9s" % ("blob", "label", "devices", "pulses", "airtime"))
    for fname, label, nmem, n, ms in report:
        print("%-10s %-16s %8d %8d %7.0f ms" % (fname, label, nmem, n, ms))


if __name__ == "__main__":
    main()
