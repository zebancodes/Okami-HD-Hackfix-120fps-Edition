#!/usr/bin/env python3
"""Execute seven enemy decision chains and the real four-attempt cooldown.

Controlled RNG draws check each winning trial, equality, failure and priority
at N=1/2/4 and every tick residue. Only external vector imports and selected
attack payloads are emulated; em16 eligibility and em85's two attempt helpers
run their real instructions. The generic world verifier checks each detour's
register/flag contract and the native DLL installer.

--break em16|em85|em89 restores one comparison window to stock.
--break attempts injects the inherited, incorrect tick gate on event counts.
"""
import argparse
from dataclasses import dataclass
import struct

import capstone
from capstone import x86 as X

import verify_world_anims as vw
import xrefs


@dataclass(frozen=True)
class Chain:
    name: str
    begin: int
    end: int
    sites: tuple
    cutoffs: tuple
    outcomes: tuple  # (state, called helper, jump vector)


CHAINS = (
    Chain("em16_near", 0x264AF7, 0x264B4C,
          (0x264B04, 0x264B16), (.012, .05),
          ((0x501, None, None),) * 2),
    Chain("em16_far", 0x264D30, 0x264F95,
          (0x264D3D, 0x264D53, 0x264D86, 0x264DA2), (.012, .003, .008, .008),
          ((0x1401, None, None), (0xD01, None, None),
           (0x301, None, (0., 3., 6.5, 1.)), (0x301, None, (0., 4., 5., 1.)))),
    Chain("em16_target", 0x264F1C, 0x264F95,
          (0x264F29,), (.5,), ((0x1701, None, None),)),
    Chain("em16_other", 0x264F33, 0x264F95,
          (0x264F40, 0x264F52), (.01, .05), ((0x1401, None, None),) * 2),
    Chain("em85", 0x5C66CF, 0x5C68E0,
          (0x5C66DC, 0x5C674B, 0x5C67BA, 0x5C67D2, 0x5C67EB,
           0x5C680C, 0x5C686B, 0x5C6881, 0x5C68CC),
          (.007, .012, .04, .1, .1, .008, .1, .1, .5),
          ((0xA01, None, None), (0xB01, None, None), (1, 0x5CD430, None),
           (1, 0x5CD690, None), (1, 0x5CD760, None), (0xC01, None, None),
           (1, 0x5CD1F0, None), (1, 0x5CD430, None), (1, 0x5CD610, None))),
    Chain("em89_phase0", 0x5EC3D6, 0x5EC65F,
          (0x5EC3E3, 0x5EC404, 0x5EC484, 0x5EC49D, 0x5EC515, 0x5EC595, 0x5EC602),
          (.009, .003, .004, .005, .005, .0055, .005),
          ((1, 0x5F4F50, None), (0x901, None, None), (1, 0x5F4ED0, None),
           (0x1001, None, None), (0xF01, None, None),
           (0x1101, None, None), (0x1201, None, None))),
    Chain("em89_phase1", 0x5EC6AF, 0x5EC7A3,
          (0x5EC6B4, 0x5EC730, 0x5EC794), (.005,) * 3,
          ((0xC01, None, None), (0xD01, None, None), (1, 0x5F4C90, None))),
)
ATTEMPTS = ((0x5CD690, 0x5CD6DE), (0x5CD760, 0x5CD7AE))


def u32(e, offset):
    return struct.unpack("<I", e.mu.mem_read(vw.OBJ + offset, 4))[0]


def put(e, offset, value):
    e.mu.mem_write(vw.OBJ + offset, struct.pack("<I", value))


def bad_attempt_gates(image, pool, img, n):
    """Inject actual executable tick gates, preserving the INC's flag contract."""
    image, pool = bytearray(image), bytearray(pool)
    for _fn, site in ATTEMPTS:
        original = bytes(img[site:site + 6])
        assert original == bytes.fromhex("ff8190340000")
        pool.extend(b"\xCC" * (-len(pool) % 16))
        at = vw.POOL + len(pool)
        stub = bytearray(b"\x9C\x50\x8B\x05")  # pushfq; push rax; mov eax,[fc]
        stub += struct.pack("<i", vw.BASE + vw.FC - (at + 8))
        stub += b"\xA9" + struct.pack("<I", n - 1)
        stub += b"\x75\x0A\x58\x9D" + original + b"\xEB\x02\x58\x9D"
        stub += b"\xE9" + struct.pack("<i", vw.BASE + site + 6 - (at + len(stub) + 5))
        pool += stub
        image[site:site + 6] = b"\xE9" + struct.pack("<i", at - (vw.BASE + site + 5)) + b"\x90"
    return image, pool


def setup(image, pool, residue):
    e = vw.vmt.Emu(image, pool)
    vw.zero_pages(e, vw.OBJ, 0x6000)
    e.set_reg("rdi", vw.OBJ)
    e.set_reg("rbx", vw.OBJ)
    e.set_reg("rsi", 1)
    e.set_reg("r12", 0)
    e.set_reg("r13", 0)
    e.set_reg("r14", 0)
    e.set_reg("rsp", vw.vmt.STACK_TOP - 0x1000)
    e.set_reg("rbp", vw.vmt.STACK_TOP - 0x800)
    e.set_reg("xmm6", vw.fbits(.005))
    e.set_reg("xmm7", vw.fbits(.1))
    e.set_reg("xmm8", 0)
    e.set_reg("xmm9", vw.fbits(1.))
    put(e, 0xE34, 1)
    put(e, 0xE44, 100)
    put(e, 0x1020, 100)
    put(e, 0x11A0, 0x1234)
    put(e, 0x128A, 0xFFFF)
    put(e, 0x12FA, 0xFFFF)
    e.mu.mem_write(vw.BASE + vw.FC, struct.pack("<I", residue))
    return e


def vector_imports(e, img):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    def construct(emu):
        address = emu.reg("rcx")
        values = (emu.xmm_low(1), emu.xmm_low(2), emu.xmm_low(3),
                  emu.rf(emu.reg("rsp") + 0x28))
        emu.mu.mem_write(address, struct.pack("<4f", *values))
        emu.set_reg("rax", address)
    def copy(emu):
        emu.mu.mem_write(emu.reg("rcx"), bytes(emu.mu.mem_read(emu.reg("rdx"), 16)))
        emu.set_reg("rax", emu.reg("rcx"))
    for k, (site, callback) in enumerate(((0x264DCB, construct), (0x264E01, copy),
                                        (0x5C68A6, construct))):
        ins = next(md.disasm(img[site:site + 16], vw.BASE + site))
        assert ins.mnemonic == "call" and ins.operands[0].type == X.X86_OP_MEM
        slot = ins.address + ins.size + ins.operands[0].mem.disp
        trap = vw.TRAP + 0x100 + k * 16
        e.mu.mem_write(slot, struct.pack("<Q", trap))
        e.traps[trap] = callback


def run_chain(image, pool, img, chain, draws, residue):
    e = setup(image, pool, residue)
    if chain.name.startswith("em89"):
        e.set_reg("rdi", 0xFFF7)
    vector_imports(e, img)
    used, called = [], []
    def random_draw(emu):
        if len(used) >= len(chain.sites):
            raise AssertionError("unexpected extra RNG call")
        value = draws[len(used)]
        used.append(value)
        emu.set_reg("xmm0", vw.fbits(value))
    e.traps[vw.BASE + 0x1BD580] = random_draw
    e.traps[vw.BASE + 0x26ADC0] = lambda emu: emu.set_reg("rax", 0)
    e.traps[vw.BASE + 0x26AE50] = lambda emu: emu.set_reg("rax", vw.OBJ + 0x4000)
    for fn in sorted({outcome[1] for outcome in chain.outcomes if outcome[1]}):
        def selected(emu, fn=fn):
            assert emu.reg("rcx") == vw.OBJ
            if fn == 0x5CD430:
                vector = struct.unpack("<4f", emu.mu.mem_read(emu.reg("rdx"), 16))
                assert vector == (0., 10., 0., 1.)
                assert emu.reg("r8") == emu.reg("r9") == 0
            else:
                assert emu.reg("rdx") & 0xFF == 0
            called.append(fn)
        if fn in (0x5CD690, 0x5CD760):
            e.pre[vw.BASE + fn] = selected  # execute the real attempt helper
        else:
            e.traps[vw.BASE + fn] = selected
    def finish(emu):
        emu.exit = vw.BASE + chain.end
        emu.mu.emu_stop()
    e.pre[vw.BASE + chain.end] = finish
    e.mu.emu_start(vw.BASE + chain.begin, 0, count=4000)
    assert e.exit == vw.BASE + chain.end, "chain did not reach its join"
    vector = struct.unpack("<4f", e.mu.mem_read(vw.OBJ + 0x1CB0, 16))
    return e, used, called, vector


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--break", dest="broken", choices=("em16", "em85", "em89", "attempts"))
    args = ap.parse_args()
    _pe, _base, img, _text = xrefs.load_bin("main.dll")
    hdr = vw.parse_header()
    rows = {site: (vw.KIND[kind], hdr["names"][group])
            for site, kind, group, *_ in hdr["sites"]}
    assert all(rows.get(site) == ("notyetb", "actor") for c in CHAINS for site in c.sites)
    assert all(site not in rows for _fn, site in ATTEMPTS), "attempt counts must stay stock"
    image, _pool = vw.image_for(img, hdr, 1)
    if args.broken in ("em16", "em85", "em89"):
        site = next(c.sites[0] for c in CHAINS if c.name.startswith(args.broken))
        w = next(w for w in hdr["windows"] if w[0] <= site < w[0] + w[3])
        image[w[0]:w[0] + w[3]] = img[w[0]:w[0] + w[3]]
    problems, runs, attempt_runs = [], 0, 0
    for n in (1, 2, 4):
        im, pool = image, vw.pool_data(hdr, img, n)
        if args.broken == "attempts":
            im, pool = bad_attempt_gates(image, pool, img, n)
        for residue in range(n):
            for c in CHAINS:
                scenarios = [("win%d" % k, [1.] * k + [0.] + [1.] * (len(c.sites) - k - 1), k)
                             for k in range(len(c.sites))]
                scenarios += [("none", [1.] * len(c.sites), None),
                              ("equal", [vw.f32(x) for x in c.cutoffs], None),
                              ("all", [0.] * len(c.sites), 0)]
                for name, draws, selected in scenarios:
                    e, used, called, vector = run_chain(im, pool, img, c, draws, residue)
                    expected = c.outcomes[selected] if residue == 0 and selected is not None else (1, None, None)
                    state, helper, jump = expected
                    want_calls = [helper] if helper else []
                    # Unsuccessful paths still draw all trials; winning chains short-circuit.
                    want_draws = selected + 1 if residue == 0 and selected is not None else len(c.sites)
                    want_count = int(helper in (0x5CD690, 0x5CD760))
                    callback = 0 if state != 1 and c.name.startswith("em16") else 0x1234
                    flags_at = 0x12FA if c.name.startswith("em89") else 0x128A
                    flags = 0xFFF7 if state != 1 and not c.name.startswith("em16") else 0xFFFF
                    if (u32(e, 0xE34) != state or called != want_calls or len(used) != want_draws
                            or u32(e, 0x3490) != want_count or u32(e, 0x348C) != 0
                            or u32(e, 0x11A0) != callback or u32(e, flags_at) != flags
                            or vector != (jump or (0.,) * 4)):
                        problems.append("N=%d residue=%d %s/%s: state=%X calls=%s draws=%d attempts=%d vector=%s; want %s" %
                                        (n, residue, c.name, name, u32(e, 0xE34), called,
                                         len(used), u32(e, 0x3490), vector, expected))
                    if state == 0x1701 and struct.unpack("<Q", e.mu.mem_read(vw.OBJ + 0x1D00, 8))[0] != vw.OBJ + 0x4000:
                        problems.append("selected target pointer was not retained")
                    runs += 1
            # Four accepted attempts must produce a cooldown on ANY frame phase.
            # Repeat at the same residue in consecutive stock periods.
            for sequence in ((0x5CD690,) * 4, (0x5CD760,) * 4,
                             (0x5CD690, 0x5CD760) * 2):
                e = setup(im, pool, residue)
                for k, fn in enumerate(sequence):
                    e.mu.mem_write(vw.BASE + vw.FC, struct.pack("<I", residue + n * k))
                    e.set_reg("rdx", 0)
                    e.call(fn, vw.OBJ)
                    want_count, cooldown = (k + 1, 0) if k < 3 else (0, 100)
                    if (u32(e, 0x3490), u32(e, 0x348C), u32(e, 0xE34)) != (want_count, cooldown, 1):
                        problems.append("N=%d residue=%d attempt%d helper%X: count=%d cooldown=%d, want %d/%d" %
                                        (n, residue, k + 1, fn, u32(e, 0x3490), u32(e, 0x348C), want_count, cooldown))
                    attempt_runs += 1
                # The active cooldown rejects further attempts, including forced requests.
                e.set_reg("rdx", 1)
                e.call(sequence[0], vw.OBJ)
                if (u32(e, 0x3490), u32(e, 0x348C)) != (0, 100):
                    problems.append("active cooldown did not reject the next attempt")
                attempt_runs += 1
    print("chance decisions: %d directed chain runs, %d attempt calls, %d problems" %
          (runs, attempt_runs, len(problems)))
    for p in problems[:12]:
        print("PROBLEM " + p)
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
