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
let LIGHTS_ON = [
    "/ext/subghz/Govee-LED_LightStrand/On.sub",
    "/ext/subghz/LED/Govee_LED_String/On.sub",
    "/ext/subghz/LED/Commercial_Electric_White_LED_Tape/On.sub",
    "/ext/subghz/LED/EverFlourish_LEDs/On.sub",
    "/ext/subghz/LED/RF_LED_Controller_T917/On.sub",
    "/ext/subghz/LED/LEDGLOW_Motorcycle_Lights/On.sub",
    "/ext/subghz/LED/SUPERNIGHT_RGBW_LED/On.sub",
    "/ext/subghz/LED/Aurora_RGB/Power.sub",
    "/ext/subghz/LED/JOOFO_Floor_Lamp/Power.sub",
    "/ext/subghz/LED/RGB_LED_Lamp/power.sub",
    "/ext/subghz/LED/RITSEC_Neon_Light/Pwr.sub",
    "/ext/subghz/LED/Speclux_LED_Strip/POWER.sub",
    "/ext/subghz/Remote_Outlet_Switches/Defiant_Outlet/On_1.sub",
    "/ext/subghz/Remote_Outlet_Switches/First_Alert-FA200/On.sub",
    "/ext/subghz/Remote_Outlet_Switches/MasterElectrician_TR-026A/On.sub",
    "/ext/subghz/Remote_Outlet_Switches/Woods_Remote_Outlet/On.sub",
    "/ext/subghz/Cooker_Hoods/Elica/light_on.sub"
  ];
let LIGHTS_OFF = [
    "/ext/subghz/Govee-LED_LightStrand/Off.sub",
    "/ext/subghz/LED/Govee_LED_String/Off.sub",
    "/ext/subghz/LED/Commercial_Electric_White_LED_Tape/Off.sub",
    "/ext/subghz/LED/EverFlourish_LEDs/Off.sub",
    "/ext/subghz/LED/RF_LED_Controller_T917/Off.sub",
    "/ext/subghz/LED/LEDGLOW_Motorcycle_Lights/Off.sub",
    "/ext/subghz/LED/SUPERNIGHT_RGBW_LED/Off.sub",
    "/ext/subghz/Remote_Outlet_Switches/Defiant_Outlet/Off_1.sub",
    "/ext/subghz/Remote_Outlet_Switches/First_Alert-FA200/Off.sub",
    "/ext/subghz/Remote_Outlet_Switches/MasterElectrician_TR-026A/Off.sub",
    "/ext/subghz/Remote_Outlet_Switches/Woods_Remote_Outlet/Off.sub",
    "/ext/subghz/Cooker_Hoods/Elica/light_off.sub",
    "/ext/subghz/LED/Aurora_RGB/Power.sub",
    "/ext/subghz/LED/JOOFO_Floor_Lamp/Power.sub",
    "/ext/subghz/LED/RGB_LED_Lamp/power.sub",
    "/ext/subghz/LED/RITSEC_Neon_Light/Pwr.sub",
    "/ext/subghz/LED/Speclux_LED_Strip/POWER.sub"
  ];
let NOISE_OFF_SUB = [
    "/ext/subghz/Cooker_Hoods/Elica/fan_off.sub",
    "/ext/subghz/Air_Filtration/WEN_3410_Air_Filter/Off.sub",
    "/ext/subghz/Vacuum/Samsung/On_Off_Samsung_VC06H70F0HD.sub",
    "/ext/subghz/Fans/Flowmate Classic/Power.sub",
    "/ext/subghz/Ceiling_Fans/Hampton_Bay_Ceiling_Fan_2/Off.sub",
    "/ext/subghz/Ceiling_Fans/Sofucor_Fan_KBS-56K001/power_off.sub"
  ];
let NOISE_ON_SUB = [
    "/ext/subghz/Vacuum/Samsung/On_Samsung_SC20F70HB.sub",
    "/ext/subghz/Vacuum/Samsung/Stronger_Samsung_VC06H70F0HD.sub",
    "/ext/subghz/Cooker_Hoods/Elica/fan_plus.sub",
    "/ext/subghz/Air_Filtration/WEN_3410_Air_Filter/On_speed.sub",
    "/ext/subghz/Fans/Flowmate Classic/Power.sub",
    "/ext/subghz/Fans/Flowmate Classic/Speed.sub",
    "/ext/subghz/Ceiling_Fans/Hampton_Bay_Ceiling_Fan_2/High.sub"
  ];
let TOYS_SUB = [
    "/ext/subghz/Sextoy_ALL/ALL_PWR.sub",
    "/ext/subghz/Sextoy_ALL/TOYS_BRUTE_8B02.sub",
    "/ext/subghz/Sextoy_ALL/TOYS_BRUTE_00FF.sub",
    "/ext/subghz/Sextoy_ALL/TOYS_BRUTE_AA55.sub"
  ];   // known toys first, then scoped brute sweeps
let TV_POWER = [["Samsung32",7,2],["Samsung32",7,230],["Samsung32",7,224],["Samsung32",7,152],["NEC",4,64],["NEC",4,8],["SIRC",1,21],["SIRC",1,109],["SIRC",1,46],["SIRC",1,47],["Kaseikyo",2097792,976],["Kaseikyo",2097808,976],["RC6",0,12],["RC5",0,12],["RC5",0,32],["RC5",0,38],["NEC",0,1],["NEC",0,81],["NEC",0,26],["NEC",0,11],["RCA",15,84],["NEC",64,11],["NECext",32512,59925],["NECext",64256,62730]];
let TV_MUTE = [["Samsung32",7,15],["NEC",4,18],["NEC",4,9],["SIRC",1,20],["Kaseikyo",2097792,800],["RC6",0,13],["RC5",0,13],["RCA",15,252],["NEC",64,20],["NECext",32512,59670],["NECext",64256,61455],["NECext",57088,63240],["NECext",32512,45390],["NEC",25,86],["NECext",41146,65025],["NEC",8,11],["NECext",57088,8],["Samsung32",14,13],["NECext",29185,41820],["NECext",1414,61710],["NECext",32002,45900],["NECext",57476,39780],["NEC",110,4],["NEC",80,11]];
let TV_VOL_DN = [["Samsung32",7,11],["NEC",4,3],["SIRC",1,19],["SIRC",1,115],["Kaseikyo",2097792,528],["RC6",0,17],["RC5",0,17],["RC5",0,20],["NEC",0,51],["RCA",15,116],["NECext",32512,58650],["NECext",64256,46155],["NECext",57088,45135],["NEC",3,21],["NEC",25,13],["NEC",8,1],["NECext",57088,79],["Samsung32",14,21],["NEC",64,18],["NECext",29185,63750],["NECext",1414,61965],["NECext",32002,58905],["NECext",32002,48450],["NECext",57476,40545]];
let TV_VOL_UP = [["Samsung32",7,7],["NEC",4,2],["SIRC",1,18],["SIRC",1,114],["Kaseikyo",2097792,512],["RC6",0,16],["RC5",0,16],["RC5",0,21],["NEC",0,17],["RCA",15,244],["NEC",64,19],["NECext",32512,58395],["NECext",64256,42840],["NECext",57088,46155],["NEC",3,17],["NEC",25,79],["NEC",8,0],["NECext",57088,75],["Samsung32",14,20],["NECext",29185,62730],["NECext",1414,62220],["NECext",32002,62220],["NECext",32002,59925],["NECext",57476,40800]];
let AUDIO_POWER = [["NEC",4,22],["NEC",4,8],["SIRC",1,21],["Kaseikyo",2097836,977],["Kaseikyo",2097824,976],["Kaseikyo",20075601,3],["Kaseikyo",3298386,131],["Kaseikyo",3298369,5],["Kaseikyo",2097792,976],["NEC",0,64],["NEC",0,28],["NEC",0,18],["NEC",0,7],["NEC",0,2],["NEC",0,4],["NEC",0,70],["NEC",0,69],["NEC",0,85],["NEC",0,0],["NEC",0,72],["NEC",0,12],["NEC",0,24],["NEC",119,241],["NEC",128,26]];
let AUDIO_MUTE = [["NEC",4,6],["NEC",4,9],["SIRC",1,20],["Kaseikyo",2097824,800],["Kaseikyo",20075601,6],["Kaseikyo",3298386,134],["Kaseikyo",3298369,370],["RC5",0,13],["NEC",0,72],["NEC",0,11],["NEC",0,30],["NEC",0,0],["NEC",0,68],["NEC",0,71],["NEC",0,1],["NEC",0,69],["NEC",0,29],["NEC",0,85],["NEC",0,9],["NEC",119,243],["NECext",59152,48705],["RC5",16,13],["NECext",54061,60435],["SIRC15",68,20]];
let AUDIO_VOL_DN = [["NEC",4,11],["NEC",4,3],["SIRC",1,19],["Kaseikyo",2097824,528],["Kaseikyo",20075601,5],["Kaseikyo",3298386,133],["Kaseikyo",3298369,369],["NEC",0,69],["NEC",0,5],["NEC",0,1],["NEC",0,9],["NEC",0,6],["NEC",0,8],["NEC",0,21],["NEC",0,22],["NEC",0,14],["NEC",0,12],["NEC",0,30],["NEC",0,3],["NEC",0,17],["NEC",0,67],["NEC",0,7],["NEC",0,133],["NEC",119,252]];
let AUDIO_VOL_UP = [["NEC",4,19],["NEC",4,2],["SIRC",1,18],["Kaseikyo",2097824,512],["Kaseikyo",20075601,4],["Kaseikyo",3298386,132],["Kaseikyo",3298369,368],["NEC",0,65],["NEC",0,15],["NEC",0,3],["NEC",0,31],["NEC",0,20],["NEC",0,87],["NEC",0,25],["NEC",0,10],["NEC",0,22],["NEC",0,21],["NEC",0,9],["NEC",0,66],["NEC",0,28],["NEC",0,70],["NEC",0,94],["NEC",119,251],["NECext",59152,63750]];

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
