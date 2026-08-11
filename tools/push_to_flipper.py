"""Push the universal remote onto a Flipper over its USB serial CLI.

Close qFlipper first - it holds the VCP port exclusively.
Uses `storage write_chunk`, which is binary-safe, and appends the map file to
/ext/favorites.txt (the archive's Favourites list) unless it is already there.
"""
import os
import sys
import time

import serial
from serial.tools import list_ports

REPO = r"C:\projects\FlipperZero-Subghz-DB"
BLOBS = ["ALL_PWR", "ALL_UP", "ALL_DOWN", "ALL_MODE", "ALL_OFF"]
MAP_SD = "/ext/subghz_remote/SEXTOY_ALL.txt"
PROMPT = b">: "


def find_port():
    for p in list_ports.comports():
        if p.vid == 0x0483 and p.pid == 0x5740:
            return p.device
    return None


class Flipper:
    def __init__(self, port):
        self.s = serial.Serial(port, timeout=5)
        self.s.reset_input_buffer()
        self.s.write(b"\r\n")
        self.read_to_prompt()

    def read_to_prompt(self):
        buf = b""
        while not buf.endswith(PROMPT):
            chunk = self.s.read(1)
            if not chunk:
                break
            buf += chunk
        return buf

    def cmd(self, line):
        self.s.write(line.encode() + b"\r\n")
        self.s.readline()                      # echo
        return self.read_to_prompt().decode(errors="replace")

    def mkdir(self, path):
        out = self.cmd("storage mkdir %s" % path)
        if "Error" in out and "exist" not in out.lower():
            print("   mkdir %s: %s" % (path, out.strip().splitlines()[:1]))

    def write_file(self, path, data):
        self.cmd("storage remove %s" % path)
        self.s.write(("storage write_chunk %s %d\r\n" % (path, len(data))).encode())
        self.s.readline()
        time.sleep(0.2)
        self.s.read_until(b"\n")               # "Ready" banner
        self.s.write(data)
        out = self.read_to_prompt().decode(errors="replace")
        if "Error" in out:
            raise RuntimeError("write %s failed: %s" % (path, out.strip()))

    def read_file(self, path):
        self.s.write(("storage read %s\r\n" % path).encode())
        self.s.readline()
        head = self.s.read_until(b"\n").decode(errors="replace")
        if "Size:" not in head:
            self.read_to_prompt()
            return None
        size = int(head.split("Size:")[1].strip())
        data = self.s.read(size)
        self.read_to_prompt()
        return data

    def close(self):
        self.s.close()


def main():
    port = find_port()
    if not port:
        print("Flipper not found on USB. Plug it in, unlock it, and close qFlipper.")
        return 1
    print("Flipper on", port)
    f = Flipper(port)
    try:
        f.mkdir("/ext/subghz/Sextoy_ALL")
        f.mkdir("/ext/subghz_remote")

        for name in BLOBS:
            local = os.path.join(REPO, "subghz", "Sextoy_ALL", name + ".sub")
            data = open(local, "rb").read()
            f.write_file("/ext/subghz/Sextoy_ALL/%s.sub" % name, data)
            print("   sent %-9s %6d bytes" % (name + ".sub", len(data)))

        data = open(os.path.join(REPO, "subghz_remote", "SEXTOY_ALL.txt"), "rb").read()
        f.write_file(MAP_SD, data)
        print("   sent %-9s %6d bytes" % ("SEXTOY_ALL.txt", len(data)))

        fav = f.read_file("/ext/favorites.txt") or b""
        lines = [l for l in fav.decode(errors="replace").splitlines() if l.strip()]
        if MAP_SD in lines:
            print("   already in favourites")
        else:
            lines.append(MAP_SD)
            f.write_file("/ext/favorites.txt", ("\n".join(lines) + "\n").encode())
            print("   added to favourites (%d entries)" % len(lines))
    finally:
        f.close()
    print("\nDone. Reboot the Flipper so the archive re-reads favourites.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
