// BLE blaster for ESP32-WROOM, triggered over UART by a Flipper Zero.
//
// Wiring to the Flipper (both 3.3 V logic, direct - no level shifter):
//   Flipper pin 13 (TX / USART TX) --> ESP32 GPIO16 (U2 RX)
//   Flipper pin 14 (RX / USART RX) <-- ESP32 GPIO17 (U2 TX)
//   Flipper GND (pin 8/11/18)      --- ESP32 GND
// USB (UART0) stays free for flashing and log output.
//
// Commands from the Flipper (newline-terminated ASCII on UART2):
//   C   chaos   : every light ON + max brightness, every toy to max
//   L1  lights  : every light ON + max
//   L0  off     : every light OFF
//   T   toys    : every toy to max
//   S   silence : every light OFF + every toy to 0
// The onboard BOOT button (GPIO0) also fires "chaos" for standalone testing.
//
// Memory safety: candidates are collected into a fixed-size array (no dynamic
// growth), every NimBLEClient is deleted right after use, and all command bytes
// live in flash (const). Nothing accumulates across blasts.

#include <Arduino.h>
#include <NimBLEDevice.h>

static const uint32_t FLIPPER_BAUD = 115200;
static const int PIN_U2_RX = 16;   // <- Flipper TX (pin 13)
static const int PIN_U2_TX = 17;   // -> Flipper RX (pin 14)
static const int PIN_BOOT = 0;
static const int PIN_LED = 2;      // onboard LED on most WROOM devkits

static const int SCAN_SECONDS = 6;
static const int MAX_TARGETS = 40; // cap; extras are logged and skipped

// ---- command payloads (in flash) ------------------------------------------
// ELK-BLEDOM / LED-BLE strips: write to char 0xFFF3
static const uint8_t ELK_ON[]  = {0x7e,0x00,0x04,0xf0,0x00,0x01,0xff,0x00,0xef};
static const uint8_t ELK_BRI[] = {0x7e,0x00,0x01,0x64,0x00,0x00,0x00,0x00,0xef}; // 100%
static const uint8_t ELK_WHT[] = {0x7e,0x00,0x05,0x03,0xff,0xff,0xff,0x00,0xef};
static const uint8_t ELK_OFF[] = {0x7e,0x00,0x04,0x00,0x00,0x00,0xff,0x00,0xef};
// Triones / "Happy Lighting" strips: write to char 0xFFD9
static const uint8_t TRI_ON[]  = {0xcc,0x23,0x33};
static const uint8_t TRI_WHT[] = {0x56,0xff,0xff,0xff,0x00,0xf0,0xaa};
static const uint8_t TRI_OFF[] = {0xcc,0x24,0x33};
// Lovense toys: ASCII commands to the control characteristic
static const uint8_t LVS_ON[]  = {'V','i','b','r','a','t','e',':','2','0',';'};
static const uint8_t LVS_OFF[] = {'V','i','b','r','a','t','e',':','0',';'};

struct Cmd { const uint8_t* data; uint8_t len; };
#define C1(a)          {a, (uint8_t)sizeof(a)}

struct Profile {
    const char* label;
    const char* nameHint;   // adv-name substring, or nullptr
    const char* svc;        // service UUID
    const char* chr;        // characteristic UUID to write
    bool withResponse;
    bool isToy;
    Cmd on[3];  uint8_t onN;
    Cmd off[2]; uint8_t offN;
};

static const Profile PROFILES[] = {
    { "ELK-BLEDOM", "ELK", "0000fff0-0000-1000-8000-00805f9b34fb",
      "0000fff3-0000-1000-8000-00805f9b34fb", false, false,
      { C1(ELK_ON), C1(ELK_BRI), C1(ELK_WHT) }, 3,
      { C1(ELK_OFF) }, 1 },
    { "LED-BLE", "LEDBLE", "0000fff0-0000-1000-8000-00805f9b34fb",
      "0000fff3-0000-1000-8000-00805f9b34fb", false, false,
      { C1(ELK_ON), C1(ELK_BRI), C1(ELK_WHT) }, 3,
      { C1(ELK_OFF) }, 1 },
    { "Triones", "Triones", "0000ffd5-0000-1000-8000-00805f9b34fb",
      "0000ffd9-0000-1000-8000-00805f9b34fb", false, false,
      { C1(TRI_ON), C1(TRI_WHT), {nullptr,0} }, 2,
      { C1(TRI_OFF) }, 1 },
    { "HappyLight", "LEDnet", "0000ffd0-0000-1000-8000-00805f9b34fb",
      "0000ffd9-0000-1000-8000-00805f9b34fb", false, false,
      { C1(TRI_ON), C1(TRI_WHT), {nullptr,0} }, 2,
      { C1(TRI_OFF) }, 1 },
    { "Lovense", "LVS", "5a300001-0024-4bd4-bbd5-a6920e4c5653",
      "5a300002-0024-4bd4-bbd5-a6920e4c5653", true, true,
      { C1(LVS_ON), {nullptr,0}, {nullptr,0} }, 1,
      { C1(LVS_OFF) }, 1 },
};
static const int N_PROFILES = sizeof(PROFILES) / sizeof(PROFILES[0]);

// ---- collected scan targets (fixed storage) --------------------------------
struct Target { NimBLEAddress addr; int8_t profile; };
static Target targets[MAX_TARGETS];
static int nTargets = 0;

static void led(bool on) { digitalWrite(PIN_LED, on ? HIGH : LOW); }

static int matchProfile(NimBLEAdvertisedDevice* d) {
    for (int i = 0; i < N_PROFILES; i++) {
        // service-UUID match (strongest)
        if (d->haveServiceUUID() &&
            d->isAdvertisingService(NimBLEUUID(PROFILES[i].svc))) {
            return i;
        }
    }
    if (d->haveName()) {
        std::string n = d->getName();
        for (int i = 0; i < N_PROFILES; i++) {
            const char* h = PROFILES[i].nameHint;
            if (h && n.find(h) != std::string::npos) return i;
        }
    }
    return -1;
}

class ScanCB : public NimBLEAdvertisedDeviceCallbacks {
    void onResult(NimBLEAdvertisedDevice* d) override {
        int p = matchProfile(d);
        if (p < 0) return;
        for (int i = 0; i < nTargets; i++)          // dedupe by address
            if (targets[i].addr == d->getAddress()) return;
        if (nTargets >= MAX_TARGETS) {
            Serial.println("  [!] target list full, skipping extras");
            return;
        }
        targets[nTargets].addr = d->getAddress();
        targets[nTargets].profile = p;
        nTargets++;
        Serial.printf("  found %s (%s)\n", PROFILES[p].label,
                      d->getAddress().toString().c_str());
    }
};

static void writeCmds(NimBLERemoteCharacteristic* c, const Cmd* cmds, uint8_t n,
                      bool withResponse) {
    for (uint8_t i = 0; i < n; i++) {
        if (!cmds[i].data || cmds[i].len == 0) continue;
        c->writeValue(cmds[i].data, cmds[i].len, withResponse);
        delay(40);
    }
}

static void hitTarget(const Target& t, bool turnOn) {
    const Profile& p = PROFILES[t.profile];
    NimBLEClient* cli = NimBLEDevice::createClient();
    cli->setConnectTimeout(4);  // NimBLE 1.4.x: argument is SECONDS (uint8_t)
    bool ok = false;
    if (cli->connect(t.addr)) {
        NimBLERemoteService* s = cli->getService(NimBLEUUID(p.svc));
        if (s) {
            NimBLERemoteCharacteristic* c = s->getCharacteristic(NimBLEUUID(p.chr));
            if (c && (c->canWrite() || c->canWriteNoResponse())) {
                writeCmds(c, turnOn ? p.on : p.off, turnOn ? p.onN : p.offN,
                          p.withResponse);
                ok = true;
            }
        }
    }
    Serial.printf("  %s %s -> %s\n", turnOn ? "ON " : "OFF", p.label,
                  ok ? "sent" : "FAILED");
    cli->disconnect();
    NimBLEDevice::deleteClient(cli);   // free immediately
}

// mode: 'C' chaos, '1' lights on, '0' lights off, 'T' toys, 'S' silence
static void blast(char mode) {
    bool wantToys = (mode == 'C' || mode == 'T' || mode == 'S');
    bool wantLights = (mode == 'C' || mode == '1' || mode == '0' || mode == 'S');
    bool turnOn = (mode == 'C' || mode == '1' || mode == 'T');

    Serial.printf("== BLAST mode=%c  scan %ds ==\n", mode, SCAN_SECONDS);
    led(true);
    nTargets = 0;
    NimBLEScan* scan = NimBLEDevice::getScan();
    scan->clearResults();
    scan->start(SCAN_SECONDS, false);   // blocking scan (seconds)
    scan->stop();

    int hits = 0;
    for (int i = 0; i < nTargets; i++) {
        const Profile& p = PROFILES[targets[i].profile];
        if (p.isToy && !wantToys) continue;
        if (!p.isToy && !wantLights) continue;
        hitTarget(targets[i], turnOn);
        hits++;
    }
    Serial.printf("== done: %d matched, %d actioned, heap=%u ==\n",
                  nTargets, hits, ESP.getFreeHeap());
    led(false);
}

// ---- UART command parsing --------------------------------------------------
static char lineBuf[16];
static uint8_t lineLen = 0;

static void handleLine(const char* s) {
    if (s[0] == 'C') blast('C');
    else if (s[0] == 'T') blast('T');
    else if (s[0] == 'S') blast('S');
    else if (s[0] == 'L' && s[1] == '1') blast('1');
    else if (s[0] == 'L' && s[1] == '0') blast('0');
    else Serial.printf("? unknown cmd '%s'\n", s);
}

void setup() {
    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_BOOT, INPUT_PULLUP);
    Serial.begin(115200);                                  // USB log
    Serial2.begin(FLIPPER_BAUD, SERIAL_8N1, PIN_U2_RX, PIN_U2_TX);
    delay(200);
    Serial.println("\nBLE blaster ready. Waiting for UART command (C/L1/L0/T/S).");
    NimBLEDevice::init("");
    NimBLEDevice::setPower(ESP_PWR_LVL_P9);                // max TX power
    NimBLEScan* scan = NimBLEDevice::getScan();
    static ScanCB cb;
    scan->setAdvertisedDeviceCallbacks(&cb, false);  // NimBLE 1.4.x: (cb, wantDuplicates)
    scan->setActiveScan(true);
    scan->setInterval(100);
    scan->setWindow(90);
    Serial.printf("free heap at boot: %u\n", ESP.getFreeHeap());
}

void loop() {
    while (Serial2.available()) {
        char c = (char)Serial2.read();
        if (c == '\n' || c == '\r') {
            if (lineLen > 0) { lineBuf[lineLen] = 0; handleLine(lineBuf); lineLen = 0; }
        } else if (lineLen < sizeof(lineBuf) - 1) {
            lineBuf[lineLen++] = c;
        }
    }
    // also accept commands typed into the USB serial monitor, for bench testing
    while (Serial.available()) {
        char c = (char)Serial.read();
        if (c == '\n' || c == '\r') {
            if (lineLen > 0) { lineBuf[lineLen] = 0; handleLine(lineBuf); lineLen = 0; }
        } else if (lineLen < sizeof(lineBuf) - 1) {
            lineBuf[lineLen++] = c;
        }
    }
    if (digitalRead(PIN_BOOT) == LOW) {   // BOOT button = chaos
        delay(30);
        if (digitalRead(PIN_BOOT) == LOW) { blast('C'); while (digitalRead(PIN_BOOT) == LOW) delay(10); }
    }
    delay(5);
}
