"""Install both remotes onto the Flipper and pin them to Favourites."""
import os
from fz import Flipper

REPO = r"C:\projects\FlipperZero-Subghz-DB"
HERE = os.path.dirname(os.path.abspath(__file__))

BLOBS = ["ALL_PWR", "ALL_UP", "ALL_DOWN", "ALL_MODE", "ALL_OFF",
         "TOYS_BRUTE_8B02", "TOYS_BRUTE_00FF", "TOYS_BRUTE_AA55"]
FAVS = ["/ext/subghz_remote/SEXTOY_ALL.txt", "/ext/apps/Scripts/justforfun.js"]


def main():
    f = Flipper()
    print("port:", f.port)
    f.mkdir("/ext/subghz/Sextoy_ALL")
    f.mkdir("/ext/subghz_remote")
    f.mkdir("/ext/apps/Scripts")

    for name in BLOBS:
        data = open(os.path.join(REPO, "subghz", "Sextoy_ALL", name + ".sub"), "rb").read()
        f.write_file("/ext/subghz/Sextoy_ALL/%s.sub" % name, data)
        print("  sent  ALL/%s.sub  %d B" % (name, len(data)))

    data = open(os.path.join(REPO, "subghz_remote", "SEXTOY_ALL.txt"), "rb").read()
    f.write_file("/ext/subghz_remote/SEXTOY_ALL.txt", data)
    print("  sent  SEXTOY_ALL.txt  %d B" % len(data))

    data = open(os.path.join(HERE, "justforfun.js"), "rb").read()
    f.write_file("/ext/apps/Scripts/justforfun.js", data)
    print("  sent  justforfun.js  %d B" % len(data))

    fav = (f.read_file("/ext/favorites.txt") or b"").decode(errors="replace")
    lines = [l for l in fav.splitlines() if l.strip()]
    added = 0
    for p in FAVS:
        if p not in lines:
            lines.append(p)
            added += 1
    f.write_file("/ext/favorites.txt", "\n".join(lines) + "\n")
    print("  favourites: +%d (now %d entries)" % (added, len(lines)))

    # verify
    print("--- on device ---")
    print(f.cmd("storage list /ext/subghz/Sextoy_ALL"))
    print(f.cmd("storage stat /ext/subghz_remote/SEXTOY_ALL.txt"))
    print(f.cmd("storage stat /ext/apps/Scripts/justforfun.js"))
    f.close()
    print("OK. Reboot Flipper so Favourites reloads (hold BACK -> Reboot, or replug).")


if __name__ == "__main__":
    main()
