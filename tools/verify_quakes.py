#!/usr/bin/env python3
"""Run the five quake initializers and the camera update without launching the game.

Compare the patched code with original instructions using the shipped stock
context. Retention follows live mode; duration follows tick-sampled FPS.
Also exercise original behavior with the family off and mode tables rewritten.
"""
import argparse
import hashlib
import itertools
import os
import random
import struct

import pefile

import verify_world_anims as wa
from gamedir import GAME

vmt = wa.vmt
BASE, POOL = wa.BASE, wa.POOL
CAMERA, FPS, MODE, FACTOR, COUNT = 0xB661E0, 0xB6AC44, 0xB6AC45, 0xB663D0, 0xB663D8
PAIR = (0x3F64F95D, 0x3F4CCCCD)
WRITERS = ((0x364C82, 0x364CDE), (0x36FFDF, 0x370046),
           (0x3703B8, 0x370421), (0x3C1DCA, 0x3C1E42), (0x3C5FA6, 0x3C600E))


def patched_image(img, hdr):
    result = bytearray(img)
    for rva, data in wa.patched_bytes(hdr, BASE, POOL):
        result[rva:rva + len(data)] = data
    return result


def make_pool(hdr, img, n, captured, live, broken=None):
    pool = wa.pool_data(hdr, img, n, smode=captured)
    if broken == "retention":
        # Corrupt immutable stock bits, not the reference's expected value.
        pair = struct.pack("<II", *PAIR)
        assert pool.count(pair) == 5
        pool = pool.replace(pair, struct.pack("<II", PAIR[0], 0x3F666666))
    if broken == "context" and n > 1:
        pool[hdr["stride"] * hdr["names"].index("objects") + 2] = 3 - captured
    pool[hdr["live_mode"] + 8] = live
    return pool


def initializer(img, pool, hdr, start, end, real_mode, fps_byte, fast_bits, seed):
    emu = vmt.Emu(img, pool, seed=seed)
    st = vmt.random_state(random.Random(seed))
    st["rdx"] = BASE  # 364C37's jump-table image base, retained to its quake path
    vmt.load_state(emu, st, 0)
    emu.mu.mem_write(BASE + MODE, bytes([real_mode]))
    emu.mu.mem_write(BASE + FPS, bytes([fps_byte]))
    emu.mu.mem_write(BASE + 0x7A81E8, struct.pack("<II", fast_bits, PAIR[1]))
    emu.stop_outside = BASE + start, BASE + end
    emu.mu.emu_start(BASE + start, 0, count=1500)
    assert emu.exit == BASE + end, "initializer did not reach its store boundary"
    factor = bytes(emu.mu.mem_read(BASE + FACTOR, 4))
    count = bytes(emu.mu.mem_read(BASE + COUNT, 1))[0]
    return emu, factor, count


def prepare_camera(emu, factor, count):
    # Isolate this quake block; phase zero makes the real wrap helper an identity.
    emu.mu.mem_write(BASE + CAMERA + 0x1E4, b"\0")
    emu.mu.mem_write(BASE + CAMERA + 0x1E8, struct.pack("<f", 1.0))
    emu.mu.mem_write(BASE + CAMERA + 0x1EC, struct.pack("<f", 0.0))
    emu.mu.mem_write(BASE + FACTOR, factor)
    emu.mu.mem_write(BASE + CAMERA + 0x1F4, struct.pack("<f", 0.0))
    emu.mu.mem_write(BASE + COUNT, bytes([count]))
    emu.traps[BASE + 0x13F2E0] = lambda e: None


def camera_state(emu):
    return (bytes(emu.mu.mem_read(BASE + CAMERA + 0x1E8, 4)),
            bytes(emu.mu.mem_read(BASE + FACTOR, 4)),
            bytes(emu.mu.mem_read(BASE + COUNT, 1)))


def trajectory(ref, fixed, hdr, img, fps, captured, live, factor, count):
    prepare_camera(ref, factor, count)
    prepare_camera(fixed, factor, count)
    steps = 0
    # Enter and leave the other stock context during an existing quake.
    # Its saved factor and count must not be renormalized by a metadata update.
    for tick in range(1, fps + 1):
        mode = captured if tick <= fps // 4 or tick > fps // 2 else 3 - captured
        n = fps // (60 if mode == 1 else 30)
        pool = make_pool(hdr, img, n, mode, live)
        for off in (hdr["stride"] * hdr["names"].index("objects"),):
            fixed.mu.mem_write(POOL + off, bytes(pool[off:off + 8]))
        fixed.mu.mem_write(POOL + hdr["live_mode"] + 8, bytes([mode]))
        fixed.mu.mem_write(BASE + MODE, bytes([mode]))
        ref.mu.mem_write(BASE + MODE, bytes([mode]))
        fixed.mu.mem_write(BASE + wa.FC, struct.pack("<I", tick))
        ref.mu.mem_write(BASE + wa.FC, struct.pack("<I", tick))
        if not tick & (n - 1):
            ref.call(0x476030, BASE + CAMERA)
        fixed.call(0x476030, BASE + CAMERA)
        assert camera_state(ref) == camera_state(fixed), "quake trajectory differs at tick %d" % tick
        steps += 1
    assert bytes(fixed.mu.mem_read(BASE + COUNT, 1)) == b"\0", "quake did not finish"
    return steps


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--break", dest="broken", choices=("retention", "context"))
    ap.add_argument("--seed", type=int, default=101)
    args = ap.parse_args()
    hdr = wa.parse_header()
    raw = open(os.path.join(GAME, "main.dll"), "rb").read()
    assert hashlib.sha1(raw).hexdigest() == hdr["sha"]
    img = bytearray(pefile.PE(data=raw, fast_load=True).get_memory_mapped_image())
    fixed_img = patched_image(img, hdr)
    cases, steps, problems = 0, 0, []
    # At 60-Hz stock-menu N=1, and at F9, both inputs retain the original read.
    for writer, fps, captured, live, table_on, family_on in itertools.product(
            WRITERS, (30, 60, 120), (1, 2), (1, 2), (False, True), (False, True)):
        start, end = writer
        n = fps // (60 if captured == 1 else 30) if fps > 30 and family_on else 1
        n = max(1, n)
        active = n > 1
        fast = wa.fbits(wa.f32(0.800000011920929 ** 0.25)) if fps == 120 and table_on else PAIR[0]
        actual_mode = 1 if fps > 30 else live
        actual_fps = 60 if fps > 30 or captured == 1 else 30
        expected_mode = live if active else actual_mode
        expected_fps = (60 if captured == 1 else 30) if active else actual_fps
        expected_fast = PAIR[0] if active else fast
        seed = args.seed + cases
        try:
            pool = make_pool(hdr, img, n, captured, live, args.broken)
            ref, want_factor, want_count = initializer(img, None, hdr, start, end,
                                                     expected_mode, expected_fps, expected_fast, seed)
            fixed, got_factor, got_count = initializer(fixed_img, pool, hdr, start, end,
                                                      actual_mode, actual_fps, fast, seed)
            assert (got_factor, got_count) == (want_factor, want_count), (
                "factor/count %s/%d, want %s/%d" % (got_factor.hex(), got_count, want_factor.hex(), want_count))
            if active and fps == 120 and table_on and not args.broken:
                steps += trajectory(ref, fixed, hdr, img, fps, captured, live, want_factor, want_count)
        except Exception as e:
            problems.append("%X fps%d captured%d live%d table%d family%d: %s" %
                            (start, fps, captured, live, table_on, family_on, e))
        cases += 1
    for p in problems[:12]:
        print(p)
    print("quakes: %d initializer cases, %d camera steps, %d problems" % (cases, steps, len(problems)))
    return bool(problems)


if __name__ == "__main__":
    raise SystemExit(main())
