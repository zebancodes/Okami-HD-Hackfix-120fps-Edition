#!/usr/bin/env python3
"""Run em16's complete eight-trial decision chain, with controlled RNG draws.

Each trial must still select its original state at N=1 and on stock ticks;
all trials must fail on intervening ticks, even when every draw would win.
The window verifier separately checks flags and registers at each detour.
    .venv/Scripts/python tools/verify_chance_rolls.py
    --break gate  removes one chance gate and must fail
"""
import argparse
import struct

import capstone
from capstone import x86 as X

import verify_world_anims as vw
import xrefs

SITES = (0x264945, 0x264992, 0x2649BD, 0x2649E8,
         0x264A13, 0x264A3E, 0x264A71, 0x264A8D)
STATES = (0x1401, 0xD01, 0x1601, 0x901, 0xA01, 0xB01, 0x301, 0x301)
BEGIN, END, INITIAL = 0x264938, 0x264B4C, 0x701


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--break", dest="broken", choices=("gate",))
    args = ap.parse_args()
    _pe, _base, img, _text = xrefs.load_bin("main.dll")
    hdr = vw.parse_header()
    site_rows = {site: (vw.KIND[kind], hdr["names"][group])
                 for site, kind, group, *_rest in hdr["sites"]}
    assert all(site_rows.get(s) == ("notyetb", "actor") for s in SITES), "all eight chance gates"
    patched, _pool = vw.image_for(img, hdr, 1)
    if args.broken:
        # Restore the first gate's complete window, including the RNG call.
        w = next(w for w in hdr["windows"] if w[0] <= SITES[0] < w[0] + w[3])
        patched[w[0]:w[0] + w[3]] = img[w[0]:w[0] + w[3]]
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    scenarios = [("win%d" % i, [1.0] * i + [0.0], STATES[i]) for i in range(8)]
    scenarios += [("none", [1.0] * 8, INITIAL), ("all", [0.0] * 8, STATES[0]),
                  ("equal", [vw.f32(0.003)] * 6 + [vw.f32(0.001)] * 2, INITIAL)]
    problems, runs = [], 0
    for n in (1, 2, 4):
        for residue in range(n):
            for name, draws, stock_state in scenarios:
                e = vw.vmt.Emu(patched, vw.pool_data(hdr, img, n))
                vw.zero_pages(e, vw.OBJ, 0x3000)
                e.set_reg("rdi", vw.OBJ)
                e.set_reg("r12", 0)
                e.set_reg("rsp", vw.vmt.STACK_TOP - 0x1000)
                e.set_reg("xmm8", 0)
                e.set_reg("xmm9", vw.fbits(1.0))
                e.mu.mem_write(vw.OBJ + 0xE34, struct.pack("<I", INITIAL))
                e.mu.mem_write(vw.OBJ + 0x11A0, struct.pack("<I", 0x1234))
                e.mu.mem_write(vw.BASE + vw.FC, struct.pack("<I", residue))
                used = []
                def random_draw(emu):
                    value = draws[len(used)] if len(used) < len(draws) else 1.0
                    used.append(value)
                    emu.set_reg("xmm0", vw.fbits(value))
                e.traps[vw.BASE + 0x1BD580] = random_draw
                e.traps[vw.BASE + 0x26B0A0] = lambda emu: emu.set_reg("rax", 1)
                e.traps[vw.BASE + 0x26ADC0] = lambda emu: emu.set_reg("rax", 0)
                # The two jump trials construct/copy a vector through imports.
                for i, at in enumerate((0x264AB6, 0x264AE8)):
                    ins = next(md.disasm(img[at:at + 16], vw.BASE + at))
                    assert ins.operands[0].type == X.X86_OP_MEM
                    slot = ins.address + ins.size + ins.operands[0].mem.disp
                    trap = vw.TRAP + 0x100 + i * 16
                    e.mu.mem_write(slot, struct.pack("<Q", trap))
                    e.traps[trap] = lambda emu: emu.set_reg("rax", emu.reg("rcx"))
                e.stop_outside = (vw.BASE + BEGIN, vw.BASE + END)
                e.mu.emu_start(vw.BASE + BEGIN, 0, count=2000)
                got = struct.unpack("<I", e.mu.mem_read(vw.OBJ + 0xE34, 4))[0]
                want = stock_state if residue == 0 else INITIAL
                if e.exit != vw.BASE + END or got != want:
                    problems.append("N=%d residue=%d %s: state %X, want %X, exit %s" %
                                    (n, residue, name, got, want, e.exit))
                if residue != 0 and struct.unpack("<I", e.mu.mem_read(vw.OBJ + 0x11A0, 4))[0] != 0x1234:
                    problems.append("skipped trial changed the action callback")
                runs += 1
    print("chance chain: %d directed runs at N=1,2,4 (all tick residues), %d problems" %
          (runs, len(problems)))
    for p in problems[:10]:
        print("PROBLEM " + p)
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
