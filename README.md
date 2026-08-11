# esp32-flipper-exp — "chaos from one button"

A Flipper Zero (Unleashed firmware) + ESP32 rig that fires a whole room's worth of
wireless gadgets from a **single button press**: Sub-GHz toys, IR TVs/audio/appliances,
and BLE lights/toys — all at once.

The Flipper is the trigger and the Sub-GHz/IR radio. The ESP32 is a BLE co-processor
that the Flipper commands over UART (the Flipper cannot act as a BLE central on its own).

> **Language note:** this doc is in English on purpose so any future agent can pick it
> up. Intent/《почему》 notes from the owner are inline where they matter.

---

## 1. What it does (user-facing)

Two independent deliverables that can be used separately or together:

### A. `SEXTOY_ALL` — Sub-GHz "universal toy remote" (Flipper SubRem map)
One button = fire the corresponding command to **every** sex toy in the DB at once.
Buttons: **power on/off**, **power up**, **power down**, **mode change**. Built by
merging every toy `.sub` capture found in the Sub-GHz DB + GitHub into combined
433.92 MHz OOK RAW blobs, plus scoped Princeton brute-force sweeps.

### B. `justforfun` — Flipper JS app (menu), the real "one-button chaos"
A `.js` app (mJS) with a 6-item menu:
1. **Lights ON**  — turn on all reachable illumination (LED strips, lamps, signs) over IR **and** BLE (via ESP32).
2. **Lights OFF** — kill all reachable light.
3. **Silence**    — mute/zero-volume public venue noise: TVs (mute, *not* power-off), music, vacuums.
4. **Chaos**      — everything at once: Sub-GHz toy brute + IR power/volume-up + kitchen/appliance IR + BLE blast (lights + toys). *"Хочу хаос с одной кнопки."*
5. **Toys: all + brute** — Sub-GHz toy blobs + Princeton brute sweeps + BLE toys.
6. **Exit**

IR is sent **most-likely-first** so the operator can abort early once the room reacts.

---

## 2. Architecture

```
   ┌─────────────┐   Sub-GHz 433.92 (CC1101)   ┌──────────────┐
   │             │────────────────────────────▶│  toys / RF   │
   │  Flipper    │   IR (internal + omni hat)  ┌──────────────┐
   │  Zero       │────────────────────────────▶│ TVs/audio/…  │
   │ (Unleashed) │                             └──────────────┘
   │             │   UART 115200  (pin13/14)    ┌──────────────┐
   │  justforfun │────────────────────────────▶│  ESP32       │──BLE──▶ lights + toys
   └─────────────┘   "C","L1","L0","T","S"      │  ble_blaster │
                                                └──────────────┘
```

- **Flipper → ESP32 UART:** the JS app opens `serial.setup("usart", 115200)` and writes a
  1–2 char command + `\n`. Wiring: **Flipper pin 13 (TX) → ESP32 GPIO16 (RX2)**,
  **ESP32 GPIO17 (TX2) → Flipper pin 14 (RX)**, **common GND**. Both sides 3.3 V, direct.
- **Commands:** `C`=chaos, `L1`=lights on, `L0`=lights off, `T`=toys, `S`=silence.
- **ESP32 firmware** (`firmware/esp32-ble-blaster`): on a command it BLE-scans for a few
  seconds, matches known device profiles by service-UUID or advertised name, then connects
  to each and writes the on/off/boost payload. Memory-safe by construction (fixed target
  array, `deleteClient()` after every device — no heap growth). *"Никаких вылетов по памяти."*

### Supported BLE profiles (in firmware `PROFILES[]`)
| Profile        | Match             | Service / Char (write)                         | Type  |
|----------------|-------------------|------------------------------------------------|-------|
| ELK-BLEDOM / LED-BLE | svc `0000fff0` | char `0000fff3`                          | light |
| Triones / HappyLight | svc `ffd5`/`ffd0` | char `0000ffd9`                        | light |
| Lovense        | svc `5a300001-…`  | char `5a300002-…` (`Vibrate:20;` etc.)         | toy   |

---

## 3. Status — what's DONE vs. OPEN

### ✅ Done & verified on hardware
- **`SEXTOY_ALL` SubRem map + all `.sub` blobs** — installed on the Flipper, confirmed
  working (external CC1101 transmits; owner confirmed via photo). Files in
  `flipper/subghz/Sextoy_ALL/` and `flipper/subghz_remote/SEXTOY_ALL.txt`.
- **`justforfun.js`** — regenerated **memory-safe** (12.2 KB, 192 IR codes = top-24 of 8
  functions; Sub-GHz brute streamed via `transmitFile`, never held in RAM). JS syntax OK.
- **ESP32 firmware source** — complete, NimBLE 1.4.x API, memory-safe design.
- **Build toolchain root-caused** (see §6). The blocker was NOT code — it was a Windows
  environment issue that ate weeks of build failures.

### 🔶 Open / not yet verified
- **ESP32 firmware final link + flash.** The framework now compiles (the hard part), and
  the last two NimBLE API bugs are fixed in source:
  - `setConnectTimeout(4)` — arg is **seconds** (was `4000`, overflowed uint8_t → 160).
  - `setAdvertisedDeviceCallbacks(&cb, false)` — 1.4.x takes **2** args (was 3).
  A clean incremental rebuild + `firmware.bin` + flash to the ESP32 (COM9, CP210x) was
  **not yet run** — do this first (see §5).
- **End-to-end chain test:** Flipper "Chaos" → UART → ESP32 BLE, concurrent with Sub-GHz
  brute + IR. Never driven end-to-end yet.
- **`justforfun.js` not yet copied onto the Flipper's SD** in this latest memory-safe form
  (Flipper was disconnected during the last session; only the ESP32 was on USB).

---

## 4. Repo layout

```
firmware/esp32-ble-blaster/    PlatformIO project (ESP32-WROOM, NimBLE)
  platformio.ini               ← see §6 for the Windows path overrides
  src/main.cpp                 UART listener → BLE scan/connect/write
flipper/
  apps/justforfun.js           the mJS menu app (copy to SD:/apps/Scripts/)
  subghz/Sextoy_ALL/*.sub      combined toy blobs + Princeton brute sweeps
  subghz_remote/SEXTOY_ALL.txt SubRem map (copy to SD:/subghz_remote/)
tools/                         Python generators + Flipper CLI helpers
  gen_justforfun.py            regenerate justforfun.js from template + IR tables
  justforfun.template.js       template the generator fills
  ir_tables.json               distilled IR codes (from Unleashed tv.ir/audio.ir)
  gen_toys_brute.py            build the Princeton TOYS_BRUTE_*.sub sweeps
  subtool.py / build.py        .sub encoders (Princeton / BinRAW / RAW) + combiner
  ir_extract.py                pull codes out of firmware .ir libraries
  verify.py / analyze.py       decode/verify generated .sub files
  fz.py / push_to_flipper.py   Flipper CLI serial helpers (upload files, run apps)
  install_all.py               push the whole Sextoy set to the Flipper
```

---

## 5. How to build, flash, wire, test (do this next)

### 5.1 Build + flash the ESP32
```bash
cd firmware/esp32-ble-blaster
python -m platformio run -e esp32dev                       # build → C:/bb/build/esp32dev/firmware.bin
python -m platformio run -e esp32dev -t upload --upload-port COM9   # flash (ESP32 = CP210x on COM9; WLED can be wiped)
python -m platformio device monitor -p COM9 -b 115200      # watch "BLE blaster ready…" + heap log
```
Expected boot log: `BLE blaster ready. Waiting for UART command (C/L1/L0/T/S).` and a
`free heap at boot:` line. The onboard LED (GPIO2) lights during a blast. The BOOT button
(GPIO0) triggers a chaos blast for standalone testing without the Flipper.

### 5.2 Wire Flipper ↔ ESP32 (UART)
| Flipper (GPIO header) | ESP32       | note        |
|-----------------------|-------------|-------------|
| pin 13  TX (PB6)      | GPIO16 (RX2)| data →      |
| pin 14  RX (PB7)      | GPIO17 (TX2)| ← data      |
| pin 8/11/18 GND       | GND         | common GND  |
Both 3.3 V logic — no level shifter. **Do not** cross-power the two 5 V rails.

### 5.3 Install the Flipper app + assets
Copy to the Flipper SD (via qFlipper, or `tools/fz.py` / `tools/install_all.py`):
- `flipper/apps/justforfun.js`        → `SD:/apps/Scripts/justforfun.js`
- `flipper/subghz/Sextoy_ALL/*`       → `SD:/subghz/Sextoy_ALL/`
- `flipper/subghz_remote/SEXTOY_ALL.txt` → `SD:/subghz_remote/`
Run: Apps → Scripts → `justforfun`. Pick **Chaos**.

### 5.4 End-to-end test
With ESP32 wired + a known BLE light (ELK-BLEDOM strip) and a toy nearby: press **Chaos**,
confirm the Sub-GHz brute fires, IR blasts, and the ESP32 serial monitor prints
`== BLAST mode=C …==` → `found <profile>` → `ON <label> -> sent`. Watch the heap stays flat.

---

## 6. Known gotchas (the hard-won ones)

### ⚠️ Cyrillic Windows username breaks the ESP32 toolchain — THE big one
This machine's home dir is `C:\Users\й\…` (Cyrillic `й`). The xtensa MinGW gcc **mangles
the non-ASCII character** in include paths to `?`, so every framework header
(`Arduino.h`, `sdkconfig.h`, NimBLE) reports *"No such file"* even though it exists. This
caused ~every build failure for weeks and is invisible unless you read the verbose compile
line (`-IC:/Users/�/.platformio/...`).
**Fix (already applied in `platformio.ini`):** force all PlatformIO dirs onto ASCII paths:
```ini
[platformio]
core_dir    = C:/pio       ; packages/platforms/framework — was the fatal one
build_dir   = C:/bb/build
libdeps_dir = C:/bb/libdeps
```
On a machine with an ASCII username these overrides are unnecessary (but harmless — adjust
or drop them). `platform = espressif32@6.9.0` is pinned so the Arduino core is 2.0.17,
which matches NimBLE **1.4.x** (do not bump NimBLE to 2.x without updating the scan-callback
API in `main.cpp`).

### ⚠️ Windows MAX_PATH (260)
NimBLE has deeply-nested sources; unpacking under the long scratchpad path fails with
`[WinError 206]`. The short `C:/bb` / `C:/pio` dirs above also solve this.

### mJS heap is tiny
Keep `justforfun.js` lean: no giant array literals. IR is capped to top-24/function (192
total); Sub-GHz brute is **streamed** from file via `subghz.transmitFile()`, never arrayed.
If you add data, regenerate via `tools/gen_justforfun.py` and keep `IR_TOP` small.

---

## 7. Planned next — migrate ESP32-WROOM → **Seeed XIAO ESP32-C6**

**Owner's goal:** move off the WROOM to a **XIAO ESP32-C6** to capture **Zigbee, Thread and
other IoT radio protocols** in addition to BLE — a much wider "one-button" reach, in a
tiny solder-friendly footprint for the Flipper hat.

Why C6 specifically:
- ESP32-**C6** (and -H2) carry an **802.15.4** radio → **Zigbee** + **Thread/Matter**,
  *plus* BLE 5.0 and Wi-Fi 6. This is the only ESP32 line that adds 802.15.4.
- (Note: "ESP32-C5" is dual-band Wi-Fi and has **no** 802.15.4 — C6 is the one you want for
  Zigbee. If a XIAO C5 is what's on hand, it still does BLE/Wi-Fi but not Zigbee/Thread.)
- XIAO form factor: ~21×17 mm, castellated, easy to solder onto the hat next to the CC1101.

### Migration checklist for the next agent
1. **PlatformIO board:** `seeed_xiao_esp32c6` (or `esp32-c6-devkitc-1`). C6 needs a **newer
   Arduino core (3.x / ESP-IDF 5.x)** → bump `platform = espressif32` to a 5x/54.x release.
   **This breaks NimBLE 1.4.x** → move to **NimBLE-Arduino 2.x** and update the scan
   callback API in `main.cpp` (2.x uses `NimBLEScanCallbacks::onResult(const NimBLEAdvertisedDevice*)`
   and `setScanCallbacks(...)`, not `setAdvertisedDeviceCallbacks`). Re-verify the two
   fixes noted in §3 against the 2.x signatures.
2. **UART pins differ** on XIAO C6 — remap `PIN_U2_RX`/`PIN_U2_TX` to free XIAO GPIOs
   (the C6 has fewer pins; pick two not used by the 802.15.4/antenna). Keep 115200.
3. **Add a Zigbee path:** use Espressif's `esp-zigbee-sdk` (Zigbee coordinator/router).
   Simplest high-impact target = Zigbee **On/Off** + **Level Control** clusters broadcast to
   lights/plugs, mirroring the BLE "lights on/off" behavior. Add commands, e.g. `Z1`/`Z0`,
   and fold them into `C` (chaos). Thread/Matter is a bigger lift — stage it after Zigbee.
4. **Keep the memory discipline:** 802.15.4 + BLE coexistence eats RAM on the single-core
   C6. Don't run BLE scan and a Zigbee network scan simultaneously; sequence them inside a
   blast. Log free heap around each phase like the current firmware does.
5. **Sub-GHz proprietary IoT** (433/868/915 non-Flipper) stays on the CC1101 / Flipper, or
   add a CC1352 later — the C6 does **not** do sub-GHz OOK.
6. **Hat/power unchanged** — see `HARDWARE` below; the XIAO just replaces the WROOM in the
   UART + power slot (XIAO runs from the same 3.3 V / 5 V-VIN rail).

---

## 8. Hardware — the Flipper GPIO hat

One GPIO hat carrying three radios + power (no pin conflicts):
- **CC1101** (Sub-GHz): SPI cluster PA7/PA6/PA4/PB3 + GDO0 + 3V3 + GND. Already auto-detected
  as external. Powered by the Flipper's own 3V3.
- **ESP32 (→ XIAO C6) UART:** Flipper pin13→RX, TX→Flipper pin14, common GND (see §5.2).
- **Omni IR blaster:** *optical pickup* — a BPW34 photodiode sees the Flipper's own internal
  IR LED and drives an IRLZ44N + a 6× 940 nm LED ring. Needs **no** Flipper GPIO, only
  power + GND. Parts: BPW34, LM393 (DIP), IRLZ44N, 3296W 10k trimmer, IR-5238C 940 nm ×6,
  22 Ω 0.5 W ×3, 100 nF. Gotcha: shield the photodiode from the ring (feedback).
- **Power:** 1–2× 18650 + protection/BMS + boost to 5 V (a TP4056+boost bank board covers
  charge+protect+5 V). Battery powers **only** the ESP32 + IR LEDs. Never feed battery 5 V
  into the Flipper's 5 V pin — share **GND only**. Do not put 4.2 V on the ESP32 3V3 pin
  (max 3.6 V) — feed 5V/VIN through the onboard LDO.

---

## 9. Legal / scope
Authorized security-research / personal-hardware experimentation on the owner's own devices
and in the owner's own space. Don't point it at other people's property.
