#!/usr/bin/env python3
"""Compose heading-mover callers with the real 2DA460 and 1BCFA0 code.

The signed direction bytes remain integers. Only their distance argument is
converted. Run the real signed-byte producer blocks, the three earlier
converted calls, and pl00's current-unit speed load and tail call. Also run
wp0e's move/load/decay/store block (move precedes decay): the imps' dropped
weapon (the knockback 242060 / 249F83 sets +E18 = -6 along the imp's heading)
moves by s x +E18 a tick through its converted call, and +E18 keeps stock
units, x 0.9^s a tick. The wp0e damping constant and installed instruction
come from the DLL's native constant-pool self-test. N=1/2/4 and every residue
are covered.
Its independent random spin is also run through the real angle wrapper with
controlled unsigned draws, including positive and negative wrap boundaries.

Only five flower_kernel imports are emulated: vector construction, matrix
identity and Y rotation, matrix application, and vector addition. The real
heading mover and its matrix-construction helper execute under Unicorn.
This checks applied distance and retained speed, not exact trajectory equality
between continuous damping and stock discrete integration or caller eligibility.
Generic world verification separately checks native installation and register
preservation for every selected conversion.

--break missing restores each new call; --break double injects an erroneous
second scale in the shared helper; --break spin restores the angular factor.
All must fail, the double scale also at pl00.
"""
import argparse
import csv
import ctypes
import math
import os
import shutil
import struct
import tempfile
from collections import Counter

import pefile

import verify_const_pools as cp
import verify_world_anims as vw

vmt = vw.vmt
BASE, POOL, OBJ, TRAP = vw.BASE, vw.POOL, vw.OBJ, vw.TRAP
ROOT = vw.ROOT
HELPER, MATRIX_HELPER = 0x2DA460, 0x1BCFA0
POSITION = OBJ + 0x80
# begin, call, signed direction byte, heading field, stock distance factor
SIGNED_BLOCKS = (
    (0x37F0B4, 0x37F0DF, 0x10F4, 0x10F0, 3.5),
    (0x387083, 0x3870B3, 0x111C, 0x1118, 6.5),
    (0x38A097, 0x38A0B8, 0x10F4, 0x10F0, 3.5),
    (0x39AD74, 0x39AD9F, 0x10E4, 0x10E0, 3.5),
)
DECAY_BEGIN, DECAY_CALL, DECAY_SITE, DECAY_END = 0x389AAD, 0x389AC8, 0x389AD5, 0x389AF4
SPIN_BEGIN, SPIN_FACTOR, SPIN_END = 0x389A90, 0x389A98, 0x389AC8
NEW_CALLS = tuple(r[1] for r in SIGNED_BLOCKS) + (DECAY_CALL,)
EXISTING = (0x383D1F, 0x383EA6, 0x39DE7A)
CURRENT_BEGIN, CURRENT_CALL = 0x3B7281, 0x3B72C6
ANGLES = tuple(cp.f32(a) for a in (0.0, math.pi / 2, -math.pi / 2, 0.6))
START_POS = (2.0, 5.0, -3.0, 7.0)
IDENTITY = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)


def native_decay(dll, image, work):
    """Relocate the native installer output and read its real per-tick slot."""
    private = os.path.join(work, "dinput8.dll")
    shutil.copy2(dll, private)
    lib = ctypes.WinDLL(private)
    fn = lib.OkamiConstPoolSelfTest
    fn.argtypes, fn.restype = [ctypes.c_char_p, ctypes.c_char_p], ctypes.c_int
    rc = fn(os.path.join(vw.GAME, "main.dll").encode("mbcs"), work.encode("mbcs"))
    if rc:
        raise RuntimeError("native constant-pool self-test failed (%d)" % rc)
    report = open(os.path.join(work, "report.txt"), encoding="utf-8").read()
    addresses = {p[0]: int(p[1], 16) for line in report.splitlines()
                 if (p := line.split()) and p[0] in ("main", "decay")}
    tables = cp.parse_table("decay_factors.h", "kDecaySites")
    pools = list(csv.DictReader(open(os.path.join(work, "pools.csv"), newline="")))
    slots = [r for r in pools if r["pool"] == "decay"]
    indices = {int(r["rva"], 16): i for i, r in enumerate(slots)}
    blob = open(os.path.join(work, "sites.bin"), "rb").read()
    start = 8 * len(cp.parse_table("phase_steps.h", "kPhaseSites"))
    index, site = next((i, s) for i, s in enumerate(tables) if s["rva"] == DECAY_SITE)
    slot = indices[site["const"]]
    assert image[DECAY_SITE:DECAY_SITE + 8] == site["orig"], "decay original differs"
    got = blob[start + index * 8:start + (index + 1) * 8]
    want = bytearray(site["orig"])
    struct.pack_into("<i", want, 4,
                     addresses["decay"] + slot * 4 - (addresses["main"] + DECAY_SITE + 8))
    assert got == want, "native installed decay differs"
    code = bytearray(got)
    struct.pack_into("<i", code, 4, vmt.AUX + slot * 4 - (BASE + DECAY_SITE + 8))
    rows = list(csv.DictReader(open(os.path.join(work, "ticks.csv"), newline="")))
    values = {}
    for n, fps in ((1, 30), (2, 60), (4, 120)):
        row = next(r for r in rows if r["path"] == "hook" and int(r["fps"]) == fps
                   and int(r["mode"]) == 2 and not int(r["muted"])
                   and not int(r["bad"]) and (n == 1 or int(r["shadow"])))
        assert cp.scale_of({k: int(row[k]) for k in
                            ("fps", "mode", "muted", "bad", "shadow")}) == 1.0 / n
        values[n] = b"".join(struct.pack("<I", v) for v in cp.split_hex(row["decay"]))
        assert len(values[n]) == 4 * len(slots)
        factor = struct.unpack_from("<f", values[n], slot * 4)[0]
        assert math.isclose(factor, 0.9 ** (1.0 / n), rel_tol=1e-6)
    return bytes(code), slot, values


def prepare(image, hdr, n, decay_code, values, broken):
    im, pool = vw.image_for(image, hdr, n)
    im[DECAY_SITE:DECAY_SITE + 8] = decay_code
    if broken == "missing":
        for site in NEW_CALLS:
            im[site:site + 5] = image[site:site + 5]
    elif broken == "spin":
        im[SPIN_FACTOR:SPIN_FACTOR + 8] = image[SPIN_FACTOR:SPIN_FACTOR + 8]
    elif broken == "double":
        original = bytes(image[HELPER:HELPER + 11])
        assert original == b"\x48\x8B\xC4\x53\x48\x81\xEC\xB0\0\0\0"
        offset = (len(pool) + 15) & ~15
        pool.extend(b"\0" * (offset - len(pool)))
        at = POOL + offset
        scale = POOL + hdr["names"].index("actor") * hdr["stride"] + 4
        stub = b"\xF3\x0F\x59\x0D" + struct.pack("<i", scale - (at + 8))
        stub += original
        stub += b"\xE9" + struct.pack("<i", BASE + HELPER + 11 - (at + len(stub) + 5))
        pool.extend(stub)
        im[HELPER:HELPER + 11] = (b"\xE9" + struct.pack("<i", at - (BASE + HELPER + 5))
                                 + b"\x90" * 6)
    return im, pool, values[n]


def machine(im, pool, aux, pe):
    e = vmt.Emu(im, pool, aux)
    vw.zero_pages(e, OBJ, 0x2000)
    e.mu.mem_write(OBJ + 0xA8, struct.pack("<Q", POSITION))
    e.mu.mem_write(POSITION, struct.pack("<4f", *START_POS))

    def ctor(m):
        dst = m.reg("rcx")
        v = (m.xmm_low(1), m.xmm_low(2), m.xmm_low(3), m.rf(m.reg("rsp") + 0x28))
        m.mu.mem_write(dst, struct.pack("<4f", *v))
        m.set_reg("rax", dst)

    def identity(m):
        m.mu.mem_write(m.reg("rcx"), struct.pack("<16f", *IDENTITY))

    def rotate_y(m):
        before = struct.unpack("<16f", m.mu.mem_read(m.reg("rdx"), 64))
        assert before == IDENTITY, "unexpected matrix before Y rotation"
        angle = m.xmm_low(2)
        c, s = cp.f32(math.cos(angle)), cp.f32(math.sin(angle))
        mat = (c, 0.0, -s, 0.0, 0.0, 1.0, 0.0, 0.0,
               s, 0.0, c, 0.0, 0.0, 0.0, 0.0, 1.0)
        m.mu.mem_write(m.reg("rcx"), struct.pack("<16f", *mat))

    def apply(m):
        mat = struct.unpack("<16f", m.mu.mem_read(m.reg("rdx"), 64))
        vec = struct.unpack("<4f", m.mu.mem_read(m.reg("r8"), 16))
        assert vec[0:2] == (0.0, 0.0) and vec[3] == 1.0, "unexpected forward vector"
        result = tuple(cp.f32(mat[8 + j] * vec[2]) for j in range(3)) + (1.0,)
        m.mu.mem_write(m.reg("rcx"), struct.pack("<4f", *result))

    def add(m):
        dst = m.reg("rcx")
        lhs = struct.unpack("<4f", m.mu.mem_read(dst, 16))
        rhs = struct.unpack("<4f", m.mu.mem_read(m.reg("rdx"), 16))
        result = tuple(cp.f32(a + b) for a, b in zip(lhs[:3], rhs[:3])) + (lhs[3],)
        m.mu.mem_write(dst, struct.pack("<4f", *result))
        m.set_reg("rax", dst)

    callbacks = {
        "??0cVec@math@wk@@QEAA@MMMM@Z": ctor,
        "?Identity@cMatrix@math@wk@@SAXAEAV123@@Z": identity,
        "?RotateY@cMatrix@math@wk@@SAXAEAV123@AEBV123@M@Z": rotate_y,
        "?Apply@cMatrix@math@wk@@SAXAEAVcVec@23@AEBV123@AEBV423@@Z": apply,
        "??YcVec@math@wk@@QEAAAEAV012@AEBV012@@Z": add,
    }
    found = set()
    for entry in pe.DIRECTORY_ENTRY_IMPORT:
        if entry.dll.lower() != b"flower_kernel.dll":
            continue
        for imp in entry.imports:
            name = imp.name.decode() if imp.name else ""
            if name not in callbacks:
                continue
            trap = TRAP + 0x100 + len(found) * 0x10
            e.mu.mem_write(BASE + imp.address - pe.OPTIONAL_HEADER.ImageBase,
                           struct.pack("<Q", trap))
            e.traps[trap] = callbacks[name]
            found.add(name)
    assert found == set(callbacks), "missing heading-mover import"
    return e


def execute(e, begin, end, frame, tail=False):
    rsp = vmt.STACK_TOP - 0x2000
    e.set_reg("rsp", rsp)
    e.set_reg("rbx", OBJ)
    e.set_reg("rcx", OBJ)
    e.mu.mem_write(BASE + vw.FC, struct.pack("<I", frame))
    if tail:
        # pl00's real epilogue restores rbx/rdi before its tail jump.
        e.mu.mem_write(rsp + 0x40, struct.pack("<Q", 0x7654))
        e.mu.mem_write(rsp + 0x48, struct.pack("<Q", vmt.SENTINEL))
        e.mu.mem_write(rsp + 0x50, struct.pack("<Q", 0x4321))
        stop_at = vmt.SENTINEL
    else:
        stop_at = BASE + end

    def stop(m):
        m.exit = stop_at
        m.mu.emu_stop()

    e.pre[stop_at] = stop
    e.exit = None
    e.mu.emu_start(BASE + begin, 0, count=3000)
    assert e.exit == stop_at, "block at %X did not finish (rip %X)" % (begin, e.reg("rip"))


def moved(position, angle, distance):
    heading = (cp.f32(math.sin(angle)), 0.0, cp.f32(math.cos(angle)))
    return tuple(cp.f32(p + cp.f32(h * distance)) for p, h in zip(position[:3], heading)) + (position[3],)


def position(e):
    return struct.unpack("<4f", e.mu.mem_read(POSITION, 16))


def wrapped(value):
    """Scalar oracle for the real 13F2E0 small-angle branches used here."""
    pi, tau = cp.f32(math.pi), cp.f32(2 * math.pi)
    if value > pi:
        while value >= pi:
            value = cp.f32(value - tau)
    elif value < -pi:
        while value < -pi:
            value = cp.f32(value + tau)
    return value


def check_inventory(hdr):
    rows = list(csv.DictReader(open(os.path.join(ROOT, "docs", "animation", "heading_movers.csv"),
                                   newline="")))
    assert len(rows) == len({r["site"] for r in rows}) == 25
    assert all(r["review"] and r["review"] != "pending" for r in rows), "unaudited heading mover"
    counts = Counter("direct" if r["exact_patch"] else r["review"] for r in rows)
    assert counts == {"direct": 8, "current_units": 17}, counts
    calls = {r[0] for r in hdr["calls"]}
    assert set(NEW_CALLS + EXISTING) <= calls, "missing selected heading call"
    assert CURRENT_CALL not in calls, "current-unit player call converted twice"
    assert SPIN_FACTOR in {r[0] for r in hdr["literals"]}, "continuous spin factor not converted"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dll", default=os.path.join(ROOT, ".build", "bin", "dinput8.dll"))
    ap.add_argument("--out")
    ap.add_argument("--break", dest="broken", choices=("missing", "double", "spin"))
    args = ap.parse_args()
    pe = pefile.PE(os.path.join(vw.GAME, "main.dll"), fast_load=False)
    image = pe.get_memory_mapped_image()
    hdr = vw.parse_header()
    check_inventory(hdr)
    work = args.out or tempfile.mkdtemp(prefix="okami_heading_selftest_")
    os.makedirs(work, exist_ok=True)
    decay_code, slot, values = native_decay(args.dll, image, work)
    fails, cases, steps = [], 0, 0
    for n in (1, 2, 4):
        im, pool, aux = prepare(image, hdr, n, decay_code, values, args.broken)
        for residue in range(n):
            for draw in (0.0, 0.125, 0.5, cp.f32(0.999)):
                for start in (0.0, 0.6, -3.0, -cp.f32(math.pi),
                              cp.f32(math.pi - 0.01), cp.f32(math.pi)):
                    e = machine(im, pool, aux, pe)
                    e.wf(OBJ + 0xB0, start)
                    e.wf(OBJ + 0xE14, 0.6)
                    e.wf(OBJ + 0xE18, 7.0)
                    rotation = cp.f32(start)
                    cases += 1
                    increment = cp.f32(cp.f32(draw * cp.f32(math.pi / 180)) * cp.f32(16.0 / n))
                    for tick in range(4 * n):
                        rotation = wrapped(cp.f32(rotation + increment))
                        e.set_xmm_low(0, draw)
                        execute(e, SPIN_BEGIN, SPIN_END, residue + tick)
                        steps += 1
                        got = e.rf(OBJ + 0xB0)
                        if (got != rotation or e.rf(OBJ + 0xE14) != cp.f32(0.6) or
                                e.rf(OBJ + 0xE18) != 7.0 or position(e) != START_POS):
                            fails.append("spin %X N=%d residue=%d draw=%g start=%g tick=%d: %g/%g"
                                         % (SPIN_FACTOR, n, residue, draw, start, tick, got, rotation))
                            break
            for begin, call, direction_field, heading_field, factor in SIGNED_BLOCKS:
                for direction in (-128, -1, 0, 1, 127):
                    for angle in ANGLES:
                        e = machine(im, pool, aux, pe)
                        e.mu.mem_write(OBJ + direction_field, struct.pack("<b", direction))
                        e.wf(OBJ + heading_field, angle)
                        pos = START_POS
                        cases += 1
                        distance = cp.f32(cp.f32(float(direction) * factor) / n)
                        for tick in range(3 * n):
                            pos = moved(pos, angle, distance)
                            execute(e, begin, call + 5, residue + tick)
                            steps += 1
                            got = position(e)
                            if (got != pos or e.rf(OBJ + heading_field) != angle or
                                    bytes(e.mu.mem_read(OBJ + direction_field, 1)) != struct.pack("<b", direction)):
                                fails.append("%X N=%d residue=%d direction=%d angle=%g tick=%d: %s/%s"
                                             % (call, n, residue, direction, angle, tick, got, pos))
                                break
            factor = struct.unpack_from("<f", aux, slot * 4)[0]
            for initial in (0.0, 7.0, -7.0):
                for angle in ANGLES:
                    e = machine(im, pool, aux, pe)
                    e.wf(OBJ + 0xE18, initial)
                    e.wf(OBJ + 0xE14, angle)
                    retained, pos = initial, START_POS
                    cases += 1
                    for tick in range(8 * n):
                        pos = moved(pos, angle, cp.f32(retained * cp.f32(1.0 / n)))
                        retained = cp.f32(retained * factor)
                        execute(e, DECAY_BEGIN, DECAY_END, residue + tick)
                        steps += 1
                        got = position(e)
                        if got != pos or e.rf(OBJ + 0xE18) != retained or e.rf(OBJ + 0xE14) != angle:
                            fails.append("wp0e %X N=%d residue=%d initial=%g angle=%g tick=%d: speed %g/%g, position %s/%s"
                                         % (DECAY_CALL, n, residue, initial, angle, tick,
                                            e.rf(OBJ + 0xE18), retained, got, pos))
                            break
            for call in EXISTING:
                for speed in (0.0, 5.0, -5.0):
                    for angle in ANGLES:
                        e = machine(im, pool, aux, pe)
                        e.set_xmm_low(1, speed)
                        e.set_xmm_low(2, angle)
                        execute(e, call, call + 5, residue)
                        want = moved(START_POS, angle, cp.f32(speed / n))
                        cases += 1
                        steps += 1
                        if position(e) != want:
                            fails.append("existing %X N=%d residue=%d speed=%g angle=%g: %s/%s"
                                         % (call, n, residue, speed, angle, position(e), want))
            for speed in (0.0, 1.1, -1.1, 35.0):
                for angle in ANGLES:
                    e = machine(im, pool, aux, pe)
                    current = cp.f32(cp.f32(speed) / n)
                    e.wf(OBJ + 0xE48, current)
                    e.wf(OBJ + 0xB4, angle)
                    e.mu.mem_write(BASE + 0xB6AC45, b"\x01")
                    execute(e, CURRENT_BEGIN, CURRENT_CALL, residue, tail=True)
                    want = moved(START_POS, angle, current)
                    cases += 1
                    steps += 1
                    if position(e) != want or e.rf(OBJ + 0xE48) != current:
                        fails.append("unchanged %X N=%d residue=%d speed=%g angle=%g: %s/%s"
                                     % (CURRENT_CALL, n, residue, speed, angle, position(e), want))
    print("25 heading callers reviewed: 8 direct, 17 current-unit")
    print("%d directed cases, %d actual movement steps, %d failures" % (cases, steps, len(fails)))
    current = sum(f.startswith("unchanged ") for f in fails)
    wp0e = sum(f.startswith("wp0e ") for f in fails)
    print("failures: %d converted blocks (%d of them wp0e's), %d current-unit"
          % (len(fails) - current, wp0e, current))
    for failure in fails[:12]:
        print("  FAIL " + failure)
    print("native dumps: " + work)
    print("FAILED" if fails else "PASS")
    return bool(fails)


if __name__ == "__main__":
    raise SystemExit(main())
