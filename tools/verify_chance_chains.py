#!/usr/bin/env python3
"""Run whole per-tick decision chains, original against patched, with random
object states, path selectors and draws.

Each chain is a region of an update (begin .. stops) whose draw compares
tools/chance_trials.py plans as gated trials. Every call in the region is
trapped at its target (or at its import slot) and answered from the
scenario, the same way in both runs, so only the region's own instructions
and the patch's stubs execute. For N = 1, 2, 4 and every tick residue:

* at N = 1 the patched run equals the original run with the same draws: the
  exit, every trapped call (target, rcx, rdx, r8, r9, xmm1..3) and every byte
  written outside the stack and the pool;
* the reference at N > 1 is the patched image with only the chain's own gate
  rows put back to the original bytes (the region's other rows, such as
  em60's paced countdown +15D8, stay converted): on a stock tick the patched
  run equals it with the same draws, and on the other ticks it equals it with
  every draw that feeds a gated compare losing (0.99999), the other draws
  unchanged: every trial fails, and everything else (eligibility tests, picks
  nested in a success, the countdowns after a chain) runs as it would.

The object is random state biased toward the immediates the region compares
its fields with; registers that the region reads before writing are set from
the constants the data flow saw, a pointer to the object or scratch memory,
the image base (a switch table's), or small random selectors.

    .venv/Scripts/python tools/verify_chance_chains.py [--runs 400] [--seed 1]
    --break gate  restores one gated window to the original: must fail
"""
import argparse
import collections
import random
import struct
import sys

import capstone
from capstone import x86 as X

import chance_trials as ct
import verify_world_anims as vw
import xrefs

# name, update, region begin, region stops, planner joins (None: automatic),
# rows standing in for a gated compare that has no window of its own
CHAINS = (
    ("em65", 0x2C0A60, 0x2C0CB6, (0x2C197B,), None, {0x2C1839: 0x2C1847}),
    ("em88", 0x5DF660, 0x5DFC56, (0x5E0697,), None, {0x5E0634: 0x5E0641}),
    ("em60", 0x2A8D20, 0x2A9398, (0x2A94F0, 0x2A9502),
     (0x2A94F0, 0x2A9502, 0x2AA208, 0x2AA8F3), {}),
)
SCRATCH = 0x7F0000000   # what pointer-shaped live-ins point at
LOSE = 0.99999
DRAWN = []              # the draw sites the last run reached, in order


def region(f, begin, stops):
    """instructions reachable from begin before a stop, and the registers read
    there before any write"""
    reach, work = set(), [begin]
    while work:
        at = work.pop()
        if at in reach or at in stops or at not in f.ins:
            continue
        reach.add(at)
        work.extend(f.succ(f.ins[at]))
    live, uses = set(), collections.defaultdict(set)
    seen, work = set(), [(begin, frozenset())]
    while work:
        at, written = work.pop()
        if at in stops or at not in f.ins or (at, written) in seen:
            continue
        seen.add((at, written))
        i = f.ins[at]
        r, w = i.regs_access()
        r = {ct.canonical(i.reg_name(x)) for x in r} - {"rip", "rsp", "rflags"}
        w = {ct.canonical(i.reg_name(x)) for x in w} - {"rip", "rsp", "rflags"}
        if i.mnemonic in ("xor", "xorps", "pxor") and len(i.operands) == 2 and \
                all(o.type == X.X86_OP_REG for o in i.operands) and \
                i.operands[0].reg == i.operands[1].reg:
            r = set()
        if i.mnemonic == "call":
            r, w = set(), w | ct.VOLATILE
        for x in r - written:
            live.add(x)
        for op in i.operands:
            if op.type == X.X86_OP_MEM:
                for reg, role in ((op.mem.base, "base"), (op.mem.index, "index")):
                    if reg:
                        name = ct.canonical(i.reg_name(reg))
                        if name not in written:
                            uses[name].add((role, op.mem.disp, op.mem.scale))
        for n in f.succ(i):
            work.append((n, written | frozenset(w)))
    return reach, live, uses


def field_candidates(f, reach, obj):
    """offset -> (size, values) for `cmp [obj + off], imm` in the region"""
    out = collections.defaultdict(lambda: [0, set()])
    for at in reach:
        i = f.ins[at]
        if i.mnemonic != "cmp" or len(i.operands) != 2:
            continue
        m, k = i.operands
        if m.type == X.X86_OP_MEM and k.type == X.X86_OP_IMM and m.mem.base and \
                ct.canonical(i.reg_name(m.mem.base)) == obj and not m.mem.index:
            c = out[m.mem.disp]
            c[0] = max(c[0], m.size)
            c[1].update({k.imm & ((1 << (8 * m.size)) - 1), (k.imm + 1) & 0xFF, 0})
    return out


class Chain:
    def __init__(self, img, name, fn, begin, stops, joins, substitutes):
        self.name, self.begin, self.stops = name, begin, set(stops)
        self.substitutes = substitutes
        f, js, _ = ct.analyse(fn, joins or (), only=bool(joins))
        gates, notes = ct.plan(f, js)
        self.f = f
        self.gated = {c for cmps, *_r in gates.values() for c in cmps}
        reach, live, uses = region(f, begin, self.stops)
        self.reach = reach
        # draw sites whose value reaches a gated compare (and only gated ones)
        self.lose_sites, mixed = set(), set()
        for c, draws in f.compares.items():
            for d in draws:
                (self.lose_sites if c in self.gated else mixed).add(d)
        both = self.lose_sites & mixed
        if both:
            raise SystemExit("%s: draws %s feed gated and ungated compares" % (
                name, " ".join("%X" % d for d in sorted(both))))
        self.gated_in = {c for c in self.gated if c in reach}
        st = f.state.get(begin, {})
        obj = next(r for r in ("rdi", "rbx", "rsi", "r14") if r in live and
                   any(role == "base" and 0xE00 <= d < 0x4000 for role, d, _s in uses[r]))
        self.obj = obj
        self.regs = {}
        for r in sorted(live):
            if r == obj:
                self.regs[r] = ("obj", None)
            elif r.startswith("xmm"):
                k = st.get("k:" + r)
                self.regs[r] = ("float", k)
            elif any(role == "base" and s == 1 and d > 0x100000 for role, d, s in uses[r]) or \
                    any(role == "base" and d > 0x100000 for role, d, _s in uses[r]):
                self.regs[r] = ("image", None)          # a switch table's base
            elif any(role == "base" for role, _d, _s in uses[r]):
                self.regs[r] = ("pointer", None)
            else:
                self.regs[r] = ("selector", None)
        self.fields = field_candidates(f, reach, obj)
        # every call in the region: direct targets and import slots
        self.direct, self.slots = set(), {}
        for at in reach:
            i = f.ins[at]
            if i.mnemonic != "call":
                continue
            t = f.call_target(i)
            if t is not None:
                self.direct.add(t)
            elif i.operands[0].type == X.X86_OP_MEM and i.operands[0].mem.base == X.X86_REG_RIP:
                self.slots[i.address + i.size + i.operands[0].mem.disp] = at
        self.globals = set()
        for at in reach:
            i = f.ins[at]
            for op in i.operands:
                if op.type == X.X86_OP_MEM and op.mem.base == X.X86_REG_RIP and \
                        i.mnemonic in ("cmp", "test"):
                    ea = i.address + i.size + op.mem.disp
                    other = [o for o in i.operands if o.type == X.X86_OP_IMM]
                    self.globals.add((ea, op.size, other[0].imm if other else None))


def scenario(chain, rnd):
    s = {"seed": rnd.getrandbits(32), "regs": {}, "obj": bytearray(0x4000),
         "draws": {}, "globals": {}}
    for off in range(0, 0x4000, 4):
        x = rnd.random()
        v = 0 if x < 0.6 else rnd.choice((1, 2, 3)) if x < 0.75 else \
            struct.unpack("<I", struct.pack("<f", rnd.choice((0.5, 1.0, 30.0, 150.0, -1.0))))[0]
        s["obj"][off:off + 4] = struct.pack("<I", v)
    for off, (size, values) in chain.fields.items():
        if rnd.random() < 0.75 and 0 <= off < 0x4000 - size:
            s["obj"][off:off + size] = rnd.choice(sorted(values)).to_bytes(size, "little")
    if rnd.random() < 0.8:
        s["obj"][0xE34] = 1
        s["obj"][0xE35] = rnd.choice((0, 1, 2))
    s["obj"][0x1080:0x1084] = struct.pack("<f", 1.0)   # the enemies' rate
    for r, (kind, k) in chain.regs.items():
        if kind == "float":
            s["regs"][r] = k if k is not None else rnd.choice((0.0, 1.0, 0.5, 60.0, 200.0))
        elif kind == "selector":
            s["regs"][r] = rnd.choice((0, 1, 1, 0xFFF7, 2))
    for ea, size, k in chain.globals:
        if k is not None and rnd.random() < 0.6:
            s["globals"][ea] = (size, k)
    for d in sorted(set(d for ds in chain.f.compares.values() for d in ds)):
        s["draws"][d] = rnd.random() ** 3     # often small: the trials win
    return s


def run(chain, image, pool, s, residue, lose):
    e = vw.vmt.Emu(image, pool, seed=s["seed"])
    vw.zero_pages(e, vw.OBJ, 0x4000)
    e.mu.mem_write(vw.OBJ, bytes(s["obj"]))
    vw.zero_pages(e, SCRATCH, 0x2000)
    for r, (kind, _k) in chain.regs.items():
        if kind == "obj":
            e.set_reg(r, vw.OBJ)
        elif kind == "pointer":
            e.set_reg(r, SCRATCH)
        elif kind == "image":
            e.set_reg(r, vw.BASE)
        elif kind == "float":
            e.set_reg(r, vw.fbits(s["regs"][r]))
        else:
            e.set_reg(r, s["regs"][r])
    e.set_reg("rsp", vw.vmt.STACK_TOP - 0x1800)
    e.set_reg("rbp", vw.vmt.STACK_TOP - 0x1000) if "rbp" not in chain.regs else None
    for ea, (size, k) in s["globals"].items():
        e.map_page((vw.BASE + ea) & ~0xFFF)
        e.mu.mem_write(vw.BASE + ea, (k & ((1 << (8 * size)) - 1)).to_bytes(size, "little"))
    e.mu.mem_write(vw.BASE + vw.FC, struct.pack("<I", residue))
    calls = []
    rnd = random.Random(s["seed"])
    answers = collections.defaultdict(lambda: rnd.getrandbits(64))

    DRAWN.clear()

    def draw(emu):
        ret = struct.unpack("<Q", emu.mu.mem_read(emu.reg("rsp"), 8))[0] - vw.BASE - 5
        v = LOSE if lose and ret in chain.lose_sites else s["draws"].get(ret, 0.5)
        DRAWN.append(ret)
        emu.set_reg("xmm0", vw.fbits(v))
        emu.set_reg("rax", struct.unpack("<I", struct.pack("<f", v))[0])
    e.traps[vw.BASE + 0x1BD580] = draw
    for t in chain.direct - {0x1BD580}:
        def answer(emu, t=t):
            n = len(calls)
            calls.append((t, emu.reg("rcx"), emu.reg("rdx"), emu.reg("r8"), emu.reg("r9"),
                          emu.xmm_low(1), emu.xmm_low(2), emu.xmm_low(3)))
            emu.set_reg("rax", answers[(t, n)] & 0xFF if t in (0x2B4770,) else answers[(t, n)] & 3)
            emu.set_reg("xmm0", vw.fbits(float(answers[(t, n)] % 200)))
        e.traps[vw.BASE + t] = answer
    for k, (slot, at) in enumerate(sorted(chain.slots.items())):
        trap = vw.TRAP + 0x100 + 16 * k

        def imported(emu, at=at):
            n = len(calls)
            calls.append(("import@%X" % at, emu.reg("rcx"), emu.reg("rdx"), emu.reg("r8"),
                          emu.reg("r9"), emu.xmm_low(1), emu.xmm_low(2), emu.xmm_low(3)))
            emu.set_reg("rax", emu.reg("rcx"))
            emu.set_reg("xmm0", vw.fbits(float(answers[("imp", n)] % 300)))
        e.map_page((vw.BASE + slot) & ~0xFFF)
        e.mu.mem_write(vw.BASE + slot, struct.pack("<Q", trap))
        e.traps[trap] = imported
    for stop in chain.stops:
        def finish(emu, stop=stop):
            emu.exit = vw.BASE + stop
            emu.mu.emu_stop()
        e.pre[vw.BASE + stop] = finish
    e.written = set()
    try:
        e.mu.emu_start(vw.BASE + chain.begin, 0, count=20000)
    except Exception as exc:   # noqa: BLE001 - a fault is a result to compare
        e.exit = "fault %s at %X" % (exc, e.reg("rip"))
    stack_lo = vw.vmt.STACK_TOP - vw.vmt.STACK_SIZE
    mem = {}
    for a in sorted(e.written):
        if stack_lo <= a < vw.vmt.STACK_TOP + 0x1000 or vw.POOL <= a < vw.POOL + 0x100000 or \
                a == vw.BASE + vw.FC or a - vw.BASE in chain.slots:
            continue
        mem[a] = bytes(e.mu.mem_read(a, 1))[0]
    return e.exit, calls, mem


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=400)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--break", dest="broken", choices=("gate",))
    args = ap.parse_args()
    _pe, _base, img, _text = xrefs.load_bin("main.dll")
    hdr = vw.parse_header()
    rows = {site: vw.KIND[kind] for site, kind, *_r in hdr["sites"]}
    patched, _pool = vw.image_for(img, hdr, 1)
    original = bytearray(img)
    chains = [Chain(img, *c) for c in CHAINS]

    def restore(image, site):
        """put the original bytes back under the row at site (its window, or
        the call a call gate retargets)"""
        w = next((w for w in hdr["windows"] if w[0] <= site < w[0] + w[3]), None)
        if w is not None:
            image[w[0]:w[0] + w[3]] = img[w[0]:w[0] + w[3]]
            return w[0]
        if any(cl[0] == site for cl in hdr["calls"]):
            image[site:site + 5] = img[site:site + 5]
            return site
        raise SystemExit("no window or call at %X" % site)
    refs = {}
    for c in chains:
        sites = sorted(c.substitutes.get(x, x) for x in c.gated_in)
        missing = [x for x in sites if rows.get(x) not in ("notyetb", "notyet", "callgate")]
        if missing:
            raise SystemExit("%s: gated compares without a row: %s" % (
                c.name, " ".join("%X" % x for x in missing)))
        ref = bytearray(patched)
        restored = {restore(ref, x) for x in sites}
        # a restored window must hold nothing but this chain's gates
        others = sorted(site for site, *_r in hdr["sites"]
                        if any(w[0] == lo and w[0] <= site < w[0] + w[3]
                               for w in hdr["windows"] for lo in restored)
                        and site not in sites)
        if others:
            raise SystemExit("%s: restored windows also hold %s" % (
                c.name, " ".join("%X" % x for x in others)))
        refs[c.name] = ref
        print("%s: begin %X, %d instructions, %d gate rows (%d standing in), live-ins %s" % (
            c.name, c.begin, len(c.reach), len(sites), len(c.substitutes),
            " ".join("%s=%s" % (r, k) for r, (k, _v) in sorted(c.regs.items()))))
    # every scenario's original runs, and which gates they exercise: a gated
    # compare reached on a held tick whose draw would have won there
    rnd = random.Random(args.seed)
    plan, fired, exercised = [], collections.Counter(), collections.defaultdict(collections.Counter)
    for c in chains:
        win = {}
        for x in c.gated_in:
            text, _o = ct.describe(c.f, x, c.f.state.get(x, {}))
            k = float(text.split("{")[-1].split("=")[-1].rstrip("}"))
            for d in c.f.compares[x]:
                win[d] = (x, k)
        for k in range(args.runs):
            s = scenario(c, rnd)
            stock = run(c, original, None, s, 0, False)
            held = run(c, original, None, s, 0, True)
            for d in set(DRAWN):
                if d in win and s["draws"][d] < win[d][1]:
                    exercised[c.name][win[d][0]] += 1
            if stock[1] != held[1] or stock[2] != held[2]:
                fired[c.name] += 1
            plan.append((c, k, s, stock, [residue + n * rnd.randrange(1 << 16)
                                         for n in (1, 2, 4) for residue in range(n)]))
    for c in chains:
        print("%s: %d of %d gates exercised (a winning draw reached on a held tick)" % (
            c.name, len(exercised[c.name]), len(c.gated_in)))
    if args.broken:
        for c in chains:
            x, _count = exercised[c.name].most_common(1)[0]
            print("broken: %s gate %X restored (exercised %d times)" % (
                c.name, x, _count))
            restore(patched, c.substitutes.get(x, x))
    problems, runs = [], 0
    for c, k, s, stock, fcs in plan:
        it = iter(fcs)
        for n in (1, 2, 4):
            pool = vw.pool_data(hdr, img, n)
            for residue in range(n):
                fc = next(it)
                got = run(c, patched, pool, s, fc, False)
                want = stock if n == 1 else run(c, refs[c.name], pool, s, fc, residue != 0)
                runs += 1
                if got != want:
                    what = [name for name, a, b in zip(("exit", "calls", "memory"), got, want)
                            if a != b]
                    problems.append("%s run %d N=%d residue %d: %s differ (exit %s, want %s)" % (
                        c.name, k, n, residue, ", ".join(what), got[0], want[0]))
    print("chance chains: %d patched runs over %d scenarios; a trial decided the outcome in %s" % (
        runs, args.runs * len(chains),
        ", ".join("%s %d" % (c.name, fired[c.name]) for c in chains)))
    for p in problems[:15]:
        print("PROBLEM " + p)
    if problems:
        print("FAILED: %d problems" % len(problems))
    return int(bool(problems))


if __name__ == "__main__":
    sys.exit(main())
