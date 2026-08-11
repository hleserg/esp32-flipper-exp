"""Minimal Flipper CLI helper over the USB VCP. Reusable from other scripts."""
import sys
import time
import serial
from serial.tools import list_ports

PROMPT = b">: "


def find_port():
    for p in list_ports.comports():
        if p.vid == 0x0483 and p.pid == 0x5740:
            return p.device
    return None


class Flipper:
    def __init__(self, port=None, timeout=6):
        port = port or find_port()
        if not port:
            raise RuntimeError("Flipper not found on USB (is qFlipper open? close it)")
        self.port = port
        self.s = serial.Serial(port, timeout=timeout)
        self.s.reset_input_buffer()
        self.s.write(b"\r\n")
        self._read_to_prompt()

    def _read_to_prompt(self):
        buf = b""
        while not buf.endswith(PROMPT):
            c = self.s.read(1)
            if not c:
                break
            buf += c
        return buf

    def cmd(self, line, settle=0.0):
        self.s.reset_input_buffer()
        self.s.write(line.encode() + b"\r\n")
        self.s.readline()                      # echoed command
        if settle:
            time.sleep(settle)
        out = self._read_to_prompt()
        return out[:-len(PROMPT)].decode(errors="replace").strip("\r\n")

    def mkdir(self, path):
        return self.cmd("storage mkdir %s" % path)

    def remove(self, path):
        return self.cmd("storage remove %s" % path)

    def write_file(self, path, data):
        if isinstance(data, str):
            data = data.encode()
        self.cmd("storage remove %s" % path)
        self.s.reset_input_buffer()
        self.s.write(("storage write_chunk %s %d\r\n" % (path, len(data))).encode())
        self.s.readline()
        # firmware prints "Ready?..." then waits; give it a beat
        time.sleep(0.3)
        self.s.reset_input_buffer()
        self.s.write(data)
        out = self._read_to_prompt().decode(errors="replace")
        if "Error" in out or "error" in out:
            raise RuntimeError("write %s failed: %s" % (path, out.strip()))
        return True

    def read_file(self, path):
        self.s.reset_input_buffer()
        self.s.write(("storage read %s\r\n" % path).encode())
        self.s.readline()
        head = b""
        while not head.endswith(b"\n"):
            c = self.s.read(1)
            if not c:
                break
            head += c
        head = head.decode(errors="replace")
        if "Size:" not in head:
            self._read_to_prompt()
            return None
        size = int(head.split("Size:")[1].strip())
        data = self.s.read(size)
        self._read_to_prompt()
        return data

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


if __name__ == "__main__":
    f = Flipper()
    print("port:", f.port)
    print(f.cmd("device_info | grep -i firmware") if False else f.cmd("!"))
    print("--- Scripts dir ---")
    print(f.cmd("storage list /ext/apps/Scripts"))
    print("--- subghz_remote dir ---")
    print(f.cmd("storage list /ext/subghz_remote"))
    f.close()
