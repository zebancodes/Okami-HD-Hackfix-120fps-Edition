#!/usr/bin/env python3
"""Check stock-unit speed retention and applied distance through real 2DA410.

Seven newly fixed callers load, decay, store and apply a stock-unit speed.
Run those complete blocks repeatedly, using the decay slots and installed
instructions dumped by the DLL's own self-test. Execute the game's actual
forward helper; emulate only its two flower_kernel vector/matrix imports.
Stored speed must retain its units, while each displacement is speed / N.

Also execute the three one-off placements and four current-tick-unit callers
unchanged. A global conversion in the helper would break these. All cases
cover N=1/2/4 and every starting residue. This checks composition with the
existing converted decays, not exact equivalence of continuous damping to
the stock game's discrete integration order.

--break missing restores one newly fixed call; --break double adds a second
scale in the helper. Both must fail. Generic world tests independently check
every generated call's register, flags, stack and native installation.
"""
import argparse
import csv
import ctypes
import os
import shutil
import struct
import tempfile
from collections import Counter

import capstone
from capstone import x86_const as CX
import pefile

import verify_const_pools as cp
import verify_world_anims as vw

vmt = vw.vmt
BASE, POOL, OBJ, TRAP = vw.BASE, vw.POOL, vw.OBJ, vw.TRAP
ROOT = vw.ROOT
HELPER = 0x2DA410
# begin, converted decay, forward call, retained field, initial speed
DECAY_BLOCKS = (
    (0x28D78F, 0x28D79A, 0x28D7AA, 0xE18, 7.0),
    (0x29125C, 0x291267, 0x291277, 0xE18, 10.0),
    (0x387233, 0x38723E, 0x38724E, 0xE28, 8.0),
    (0x3885E0, 0x3885EB, 0x3885FB, 0xE28, 9.0),
    (0x3888AE, 0x3888B9, 0x3888C9, 0xE28, 9.0),
    (0x38B7A5, 0x38B7B0, 0x38B7C0, 0xE28, 21.0),
    (0x38CC0D, 0x38CC18, 0x38CC28, 0xE28, 3.5),
)
ONCE = (0x256AF9, 0x2D5463, 0x385E01)
CURRENT = (0x3C22F8, 0x3C288A, 0x3C56D8, 0x3C5E95)
HEADING = (cp.f32(0.6), 0.0, cp.f32(0.8))
POSITION = OBJ + 0x80


def native_decays(dll, image, work):
    """Read the actual installer and per-tick decay outputs, not generated guesses."""
    private = os.path.join(work, "dinput8.dll")
    shutil.copy2(dll, private)
    lib = ctypes.WinDLL(private)
    fn = lib.OkamiConstPoolSelfTest
    fn.argtypes, fn.restype = [ctypes.c_char_p, ctypes.c_char_p], ctypes.c_int
    path = os.path.join(vw.GAME, "main.dll")
    rc = fn(path.encode("mbcs"), work.encode("mbcs"))
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
    selected = {r[1] for r in DECAY_BLOCKS}
    installed = {}
    for i, site in enumerate(tables):
        rva = site["rva"]
        if rva not in selected:
            continue
        idx = indices[site["const"]]
        assert image[rva:rva + 8] == site["orig"], "decay original differs"
        got = blob[start + i * 8:start + (i + 1) * 8]
        want = bytearray(site["orig"])
        struct.pack_into("<i", want, 4,
                         addresses["decay"] + idx * 4 - (addresses["main"] + rva + 8))
        assert got == want, "native installed decay differs at %X" % rva
        # Relocate that native instruction to the emulator's private slot.
        code = bytearray(got)
        struct.pack_into("<i", code, 4, vmt.AUX + idx * 4 - (BASE + rva + 8))
        installed[rva] = (bytes(code), idx)
    assert set(installed) == selected, "missing native decay site"
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
    return installed, values


def prepare(image, hdr, n, installed, values, broken):
    im, pool = vw.image_for(image, hdr, n)
    for rva, (code, _idx) in installed.items():
        im[rva:rva + 8] = code
    if broken == "missing":
        at = DECAY_BLOCKS[0][2]
        im[at:at + 5] = image[at:at + 5]
    elif broken == "double":
        # A deliberately wrong global hook. Execute it, rather than altering
        # the expected result or intercepting the argument in a Python hook.
        original = bytes(image[HELPER:HELPER + 6])
        assert original == b"\x40\x53\x48\x83\xEC\x40"
        offset = (len(pool) + 15) & ~15
        pool.extend(b"\0" * (offset - len(pool)))
        at = POOL + offset
        scale = POOL + hdr["names"].index("actor") * hdr["stride"] + 4
        stub = b"\xF3\x0F\x59\x0D" + struct.pack("<i", scale - (at + 8))
        stub += original
        stub += b"\xE9" + struct.pack("<i", BASE + HELPER + 6 - (at + len(stub) + 5))
        pool.extend(stub)
        im[HELPER:HELPER + 6] = b"\xE9" + struct.pack("<i", at - (BASE + HELPER + 5)) + b"\x90"
    return im, pool, values[n]


def machine(im, pool, aux, image):
    e = vmt.Emu(im, pool, aux)
    vw.zero_pages(e, OBJ, 0x2000)
    matrix = (0.8, 0.0, -0.6, 0.0, 0.0, 1.0, 0.0, 0.0,
              *HEADING, 0.0, 0.0, 5.0, 0.0, 1.0)
    e.mu.mem_write(OBJ + 0x50, struct.pack("<16f", *matrix))
    e.mu.mem_write(OBJ + 0xA8, struct.pack("<Q", POSITION))

    def ctor(m):
        dst = m.reg("rcx")
        vec = (m.xmm_low(1), m.xmm_low(2), m.xmm_low(3), m.rf(m.reg("rsp") + 0x28))
        m.mu.mem_write(dst, struct.pack("<4f", *vec))
        m.set_reg("rax", dst)

    def apply(m):
        mat = struct.unpack("<16f", m.mu.mem_read(m.reg("rdx"), 64))
        vec = struct.unpack("<4f", m.mu.mem_read(m.reg("r8"), 16))
        assert vec[0:2] == (0.0, 0.0) and vec[3] == 1.0, "unexpected forward vector"
        result = [cp.f32(cp.f32(mat[8 + j] * vec[2]) + mat[12 + j]) for j in range(4)]
        m.mu.mem_write(m.reg("rcx"), struct.pack("<4f", *result))

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    imports = [x for x in md.disasm(image[HELPER:HELPER + 0x47], BASE + HELPER)
               if x.mnemonic == "call"]
    assert len(imports) == 2
    for i, (ins, fn) in enumerate(zip(imports, (ctor, apply))):
        op = ins.operands[0]
        assert op.type == CX.X86_OP_MEM and op.mem.base == CX.X86_REG_RIP
        trap = TRAP + 0x100 + i * 0x10
        e.mu.mem_write(ins.address + ins.size + op.mem.disp, struct.pack("<Q", trap))
        e.traps[trap] = fn
    return e


def execute(e, begin, call, image, frame):
    rsp = vmt.STACK_TOP - 0x2000
    e.set_reg("rsp", rsp)
    e.set_reg("rbx", OBJ)
    e.set_reg("rcx", OBJ)
    e.mu.mem_write(rsp, struct.pack("<Q", vmt.SENTINEL))
    e.mu.mem_write(BASE + vw.FC, struct.pack("<I", frame))
    end = BASE + call + 5 if image[call] == 0xE8 else vmt.SENTINEL

    def stop(m):
        m.exit = end
        m.mu.emu_stop()

    e.pre[end] = stop
    e.exit = None
    e.mu.emu_start(BASE + begin, 0, count=2000)
    assert e.exit == end, "block did not return at %X (rip %X)" % (call, e.reg("rip"))


def check_inventory(hdr):
    rows = list(csv.DictReader(open(os.path.join(ROOT, "docs", "animation", "forward_movers.csv"),
                                   newline="")))
    assert len(rows) == len({r["site"] for r in rows}) == 129
    assert all(r["review"] and r["review"] != "pending" for r in rows), "unaudited mover"
    counts = Counter("direct" if r["exact_patch"] else r["review"] for r in rows)
    assert counts == {"direct": 109, "upstream": 12, "once": 4, "current_units": 4}, counts
    calls = {r[0] for r in hdr["calls"]}
    assert all(r[2] in calls for r in DECAY_BLOCKS), "missing selected call"
    assert not calls.intersection(ONCE + CURRENT), "already-scaled/one-off call patched"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dll", default=os.path.join(ROOT, ".build", "bin", "dinput8.dll"))
    ap.add_argument("--out")
    ap.add_argument("--break", dest="broken", choices=("missing", "double"))
    args = ap.parse_args()
    image = pefile.PE(os.path.join(vw.GAME, "main.dll"), fast_load=True).get_memory_mapped_image()
    hdr = vw.parse_header()
    check_inventory(hdr)
    work = args.out or tempfile.mkdtemp(prefix="okami_forward_selftest_")
    os.makedirs(work, exist_ok=True)
    installed, values = native_decays(args.dll, image, work)
    fails, cases, steps = [], 0, 0
    for n in (1, 2, 4):
        im, pool, aux = prepare(image, hdr, n, installed, values, args.broken)
        for residue in range(n):
            for begin, decay, call, field, speed in DECAY_BLOCKS:
                factor = struct.unpack_from("<f", aux, installed[decay][1] * 4)[0]
                for initial in (0.0, speed, -speed):
                    e = machine(im, pool, aux, image)
                    e.wf(OBJ + field, initial)
                    retained, pos = initial, [0.0, 5.0, 0.0]
                    cases += 1
                    for tick in range(8 * n):
                        retained = cp.f32(retained * factor)
                        distance = cp.f32(retained / n)
                        pos = [cp.f32(cp.f32(h * distance) + p) for h, p in zip(HEADING, pos)]
                        execute(e, begin, call, image, residue + tick)
                        got = [e.rf(POSITION + j * 4) for j in range(3)]
                        steps += 1
                        if e.rf(OBJ + field) != retained or got != pos:
                            fails.append("%X N=%d residue=%d initial=%g tick=%d: speed %g/%g, position %s/%s"
                                         % (call, n, residue, initial, tick, e.rf(OBJ + field), retained, got, pos))
                            break
            for call in ONCE + CURRENT:
                for speed in (0.0, 35.0, -35.0):
                    distance = cp.f32(speed / n) if call in CURRENT else speed
                    e = machine(im, pool, aux, image)
                    e.set_xmm_low(1, distance)
                    execute(e, call, call, image, residue)
                    want = [cp.f32(cp.f32(h * distance) + p)
                            for h, p in zip(HEADING, (0.0, 5.0, 0.0))]
                    got = [e.rf(POSITION + j * 4) for j in range(3)]
                    cases += 1
                    steps += 1
                    if got != want:
                        fails.append("unchanged %X N=%d residue=%d speed=%g: %s/%s"
                                     % (call, n, residue, speed, got, want))
    print("129 callers classified: 109 direct, 12 upstream, 4 one-off, 4 current-unit")
    print("%d directed cases, %d actual movement steps, %d failures" % (cases, steps, len(fails)))
    preserved = sum(f.startswith("unchanged ") for f in fails)
    print("failures: %d composed blocks, %d preserved callers" % (len(fails) - preserved, preserved))
    for failure in fails[:12]:
        print("  FAIL " + failure)
    print("native dumps: " + work)
    print("FAILED" if fails else "PASS")
    return bool(fails)


if __name__ == "__main__":
    raise SystemExit(main())
