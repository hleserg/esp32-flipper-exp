"""Generate justforfun.js from the IR tables and curated Sub-GHz path lists.

The whole Sub-GHz DB already lives on the SD card, so the script transmits files
straight from their /ext/subghz/... paths; each transmitFile is wrapped in try/
catch on the device so a path that differs on a given card is skipped, not fatal.
"""
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "justforfun.js")
SUB = "/ext/subghz/"

# ---- curated Sub-GHz device files (one representative per device) ----------
# Toggle/power files (t) flip state; dedicated on/off are explicit.
LIGHTS_ON = [
    "Govee-LED_LightStrand/On.sub",
    "LED/Govee_LED_String/On.sub",
    "LED/Commercial_Electric_White_LED_Tape/On.sub",
    "LED/EverFlourish_LEDs/On.sub",
    "LED/RF_LED_Controller_T917/On.sub",
    "LED/LEDGLOW_Motorcycle_Lights/On.sub",
    "LED/SUPERNIGHT_RGBW_LED/On.sub",
    "LED/Aurora_RGB/Power.sub",          # toggle
    "LED/JOOFO_Floor_Lamp/Power.sub",    # toggle
    "LED/RGB_LED_Lamp/power.sub",        # toggle
    "LED/RITSEC_Neon_Light/Pwr.sub",     # toggle
    "LED/Speclux_LED_Strip/POWER.sub",   # toggle
    "Remote_Outlet_Switches/Defiant_Outlet/On_1.sub",
    "Remote_Outlet_Switches/First_Alert-FA200/On.sub",
    "Remote_Outlet_Switches/MasterElectrician_TR-026A/On.sub",
    "Remote_Outlet_Switches/Woods_Remote_Outlet/On.sub",
    "Cooker_Hoods/Elica/light_on.sub",
]
LIGHTS_OFF = [
    "Govee-LED_LightStrand/Off.sub",
    "LED/Govee_LED_String/Off.sub",
    "LED/Commercial_Electric_White_LED_Tape/Off.sub",
    "LED/EverFlourish_LEDs/Off.sub",
    "LED/RF_LED_Controller_T917/Off.sub",
    "LED/LEDGLOW_Motorcycle_Lights/Off.sub",
    "LED/SUPERNIGHT_RGBW_LED/Off.sub",
    "Remote_Outlet_Switches/Defiant_Outlet/Off_1.sub",
    "Remote_Outlet_Switches/First_Alert-FA200/Off.sub",
    "Remote_Outlet_Switches/MasterElectrician_TR-026A/Off.sub",
    "Remote_Outlet_Switches/Woods_Remote_Outlet/Off.sub",
    "Cooker_Hoods/Elica/light_off.sub",
    # toggles again: in a lit venue these are ON, so the toggle turns them OFF
    "LED/Aurora_RGB/Power.sub",
    "LED/JOOFO_Floor_Lamp/Power.sub",
    "LED/RGB_LED_Lamp/power.sub",
    "LED/RITSEC_Neon_Light/Pwr.sub",
    "LED/Speclux_LED_Strip/POWER.sub",
]
# Noisy appliances OFF
NOISE_OFF_SUB = [
    "Cooker_Hoods/Elica/fan_off.sub",
    "Air_Filtration/WEN_3410_Air_Filter/Off.sub",
    "Vacuum/Samsung/On_Off_Samsung_VC06H70F0HD.sub",   # toggle -> off if running
    "Fans/Flowmate Classic/Power.sub",                 # toggle
    "Ceiling_Fans/Hampton_Bay_Ceiling_Fan_2/Off.sub",
    "Ceiling_Fans/Sofucor_Fan_KBS-56K001/power_off.sub",
]
# Noisy appliances ON / MAX
NOISE_ON_SUB = [
    "Vacuum/Samsung/On_Samsung_SC20F70HB.sub",
    "Vacuum/Samsung/Stronger_Samsung_VC06H70F0HD.sub",
    "Cooker_Hoods/Elica/fan_plus.sub",
    "Air_Filtration/WEN_3410_Air_Filter/On_speed.sub",
    "Fans/Flowmate Classic/Power.sub",
    "Fans/Flowmate Classic/Speed.sub",
    "Ceiling_Fans/Hampton_Bay_Ceiling_Fan_2/High.sub",
]
# Toys: known captured set (ALL_PWR blob) first, then per-family scoped brute
# sweeps. These live in Sextoy_ALL/, not the shared DB path prefix.
TOYS_SUB = [
    "Sextoy_ALL/ALL_PWR.sub",
    "Sextoy_ALL/TOYS_BRUTE_8B02.sub",
    "Sextoy_ALL/TOYS_BRUTE_00FF.sub",
    "Sextoy_ALL/TOYS_BRUTE_AA55.sub",
]


def js_paths(lst):
    return "[\n" + ",\n".join('    "%s%s"' % (SUB, p) for p in lst) + "\n  ]"


# Keep the embedded IR arrays small so the mjs heap can never overflow. The
# tables are already ranked most-likely-brand-first, so the top slice is the
# high-hit-rate head; the long tail is dropped on purpose (memory > completeness).
IR_TOP = 24


def js_ir(rows):
    rows = rows[:IR_TOP]
    return "[" + ",".join('["%s",%d,%d]' % (p, a, c) for p, a, c in rows) + "]"


def main():
    ir = json.load(open(os.path.join(HERE, "ir_tables.json")))
    tpl = open(os.path.join(HERE, "justforfun.template.js"), encoding="utf-8").read()
    subst = {
        "LIGHTS_ON": js_paths(LIGHTS_ON),
        "LIGHTS_OFF": js_paths(LIGHTS_OFF),
        "NOISE_OFF_SUB": js_paths(NOISE_OFF_SUB),
        "NOISE_ON_SUB": js_paths(NOISE_ON_SUB),
        "TOYS_SUB": js_paths(TOYS_SUB),
        "TV_POWER": js_ir(ir["TV_POWER"]),
        "TV_MUTE": js_ir(ir["TV_MUTE"]),
        "TV_VOL_DN": js_ir(ir["TV_VOL_DN"]),
        "TV_VOL_UP": js_ir(ir["TV_VOL_UP"]),
        "AUDIO_POWER": js_ir(ir["AUDIO_POWER"]),
        "AUDIO_MUTE": js_ir(ir["AUDIO_MUTE"]),
        "AUDIO_VOL_DN": js_ir(ir["AUDIO_VOL_DN"]),
        "AUDIO_VOL_UP": js_ir(ir["AUDIO_VOL_UP"]),
    }
    for k, v in subst.items():
        tpl = tpl.replace("/*{%s}*/" % k, v)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(tpl)
    embedded = sum(min(IR_TOP, len(ir[k])) for k in ir)
    print("wrote", OUT, "%.1f KB" % (os.path.getsize(OUT) / 1024))
    print("IR codes embedded: %d (top %d of each of %d functions)"
          % (embedded, IR_TOP, len(ir)))
    print("SubGhz: lights_on=%d lights_off=%d noise_off=%d noise_on=%d" %
          (len(LIGHTS_ON), len(LIGHTS_OFF), len(NOISE_OFF_SUB), len(NOISE_ON_SUB)))


if __name__ == "__main__":
    main()
