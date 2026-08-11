// justforfun - one-tap "fire everything" remote for Flipper Zero (Unleashed, mjs).
//
// Four actions, each a single menu tap:
//   Lights ON   - every light/sign/outlet ON or toggle we have (Sub-GHz)
//   Lights OFF  - every light OFF, plus toggles (a lit venue toggles dark)
//   Silence     - noisy appliances OFF (Sub-GHz) + mute & volume-down every TV
//                 and audio system (IR), most common brands first
//   Chaos       - noisy appliances ON/MAX (Sub-GHz) + power-on and ramp volume
//                 up on every TV/audio (IR); each tap bumps volume further
//
// Sub-GHz files are sent straight from the SD card, so each carries its own
// frequency/preset - one action freely spans 315 / 433 / 303 MHz. Plug the
// external CC1101 in before launching for range; the internal radio is the
// fallback. IR uses the built-in blaster (see README for an omni hat).
//
// Long-press BACK aborts a running blast. Generated file - edit the lists in
// gen_justforfun.py, not here.

let eventLoop = require("event_loop");
let gui = require("gui");
let submenuView = require("gui/submenu");
let loadingView = require("gui/loading");
let subghz = require("subghz");
let infrared = require("infrared");

// UART link to an external ESP32 BLE blaster (Flipper pin 13 TX / 14 RX).
// Optional: if nothing is wired, setup still succeeds and writes go nowhere.
let SER_OK = false;
try {
    let serial = require("serial");
    serial.setup("usart", 115200);
    SER_OK = true;
    var SER = serial;
} catch (e) {
    SER_OK = false;
}
function trig(cmd) {          // fire-and-forget trigger to the ESP32
    if (SER_OK) {
        try { SER.write(cmd + "\n"); } catch (e) { }
    }
}

let SUB_DELAY = 150;   // ms between Sub-GHz transmissions
let IR_DELAY = 15;     // ms between IR codes
let VOL_STEPS = 6;     // IR volume presses per code (~one "bump")
let VOL_ZERO = 16;     // IR volume-down presses to floor the volume

// ---- data (injected by generator) -----------------------------------------
let LIGHTS_ON = /*{LIGHTS_ON}*/;
let LIGHTS_OFF = /*{LIGHTS_OFF}*/;
let NOISE_OFF_SUB = /*{NOISE_OFF_SUB}*/;
let NOISE_ON_SUB = /*{NOISE_ON_SUB}*/;
let TOYS_SUB = /*{TOYS_SUB}*/;   // known toys first, then scoped brute sweeps
let TV_POWER = /*{TV_POWER}*/;
let TV_MUTE = /*{TV_MUTE}*/;
let TV_VOL_DN = /*{TV_VOL_DN}*/;
let TV_VOL_UP = /*{TV_VOL_UP}*/;
let AUDIO_POWER = /*{AUDIO_POWER}*/;
let AUDIO_MUTE = /*{AUDIO_MUTE}*/;
let AUDIO_VOL_DN = /*{AUDIO_VOL_DN}*/;
let AUDIO_VOL_UP = /*{AUDIO_VOL_UP}*/;

// ---- helpers ---------------------------------------------------------------
function sendSub(list) {
    for (let i = 0; i < list.length; i++) {
        try {
            subghz.transmitFile(list[i]);
        } catch (e) {
            // path missing on this card / bad file - skip, keep going
        }
        delay(SUB_DELAY);
    }
}

function sendIr(list, times) {
    for (let i = 0; i < list.length; i++) {
        let row = list[i];
        try {
            infrared.sendSignal(row[0], row[1], row[2], { times: times });
        } catch (e) {
        }
        delay(IR_DELAY);
    }
}

function runAction(index) {
    subghz.setup(); // (re)detect external CC1101
    if (index === 0) {                       // Lights ON
        trig("L1");                          // ESP32: BLE lights ON + max
        print("Lights ON: Sub-GHz x" + LIGHTS_ON.length);
        sendSub(LIGHTS_ON);
    } else if (index === 1) {                // Lights OFF
        trig("L0");                          // ESP32: BLE lights OFF
        print("Lights OFF: Sub-GHz x" + LIGHTS_OFF.length);
        sendSub(LIGHTS_OFF);
    } else if (index === 2) {                // Silence
        trig("S");                           // ESP32: BLE lights off + toys 0
        print("Silence: appliances OFF");
        sendSub(NOISE_OFF_SUB);
        print("Silence: mute TV+audio");
        sendIr(TV_MUTE, 1);
        sendIr(AUDIO_MUTE, 1);
        print("Silence: volume to floor");
        sendIr(TV_VOL_DN, VOL_ZERO);
        sendIr(AUDIO_VOL_DN, VOL_ZERO);
    } else if (index === 3) {                // Chaos - the everything button
        trig("C");                           // ESP32: BLE lights max + toys max
        print("Chaos: appliances ON/MAX");
        sendSub(NOISE_ON_SUB);
        print("Chaos: toy Sub-GHz brute");   // known toys + 3 scoped sweeps (~80s)
        sendSub(TOYS_SUB);
        print("Chaos: power on TV+audio");
        sendIr(AUDIO_POWER, 1);
        sendIr(TV_POWER, 1);
        print("Chaos: volume UP +" + VOL_STEPS);
        sendIr(TV_VOL_UP, VOL_STEPS);
        sendIr(AUDIO_VOL_UP, VOL_STEPS);
    } else if (index === 4) {                // Toys: known + scoped brute (~80s)
        trig("T");                           // ESP32: BLE toys max
        print("Toys: known set");
        sendSub([TOYS_SUB[0]]);              // ALL_PWR.sub - every captured toy
        for (let i = 1; i < TOYS_SUB.length; i++) {
            print("Toys: brute " + (i) + "/" + (TOYS_SUB.length - 1));
            sendSub([TOYS_SUB[i]]);          // one family sweep per file (~25s each)
        }
    }
    subghz.end();
    print("Done.");
}

// ---- UI --------------------------------------------------------------------
let views = {
    loading: loadingView.make(),
    menu: submenuView.makeWith({ header: "justforfun" }, [
        "Lights  ON",
        "Lights  OFF",
        "Silence (mute all)",
        "Chaos (max noise)",
        "Toys: all + brute",
        "Exit",
    ]),
};

eventLoop.subscribe(views.menu.chosen, function (_sub, index, gui, views, eventLoop) {
    if (index === 5) {
        eventLoop.stop();
        return;
    }
    gui.viewDispatcher.switchTo(views.loading);
    // let the loading screen paint, then run the (blocking) blast
    eventLoop.subscribe(eventLoop.timer("oneshot", 40), function (_s, _t, gui, views, index) {
        runAction(index);
        gui.viewDispatcher.switchTo(views.menu);
    }, gui, views, index);
}, gui, views, eventLoop);

eventLoop.subscribe(gui.viewDispatcher.navigation, function (_sub, _, gui, views, eventLoop) {
    if (gui.viewDispatcher.currentView === views.menu) {
        eventLoop.stop();
        return;
    }
    gui.viewDispatcher.switchTo(views.menu);
}, gui, views, eventLoop);

gui.viewDispatcher.switchTo(views.menu);
eventLoop.run();
