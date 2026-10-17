#!/usr/bin/env python3
"""Check the real animation-rate installs, stock identity, floors and toggles.

    .venv/Scripts/python tools/verify_player_anim_rates.py
    --break walk   removes the walk detour; the high-rate cases must fail
    --break reg    scales xmm1 instead of walk's xmm0; must fail
"""
import argparse
import csv
import ctypes
import os
import shutil
import struct
import tempfile

import pefile

from gamedir import GAME
import verify_menu_transitions as vmt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE, CAVE, OBJ = vmt.BASE, vmt.POOL, vmt.OBJ
# Independent of the source table: start, join, load register, divisor, floor.
CASES = ((0x3B27D9, 0x3B2800, 0, 1.1, 0.5),
         (0x3B3275, 0x3B399F, 1, 3.9, 0.5),
         (0x3B35A2, 0x3B35CD, 1, 5.4, 0.7),
         (0x3B38F7, 0x3B3926, 1, 5.4, 0.7))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dll", default=os.path.join(ROOT, ".build", "bin", "dinput8.dll"))
    ap.add_argument("--break", dest="broken", choices=("walk", "reg"))
    args = ap.parse_args()
    path = os.path.join(GAME, "main.dll")
    img = bytearray(pefile.PE(path, fast_load=True).get_memory_mapped_image())
    work = tempfile.mkdtemp(prefix="okami_player_anim_")
    dll = os.path.join(work, "dinput8.dll")
    shutil.copy2(args.dll, dll)
    fn = ctypes.WinDLL(dll).OkamiPlayerAnimRateSelfTest
    fn.argtypes, fn.restype = [ctypes.c_char_p, ctypes.c_char_p], ctypes.c_int
    rc = fn(path.encode("mbcs"), work.encode("mbcs"))
    if rc:
        raise RuntimeError("animation install self-test failed (%d): %s" % (rc, work))
    rep = open(os.path.join(work, "report.txt")).read()
    vals = dict(ln.split(None, 1) for ln in rep.splitlines() if len(ln.split()) == 2)
    main_base, cave_base = int(vals["main"], 16), int(vals["cave"], 16)
    cave = bytearray(open(os.path.join(work, "cave.bin"), "rb").read())
    installed = open(os.path.join(work, "sites.bin"), "rb").read()
    states = list(csv.DictReader(open(os.path.join(work, "states.csv"))))
    assert len(installed) == 8 * len(CASES), "animation table completeness"
    problems, stubs = [], []
    for i, (site, _join, reg, _divisor, _floor) in enumerate(CASES):
        raw = bytes((0xF3, 0x0F, 0x10, 0x87 | reg << 3, 0x48, 0x0E, 0, 0))
        assert bytes(img[site:site + 8]) == raw, "audited speed load"
        patch = installed[8 * i:8 * i + 8]
        assert patch[0] == 0xE9 and patch[5:] == b"\x90" * 3, "detour bytes"
        stub = main_base + site + 5 + struct.unpack_from("<i", patch, 1)[0]
        off = stub - cave_base
        want = raw + bytes((0xF3, 0x0F, 0x59, 5 | reg << 3)) + \
            struct.pack("<i", cave_base + 4 - (stub + 16)) + b"\xE9" + \
            struct.pack("<i", main_base + site + 8 - (stub + 21))
        assert cave[off:off + 21] == want, "real installed stub"
        # Relocate the emitted code for the emulator, preserving its opcodes.
        stub_emu = CAVE + off
        struct.pack_into("<i", cave, off + 12, CAVE + 4 - (stub_emu + 16))
        struct.pack_into("<i", cave, off + 17, BASE + site + 8 - (stub_emu + 21))
        img[site:site + 8] = b"\xE9" + struct.pack("<i", stub_emu - (BASE + site + 5)) + b"\x90" * 3
        stubs.append(off)
    if args.broken == "walk":
        img[CASES[0][0]:CASES[0][0] + 8] = bytes((0xF3,0x0F,0x10,0x87,0x48,0x0E,0,0))
    elif args.broken == "reg":
        cave[stubs[0] + 11] = 0x0D
    runs = 0
    for state in states:
        fps, muted, run_on, anim_on = (int(state[k]) for k in ("fps", "muted", "run", "anim"))
        scale = float(state["scale"])
        want_scale = fps / 30 if fps != 30 and not muted and run_on and anim_on else 1.0
        if scale != want_scale:
            problems.append("state %s: scale %g, want %g" % (state, scale, want_scale))
        struct.pack_into("<f", cave, 4, scale)
        for site, join, _reg, divisor, floor in CASES:
            divisor, floor = vmt.f32(divisor), vmt.f32(floor)
            speeds = (0.0, -0.1, floor * divisor - 1e-5, floor * divisor,
                      floor * divisor + 1e-5, divisor, 2 * divisor)
            for stock_speed in speeds:
                # The run fix's speed is in current-tick units while it is on.
                tick_scale = 30 / fps if fps != 30 and not muted and run_on else 1.0
                speed = vmt.f32(stock_speed * tick_scale)
                numerator = vmt.f32(speed * want_scale)
                want_rate = max(floor, vmt.f32(numerator / divisor))
                e = vmt.Emu(img, cave)
                e.map_page(OBJ)
                e.set_reg("rdi", OBJ)
                e.set_reg("rsp", vmt.STACK_TOP - 0x1000)
                e.set_reg("xmm6", vmt.fbits(divisor))  # run's surviving 5.4 divisor
                e.set_reg("xmm7", vmt.fbits(0.5))      # walk's surviving floor
                e.wf(OBJ + 0xE48, speed)
                e.stop_outside = (BASE + site, BASE + (0x3B32AD if site == 0x3B3275 else join))
                e.mu.emu_start(BASE + site, 0, count=100)
                got = e.rf(OBJ + 0xF54)
                if e.exit != BASE + join or vmt.fbits(got) != vmt.fbits(want_rate):
                    problems.append("%X state %s speed %g: got %g, want %g" %
                                    (site, state, speed, got, want_rate))
                if vmt.fbits(e.rf(OBJ + 0xE48)) != vmt.fbits(speed):
                    problems.append("%X changed stored movement speed" % site)
                runs += 1
    print("animation rates: four real installs, %d switch states, %d floor/ratio runs, %d problems" %
          (len(states), runs, len(problems)))
    for p in problems[:8]:
        print("PROBLEM " + p)
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
