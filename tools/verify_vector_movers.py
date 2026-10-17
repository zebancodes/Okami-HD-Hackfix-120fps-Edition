#!/usr/bin/env python3
"""Compose the three newly scaled vector-mover sites with actual 2DA3F0.

The helper applies the actor's matrix, whose translation row is also its
position. With input w=1 this adds the rotated xyz displacement; it does not
permit a global scale of absolute positions or already converted vectors.

Run em60's actual two vector multiplies and retained-velocity gravity block,
and wp0f's actual outbound initializer, movement and homing blocks. Only
flower_kernel imports are emulated. Generated world windows/literals execute
normally; the whole-world verifier independently checks native installation,
register preservation and the other families' timer/phase conversions.

N=1/2/4 and every frame residue are covered. --break missing restores the
em60 speed window and both wp0f literals; --break double executes an erroneous additional xyz scale
inside the shared helper. Either fault must fail the directed assertions.

The hovering bobbers (em8f 2D9460 in both B6B2A0 bit-14 branches, uta4 5607A0
and its forward surge 5616C0, utb6 56F330, utb7 570640) run their real phase
and sway code tick by tick: the degree phase +E40 must step once a stock
period (N ticks apart), the vector the code stores must be bit for bit what
the original code stores at the same phase, and the position must move by
exactly s times it (em8f through its callvec copy, the others through their
K x s literals). --break missing also restores em8f's call and the bobbers'
literals.
"""
import argparse
import math
import os
import struct

import capstone
from capstone import x86_const as CX
import pefile

import verify_world_anims as vw

vmt = vw.vmt
BASE, POOL, OBJ = vw.BASE, vw.POOL, vw.OBJ
HELPER = 0x2DA3F0
POSITION = OBJ + 0x80
SOURCE = OBJ + 0x1590
TARGET = OBJ + 0x3000
OUTBOUND_LOAD, HOMING_LOAD, SPEED_LOAD = 0x38A973, 0x38AA0D, 0x2A863A
f32 = vw.f32
# the bobbers: (label, blocks run each tick in order, B6B2A0 bit 14, registers
# the blocks expect zero). Each block is (begin, end) on instruction
# boundaries outside every window; the motion advance and the turn between
# them are not run (neither reads +E40 or +E10..+E1C).
BOB_FLAGS = 0xB6B2A0
# "copy": the mover gets a scaled copy (callvec), the stored vector keeps the
# original's values; "literal": the stored vector is the original's times s.
BOBBERS = (
    ("em8f", ((0x2D95CF, 0x2D9715), (0x2D9755, 0x2D981E)), 0, ("r15",), "copy"),
    ("em8f bit14", ((0x2D95CF, 0x2D9715), (0x2D9755, 0x2D981E)), 1, ("r15",), "copy"),
    ("uta4 sway", ((0x56090C, 0x5609A8), (0x5609E7, 0x560A4B)), 0, ("r14",), "literal"),
    ("uta4 surge", ((0x56183C, 0x5618D0), (0x561934, 0x56199B)), 0, (), "literal"),
    ("utb6", ((0x56F47C, 0x56F56B),), 0, ("rbp",), "literal"),
    ("utb7", ((0x570723, 0x570812),), 0, ("rsi",), "literal"),
)
BOB_CALL = 0x2D9819
BOB_LITERALS = (0x560A25, 0x561974, 0x561986, 0x56F546, 0x5707ED)
BOB_COUNTS = (0x2D9615, 0x2D96AB, 0x560932, 0x561862, 0x56F4A2, 0x570749)
# A nonzero translation and nontrivial rotation catch scaling the matrix's
# translation, scaling w, or scaling the input twice.
MATRIX = tuple(map(f32, (0.8, 0.0, -0.6, 0.0, 0.0, 1.0, 0.0, 0.0,
                         0.6, 0.0, 0.8, 0.0, 13.0, 5.0, -17.0, 1.0)))


def vec(e, address):
    return tuple(struct.unpack("<4f", e.mu.mem_read(address, 16)))


def put_vec(e, address, values):
    e.mu.mem_write(address, struct.pack("<4f", *(f32(x) for x in values)))


def translated(position, displacement):
    """Apply's SSE order: (w*M3 + z*M2) + (y*M1 + x*M0)."""
    out = []
    for j in range(3):
        wz = f32(position[j] + f32(MATRIX[8 + j] * displacement[2]))
        yx = f32(f32(MATRIX[4 + j] * displacement[1]) + f32(MATRIX[j] * displacement[0]))
        out.append(f32(wz + yx))
    return tuple(out) + (1.0,)


def prepare(image, hdr, n, broken):
    im, pool = vw.image_for(image, hdr, n)
    if broken == "missing":
        row = next(r for r in hdr["sites"] if r[0] == SPEED_LOAD)
        lo, _stub, _orig, length = hdr["windows"][row[3]]
        im[lo:lo + length] = image[lo:lo + length]
        for site in (OUTBOUND_LOAD, HOMING_LOAD) + BOB_LITERALS:
            im[site:site + 8] = image[site:site + 8]
        im[BOB_CALL:BOB_CALL + 5] = image[BOB_CALL:BOB_CALL + 5]
    elif broken == "double":
        # Real SSE code makes a local scaled copy while retaining input w=1.
        # The original helper's three instructions still set up the Apply
        # arguments, and the IAT call still invokes the same import handler.
        offset = (len(pool) + 15) & ~15
        pool.extend(b"\0" * (offset - len(pool)))
        factor = POOL + len(pool)
        pool.extend(struct.pack("<4f", 1.0 / n, 1.0 / n, 1.0 / n, 1.0))
        entry = POOL + len(pool)
        code = bytearray(b"\x48\x83\xEC\x38\x0F\x10\x02\x0F\x59\x05")
        code.extend(struct.pack("<i", factor - (entry + len(code) + 4)))
        code.extend(b"\x0F\x11\x44\x24\x20\x48\x8D\x54\x24\x20")
        assert image[HELPER:HELPER + 14] == bytes.fromhex("4C8BC2488D5150488B89A8000000")
        code.extend(image[HELPER:HELPER + 14])
        slot = BASE + HELPER + 21 + struct.unpack_from("<i", image, HELPER + 17)[0]
        code.extend(b"\xFF\x15")
        code.extend(struct.pack("<i", slot - (entry + len(code) + 4)))
        code.extend(b"\x48\x83\xC4\x38\xC3")
        pool.extend(code)
        im[HELPER:HELPER + 7] = b"\xE9" + struct.pack("<i", entry - (BASE + HELPER + 5)) + b"\x90\x90"
    return im, pool


def machine(im, pool, imports):
    e = vmt.Emu(im, pool)
    vw.zero_pages(e, OBJ, 0x4000)
    e.mu.mem_write(OBJ + 0x50, struct.pack("<16f", *MATRIX))
    e.mu.mem_write(OBJ + 0xA8, struct.pack("<Q", POSITION))
    e.mu.mem_write(TARGET + 0xA8, struct.pack("<Q", TARGET + 0x80))
    put_vec(e, OBJ + 0xE10, (0, 0, 0, 1))
    handlers = vw.import_handlers()

    def set_xyz(m):
        dst = m.reg("rcx")
        previous = vec(m, dst)
        put_vec(m, dst, (m.xmm_low(1), m.xmm_low(2), m.xmm_low(3), previous[3]))

    def assign(m):
        # Kernel+1A9D0 copies xyz and leaves the destination's w unchanged.
        dst = m.reg("rcx")
        previous, source = vec(m, dst), vec(m, m.reg("rdx"))
        put_vec(m, dst, (*source[:3], previous[3]))
        m.set_reg("rax", dst)

    def normalize(m):
        incoming = vec(m, m.reg("rdx"))
        squared = f32(f32(incoming[0] * incoming[0]) + f32(incoming[1] * incoming[1]))
        squared = f32(squared + f32(incoming[2] * incoming[2]))
        # Kernel+1D940 excludes w from the magnitude, then scales all four
        # lanes by the reciprocal. For zero xyz the destination is untouched.
        if squared > 0:
            inverse = f32(1.0 / f32(math.sqrt(squared)))
            put_vec(m, m.reg("rcx"), tuple(f32(x * inverse) for x in incoming))

    def apply(m):
        matrix = struct.unpack("<16f", m.mu.mem_read(m.reg("rdx"), 64))
        source = vec(m, m.reg("r8"))
        assert source[3] == 1.0, "movement vector lost its affine w=1"
        result = []
        for j in range(4):
            wz = f32(f32(matrix[12 + j] * source[3]) + f32(matrix[8 + j] * source[2]))
            yx = f32(f32(matrix[4 + j] * source[1]) + f32(matrix[j] * source[0]))
            result.append(f32(wz + yx))
        put_vec(m, m.reg("rcx"), result)

    handlers.update({
        # the wrap-angle helper 13F2E0 reduces with fmodf (exact in IEEE)
        "fmodf": lambda m: m.set_xmm_low(0, f32(math.fmod(m.xmm_low(0), m.xmm_low(1)))),
        "?setXYZ@cVec@math@wk@@QEAAXMMM@Z": set_xyz,
        "??4cVec@math@wk@@QEAAAEAV012@AEBV012@@Z": assign,
        "?Normalize4@cVec@math@wk@@SAXAEAV123@AEBV123@@Z": normalize,
        "?Apply@cMatrix@math@wk@@SAXAEAVcVec@23@AEBV123@AEBV423@@Z": apply,
    })
    for i, (slot, name) in enumerate(sorted(imports.items())):
        if name not in handlers:
            continue
        trap = vw.IMPORT_TRAPS + 8 * i
        e.map_page(trap & ~(vw.PAGE - 1))
        e.mu.mem_write(BASE + slot, struct.pack("<Q", trap))
        e.traps[trap] = handlers[name]
    return e


def execute(e, begin, end, frame, setup=None):
    rsp = vmt.STACK_TOP - 0x2000
    e.set_reg("rsp", rsp)
    e.set_reg("rcx", OBJ)
    e.set_reg("rbx", OBJ)
    e.set_reg("rdi", OBJ)
    e.set_reg("rsi", TARGET)
    e.mu.mem_write(rsp, struct.pack("<Q", vmt.SENTINEL))
    e.mu.mem_write(BASE + vw.FC, struct.pack("<I", frame))
    if setup:
        setup(e)
    stop_at = vmt.SENTINEL if end is None else BASE + end

    def stop(m):
        m.exit = stop_at
        m.mu.emu_stop()

    e.pre[stop_at] = stop
    e.exit = None
    try:
        e.mu.emu_start(BASE + begin, 0, count=2000)
        assert e.exit == stop_at, "block %X failed to return (rip %X)" % (begin, e.reg("rip"))
    finally:
        del e.pre[stop_at]


def check_inventory(hdr):
    literals = {r[0]: (vw.KIND[r[3]], hdr["names"][r[4]]) for r in hdr["literals"]}
    sites = {r[0]: (vw.KIND[r[1]], hdr["names"][r[2]]) for r in hdr["sites"]}
    assert literals.get(OUTBOUND_LOAD) == ("lin", "player"), "outbound initializer is not scaled"
    assert literals.get(HOMING_LOAD) == ("lin", "player"), "homing magnitude is not scaled"
    assert sites.get(SPEED_LOAD) == ("dst", "actor"), "actor helper speed copy is not scaled"
    assert not any(site == HELPER for site, *_ in hdr["sites"]), "shared vector helper must stay unchanged"
    assert sites.get(BOB_CALL) == ("callvec", "actor"), "em8f's sway call is not a callvec"
    for site in BOB_LITERALS:
        assert literals.get(site) == ("lin", "objects"), "bobber literal %X is not scaled" % site
    for site in BOB_COUNTS:
        assert sites.get(site, ("",))[0] == "count", "bobber phase %X is not paced" % site
    for _label, blocks, *_ in BOBBERS:
        for edge in (x for block in blocks for x in block):
            assert not any(lo < edge < lo + length for lo, _s, _o, length in hdr["windows"]), \
                "block edge %X lies inside a window" % edge


def check_bobber(im, pool, image, imports, n, residue, blocks, bit, zero, mode, phase):
    """Run a bobber's phase and sway blocks for three stock periods at N."""
    e = machine(im, pool, imports)
    o = machine(bytearray(image), None, imports)
    for m in (e, o):
        m.mu.mem_write(BASE + BOB_FLAGS, struct.pack("<I", bit << 14))
    e.mu.mem_write(OBJ + 0xE40, struct.pack("<h", phase))
    s = f32(1.0 / n)
    stepped = []

    def zero_regs(m):
        for r in zero:
            m.set_reg(r, 0)

    for tick in range(3 * n):
        before = struct.unpack("<h", e.mu.mem_read(OBJ + 0xE40, 2))[0]
        position = vec(e, POSITION)
        for begin, end in blocks:
            if len(blocks) > 1 and begin == blocks[-1][0]:
                position = vec(e, POSITION)   # the hover's y blend ran in the block before
            execute(e, begin, end, residue + tick, zero_regs)
        after = struct.unpack("<h", e.mu.mem_read(OBJ + 0xE40, 2))[0]
        assert after - before in (0, 1), "phase moved by %d in one tick" % (after - before)
        if after != before:
            stepped.append(tick)
        # the original code at the same phase: one stock tick into `after`
        o.mu.mem_write(OBJ + 0xE40, struct.pack("<h", after - 1))
        for begin, end in blocks:
            execute(o, begin, end, residue + tick, zero_regs)
        assert struct.unpack("<h", o.mu.mem_read(OBJ + 0xE40, 2))[0] == after
        stock, stored = vec(o, OBJ + 0xE10), vec(e, OBJ + 0xE10)
        want = stock if mode == "copy" else tuple(f32(v * s) for v in stock[:3]) + stock[3:]
        assert stored == want, "stored sway %s, want %s (%s)" % (stored, want, mode)
        moved = translated(position, tuple(f32(v * s) for v in stock[:3]))
        got = vec(e, POSITION)
        assert (got[0], got[2]) == (moved[0], moved[2]), \
            "moved to %s, want x, z of %s" % (got, moved)
    assert len(stepped) == 3 and all(b - a == n for a, b in zip(stepped, stepped[1:])), \
        "phase stepped on ticks %s at N=%d" % (stepped, n)
    return 3 * n


def check_em60(e, n, residue, speed, factor):
    initial = (3.0, -2.0, 7.0, 1.0)
    put_vec(e, SOURCE, initial)
    e.wf(OBJ + 0x1080, speed)
    e.wf(OBJ + 0xF54, factor)
    retained, position = initial, vec(e, POSITION)
    for tick in range(8 * n):
        scaled_speed = f32(f32(speed) / n)
        distance = tuple(f32(f32(v * scaled_speed) * factor) for v in retained[:3])
        position = translated(position, distance)
        execute(e, 0x2A8630, None, residue + tick,
                lambda m: (m.set_reg("rdx", OBJ), m.set_reg("r8", SOURCE)))
        assert vec(e, SOURCE) == retained, "em60 helper changed retained velocity"
        assert vec(e, POSITION) == position, "em60 movement has wrong speed units"
        execute(e, 0x2AD833, 0x2AD86E, residue + tick)
        retained = (retained[0], f32(retained[1] - f32(scaled_speed * f32(0.2))), retained[2], 1.0)
        assert vec(e, SOURCE) == retained, "em60 gravity composition changed source units"
        assert e.rf(OBJ + 0x1080) == f32(speed) and e.rf(OBJ + 0xF54) == f32(factor)
    return 16 * n


def check_wp0f(e, n, residue):
    execute(e, OUTBOUND_LOAD, 0x38A99F, residue,
            lambda m: (m.set_reg("rbp", 0), m.set_xmm_low(6, 0.0)))
    velocity = (0.0, 0.0, f32(10.0 / n), 1.0)
    assert vec(e, OBJ + 0xE10) == velocity, "wp0f outbound initializer has wrong units"
    assert e.rf(OBJ + 0x10FC) == 0.0 and e.rf(OBJ + 0xE54) == 0.0
    position = vec(e, POSITION)
    for tick in range(30 * n):
        position = translated(position, velocity)
        execute(e, 0x38AA40, 0x38AA4F, residue + tick)
        assert vec(e, POSITION) == position, "wp0f outbound displacement differs"
        assert vec(e, OBJ + 0xE10) == velocity, "wp0f outbound application changed stored vector"
    return 1 + 30 * n + check_homing(e, n, residue + 30 * n)


def check_homing(e, n, residue):
    # Every homing tick rebuilds the source from the current owner-relative
    # direction, so the outbound 10/N never leaks into the new 4/N magnitude.
    position = vec(e, POSITION)
    for tick in range(8 * n):
        target = tuple(f32(position[j] + d) for j, d in enumerate((3.0, 4.0, 0.0))) + (1.0,)
        put_vec(e, TARGET + 0x80, target)
        direction = tuple(f32(target[j] - position[j]) for j in range(3))
        squared = f32(f32(direction[0] * direction[0]) + f32(direction[1] * direction[1]))
        squared = f32(squared + f32(direction[2] * direction[2]))
        inverse = f32(1.0 / f32(math.sqrt(squared)))
        normalized = tuple(f32(x * inverse) for x in direction)
        retained_w = f32(vec(e, OBJ + 0xE10)[3] * inverse)
        velocity = tuple(f32(x * f32(4.0 / n)) for x in normalized) + (retained_w,)
        position = tuple(f32(position[j] + velocity[j]) for j in range(3)) + (1.0,)
        execute(e, 0x38A9C1, 0x38AA4F, residue + tick,
                lambda m: m.set_reg("rbp", 0))
        assert vec(e, OBJ + 0xE10) == velocity, "wp0f homing vector has wrong units"
        assert vec(e, POSITION) == position, "wp0f homing displacement differs"
        assert vec(e, TARGET + 0x80) == target, "wp0f changed the absolute target geometry"
    return 8 * n


def check_current_units(e, n, residue):
    source = (f32(3.0 / n), f32(-2.0 / n), f32(7.0 / n), 1.0)
    put_vec(e, SOURCE, source)
    position = translated(vec(e, POSITION), source)
    execute(e, HELPER, None, residue, lambda m: m.set_reg("rdx", SOURCE))
    assert vec(e, POSITION) == position, "shared helper rescaled a current-tick vector or position"
    assert vec(e, SOURCE) == source, "shared helper changed input vector"
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--break", dest="broken", choices=("missing", "double"))
    args = ap.parse_args()
    image = pefile.PE(os.path.join(vw.GAME, "main.dll"), fast_load=True).get_memory_mapped_image()
    hdr = vw.parse_header()
    check_inventory(hdr)
    # Check the binary constants rather than relying on decompiler labels.
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    for site, want in ((OUTBOUND_LOAD, 10.0), (HOMING_LOAD, 4.0)):
        ins = next(md.disasm(image[site:site + 8], site))
        op = ins.operands[1]
        assert op.type == CX.X86_OP_MEM and op.mem.base == CX.X86_REG_RIP
        assert struct.unpack_from("<f", image, site + ins.size + op.mem.disp)[0] == want
    imports = vw.pe_import_names()
    failures, cases, steps = [], 0, 0
    for n in (1, 2, 4):
        im, pool = prepare(image, hdr, n, args.broken)
        for residue in range(n):
            for speed in (0.0, 0.3, 1.0, 2.0):
                for factor in (0.0, 0.5, 1.0, 2.0):
                    cases += 1
                    try:
                        steps += check_em60(machine(im, pool, imports), n, residue, speed, factor)
                    except AssertionError as exc:
                        failures.append("em60 N=%d residue=%d speed=%g factor=%g: %s" %
                                        (n, residue, speed, factor, exc))
            for label, check in (("wp0f outbound", check_wp0f), ("wp0f homing", check_homing),
                                 ("current units", check_current_units)):
                cases += 1
                try:
                    steps += check(machine(im, pool, imports), n, residue)
                except AssertionError as exc:
                    failures.append("%s N=%d residue=%d: %s" % (label, n, residue, exc))
            for label, blocks, bit, zero, mode in BOBBERS:
                for phase in (0, 359, 7000, -3):
                    cases += 1
                    try:
                        steps += check_bobber(im, pool, image, imports, n, residue, blocks, bit,
                                              zero, mode, phase)
                    except AssertionError as exc:
                        failures.append("%s N=%d residue=%d phase=%d: %s" %
                                        (label, n, residue, phase, exc))
    print("3 scaled sites: em60 speed copy; wp0f outbound10 and homing4")
    print("bobbers: em8f's callvec (both branches), uta4/utb6/utb7 sway and uta4 surge literals")
    print("%d directed cases, %d completed movement/gravity steps, %d failures" %
          (cases, steps, len(failures)))
    for family in ("em60", "wp0f outbound", "wp0f homing", "current units") + \
            tuple(b[0] for b in BOBBERS):
        print("  %s failures: %d" % (family, sum(f.startswith(family + " N=") for f in failures)))
    for failure in failures[:12]:
        print("  FAIL " + failure)
    print("FAILED" if failures else "PASS")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
