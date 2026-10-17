#!/usr/bin/env python3
"""Find code keyed to an animation frame that runs on every tick the frame
spends in a window, and what that code does.

    .venv/Scripts/python tools/frame_events.py [--csv OUT] [--all]

The shared motion advance (4B9C80) steps a model's frame (+F48) by 1 a stock
tick (rate 1), and by 1/N a tick at N times the rate. A test such as
`(int)frame == 18` therefore holds for one tick of a stock pass and for N at
N x: whatever it guards runs N times. Code that means "once, at this frame"
either guards with a crossing (`(int)frame != (int)last && (int)frame ==
K`, at any rate once) or does something idempotent (a hitbox's flag; the hit
test 2DC7B0 itself refuses a target already hit, +E76); a sound, an effect
or a draw guarded by an equality alone runs N times.

The same holds for an integer counter that a pacing family (memory, action
or lea timers, integer skips, a world_anims count row) steps on stock ticks
only: each value lasts N ticks, so `counter == K` (K nonzero) on a field
stepped in the same function is a window too (kind `counter`), and so are
`counter % N == 0` (kind `modulo`) and `(counter & mask) == 0` (kind `bits`).
A function that runs only on stock ticks (a gatefn or gate0 row, or the
target of a call gate) is guarded as a whole.

For every `cvttss2si r32, [base + disp]` (any field: sub-models keep frames
of their own, +1C84, +1534, +3854, +4FA8 ...) the truncated frame is
followed through straight-line code to each `cmp r32, imm` read by je/jne
(an equality window) or `sub r32, a; cmp r32, w; ja/jbe` (a range [a, a+w]).
A window is crossing-guarded when a dominating `cmp r, r` compares it with
the truncated field 4 bytes away. The guarded side is followed to the
branch's post-dominator and its calls (named where known) and stores listed.
Only windows whose guarded side calls something or stores outside the stack
are printed; --all prints every window.

--check fails on an unguarded window whose guarded side starts something
one-shot (an effect, a sound, an object spawn, a motion start or a draw,
followed two calls deep) unless gen_world_anims.MANIFEST has a notyet row on
its compare (between stock ticks it reads "not equal") or REVIEWED says why
it is right as it is.
"""
import argparse
import bisect
import collections
import csv
import os
import re
import sys

from capstone import x86 as X

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import chance_trials as ct  # noqa: E402
import xrefs  # noqa: E402

NAMES = {0x1989F0: "effect", 0x44EA00: "sound", 0x44E3C0: "sound", 0x44E470: "sound",
         0x44E530: "sound", 0x1BD580: "draw", 0x1BD590: "draw", 0x1BD480: "draw",
         0x1BD6D0: "draw", 0x1BD620: "draw", 0x2DC7B0: "hit", 0x199500: "effect2",
         0x1DA050: "spawn", 0x4BA080: "play motion", 0x239420: "advance",
         0x4B9C80: "advance", 0x20E210: "turn", 0x2DA410: "forward", 0x2DA3F0: "move",
         0x20CFD0: "submodel", 0x20CF90: "material", 0x19A000: "effect kind"}
ONE_SHOT = ("effect", "effect2", "sound", "draw", "spawn", "play motion")
SPAWNERS = {0x1989F0: "effect", 0x199500: "effect2", 0x19C620: "effect", 0x44EA00: "sound",
            0x44E3C0: "sound", 0x44E470: "sound", 0x44E530: "sound", 0x1DA050: "spawn",
            0x2DA050: "spawn", 0x4BA080: "play motion"}
_REACH = {}
# unguarded one-shot windows that are right as they are: compare -> why
REVIEWED = {
    0x5074B8: "5072D0 is a scripted task whose loop (the wait 4567C0) task_waits.h paces "
              "to one pass a stock period: the frame moves a whole step between passes",
    0x5E4AD5: "em88 5E4900: frames 29..89 run the hit test 2DD1A0 every tick, a hitbox; "
              "its effect starts only on a hit, which the target's +E76 refuses to repeat",
    0x5E530A: "em88 5E5150: frames 24..36 run the hit test 2DD1A0, as 5E4AD5",
    0x5EF937: "em89 5EF560: frames 11..189 run the hit test 2DD1A0, as 5E4AD5",
    0x2F5711: "2F5640: the effect and sound at +1102 = 90 set +1100, which the code checks "
              "first: once",
    0x364F8F: "364DF0: odd and even counts each add a random height jitter (both sides "
              "act every tick); an alternating per-tick behaviour, not an event",
    0x36CDEF: "36CC50: the same alternating jitter as 364F8F",
}


HIT_TESTS = (0x2DC7B0, 0x2DD1A0)   # their hit effect starts only on a hit +E76 refuses to repeat


def one_shot_of(fn, depth=2):
    """the one-shot kind a call of fn starts (an effect, a sound, an object
    spawn or a motion start), following its own direct calls depth deep; the
    hit tests are not one-shot (a target is hit once per attack)"""
    if fn in HIT_TESTS:
        return None
    if fn in SPAWNERS:
        return SPAWNERS[fn]
    if fn in NAMES and NAMES[fn] == "draw":
        return "draw"
    if depth == 0 or fn in _REACH:
        return _REACH.get(fn)
    _REACH[fn] = None
    try:
        f = ct.Func(fn)
    except (SystemExit, IndexError):
        return None
    for i in f.ins.values():
        if i.mnemonic == "call":
            t = f.call_target(i)
            if t is not None and t != fn:
                k = one_shot_of(t, depth - 1)
                if k:
                    _REACH[fn] = k
                    return k
    return None


def windows_in(f):
    """[(load, field disp, kind, value(s), compare, branch, guarded side)]"""
    out = []
    for at in f.order:
        i = f.ins[at]
        if i.mnemonic != "cvttss2si" or i.operands[1].type != X.X86_OP_MEM:
            continue
        m = i.operands[1].mem
        if m.base in (X.X86_REG_RSP, X.X86_REG_RIP, 0) or m.index:
            continue
        reg = ct.canonical(i.reg_name(i.operands[0].reg))
        k = f.order.index(at)
        sub = None
        for b in f.order[k + 1:k + 16]:
            j = f.ins[b]
            r, w = j.regs_access()
            reads = {ct.canonical(j.reg_name(x)) for x in r}
            writes = {ct.canonical(j.reg_name(x)) for x in w}
            if j.mnemonic in ("call", "ret") or (j.mnemonic == "jmp"):
                break
            if j.mnemonic == "sub" and j.operands[0].type == X.X86_OP_REG and \
                    ct.canonical(j.reg_name(j.operands[0].reg)) == reg and \
                    j.operands[1].type == X.X86_OP_IMM:
                sub = j.operands[1].imm
                continue
            if j.mnemonic == "lea" and ct.canonical(j.reg_name(j.operands[0].reg)) == reg and \
                    j.operands[1].mem.base and \
                    ct.canonical(j.reg_name(j.operands[1].mem.base)) == reg:
                sub = -j.operands[1].mem.disp
                continue
            if j.mnemonic == "cmp" and j.operands[0].type == X.X86_OP_REG and \
                    ct.canonical(j.reg_name(j.operands[0].reg)) == reg and \
                    j.operands[1].type == X.X86_OP_IMM:
                nb = f.ins.get(b + j.size)
                if nb is None or not nb.mnemonic.startswith("j") or nb.mnemonic == "jmp":
                    continue
                v = j.operands[1].imm
                tk = nb.operands[0].imm if nb.operands[0].type == X.X86_OP_IMM else None
                ft = nb.address + nb.size
                if sub is None and nb.mnemonic in ("je", "jne"):
                    side = tk if nb.mnemonic == "je" else ft
                    out.append((at, m.disp, "eq", (v,), b, nb.address, side))
                elif sub is not None and nb.mnemonic in ("ja", "jbe", "jae", "jb"):
                    inside = ft if nb.mnemonic in ("ja", "jae") else tk
                    hi = v if nb.mnemonic in ("ja", "jbe") else v - 1
                    out.append((at, m.disp, "range", (sub, sub + hi), b, nb.address, inside))
                continue
            if reg in writes:
                break
    return out


PACING = ("memory_timers.h", "action_timers.h", "lea_timers.h", "integer_skips.h",
          "world_anims.h")


def paced_counters():
    """function -> {field offset: [census sites]}: integer counters that a
    pacing family steps on stock ticks only (coverage.csv's family; for
    world_anims.h a count row), so each value lasts N ticks at N x"""
    import gen_world_anims as gwa
    counts = {rva for _g, kind, rva, *_r in gwa.MANIFEST if kind in ("count", "count2")}
    docs = os.path.join(os.path.dirname(HERE), "docs", "animation")
    cov = {r["site"]: r for r in csv.DictReader(open(os.path.join(docs, "coverage.csv"),
                                                      encoding="utf-8"))}
    out = collections.defaultdict(lambda: collections.defaultdict(list))
    states = collections.Counter()   # (function, field) -> census sites excluded as state
    for r in csv.DictReader(open(os.path.join(docs, "sites.csv"), encoding="utf-8")):
        m = re.match(r"param_1\+0x([0-9A-Fa-f]+)$", r["field"])
        if not m:
            continue
        key = (int(r["function"], 16), int(m.group(1), 16))
        c = cov.get(r["site"])
        if not c:
            continue
        if c["status"] == "excluded":
            states[key] += 1
            continue
        if c["status"] != "covered" or c["family"] not in PACING or r["shape"] != "counter":
            continue
        if c["family"] == "world_anims.h" and int(r["site"], 16) not in counts and                 not any(int(r["site"], 16) - 8 <= x <= int(r["site"], 16) + 8 for x in counts):
            continue
        out[key[0]][key[1]].append(r["site"])
    # a field the census mostly excluded (a sub-state byte) is dispatched on, not counted
    for (fn, disp), n in states.items():
        if fn in out and disp in out[fn] and n >= len(out[fn][disp]):
            del out[fn][disp]
    return out


def counter_windows_in(f, fields):
    """equality tests of a paced counter field against a nonzero constant:
    `cmp m, imm` on the field, or a register loaded from it just before"""
    out = []
    for at in f.order:
        i = f.ins[at]
        if i.mnemonic != "cmp" or len(i.operands) != 2 or i.operands[1].type != X.X86_OP_IMM                 or i.operands[1].imm == 0:
            continue
        op, disp, load = i.operands[0], None, at
        if op.type == X.X86_OP_MEM and op.mem.base not in (X.X86_REG_RSP, X.X86_REG_RIP, 0)                 and op.mem.disp in fields and not op.mem.index:
            disp = op.mem.disp
        elif op.type == X.X86_OP_REG:
            reg = ct.canonical(i.reg_name(op.reg))
            for b in reversed(f.before(at, 4)):
                j = f.ins[b]
                r, w = j.regs_access()
                if reg not in {ct.canonical(j.reg_name(x)) for x in w}:
                    continue
                if j.mnemonic in ("mov", "movzx", "movsx", "movsxd") and                         j.operands[1].type == X.X86_OP_MEM and                         j.operands[1].mem.disp in fields and not j.operands[1].mem.index and                         j.operands[1].mem.base not in (X.X86_REG_RSP, X.X86_REG_RIP, 0):
                    disp, load = j.operands[1].mem.disp, b
                break
        if disp is None:
            continue
        nb = f.ins.get(at + i.size)
        if nb is None or nb.mnemonic not in ("je", "jne") or nb.operands[0].type != X.X86_OP_IMM:
            continue
        side = nb.operands[0].imm if nb.mnemonic == "je" else nb.address + nb.size
        out.append((load, disp, "counter", (i.operands[1].imm,), at, nb.address, side))
    out += modulo_windows_in(f, fields) + bit_windows_in(f, fields)
    return out


def bit_windows_in(f, fields):
    """`(counter & mask) == 0` on a paced field (`test m/r, imm` read by
    je/jne): an every-8th-count event whose bits hold N ticks at N x"""
    out = []
    for at in f.order:
        i = f.ins[at]
        if i.mnemonic != "test" or len(i.operands) != 2 or i.operands[1].type != X.X86_OP_IMM:
            continue
        op, disp, load = i.operands[0], None, at
        if op.type == X.X86_OP_MEM and op.mem.disp in fields and not op.mem.index and                 op.mem.base not in (X.X86_REG_RSP, X.X86_REG_RIP, 0):
            disp = op.mem.disp
        elif op.type == X.X86_OP_REG:
            reg = ct.canonical(i.reg_name(op.reg))
            for b in reversed(f.before(at, 4)):
                j = f.ins[b]
                _r, w = j.regs_access()
                if reg not in {ct.canonical(j.reg_name(x)) for x in w}:
                    continue
                if j.mnemonic in ("mov", "movzx", "movsx") and                         j.operands[1].type == X.X86_OP_MEM and j.operands[1].mem.disp in fields                         and not j.operands[1].mem.index and                         j.operands[1].mem.base not in (X.X86_REG_RSP, X.X86_REG_RIP, 0):
                    disp, load = j.operands[1].mem.disp, b
                break
        if disp is None:
            continue
        nb = f.ins.get(at + i.size)
        if nb is None or nb.mnemonic not in ("je", "jne") or nb.operands[0].type != X.X86_OP_IMM:
            continue
        side = nb.operands[0].imm if nb.mnemonic == "je" else nb.address + nb.size
        out.append((load, disp, "bits", (i.operands[1].imm,), at, nb.address, side))
    return out


def modulo_windows_in(f, fields):
    """`counter % N == 0` on a paced field: `cmp r, s` where s = (r / N) * N
    (MSVC's reciprocal multiply, then `imul s, t, N`) and r was loaded from
    the field; the value is a multiple of N for N ticks a step at N x"""
    out = []
    for at in f.order:
        i = f.ins[at]
        if i.mnemonic != "cmp" or len(i.operands) != 2 or                 any(op.type != X.X86_OP_REG for op in i.operands):
            continue
        regs = [ct.canonical(i.reg_name(op.reg)) for op in i.operands]
        period, disp, load = None, None, None
        for b in reversed(f.before(at, 16)):
            j = f.ins[b]
            if j.mnemonic == "imul" and len(j.operands) == 3 and                     j.operands[2].type == X.X86_OP_IMM and period is None and                     ct.canonical(j.reg_name(j.operands[0].reg)) in regs:
                period = j.operands[2].imm
            if j.mnemonic in ("mov", "movzx", "movsx", "movsxd") and                     j.operands[0].type == X.X86_OP_REG and                     ct.canonical(j.reg_name(j.operands[0].reg)) in regs and                     j.operands[1].type == X.X86_OP_MEM and j.operands[1].mem.disp in fields and                     not j.operands[1].mem.index and                     j.operands[1].mem.base not in (X.X86_REG_RSP, X.X86_REG_RIP, 0):
                disp, load = j.operands[1].mem.disp, b
                break
        if period is None or disp is None:
            continue
        nb = f.ins.get(at + i.size)
        if nb is None or nb.mnemonic not in ("je", "jne") or nb.operands[0].type != X.X86_OP_IMM:
            continue
        side = nb.operands[0].imm if nb.mnemonic == "je" else nb.address + nb.size
        out.append((load, disp, "modulo", (period,), at, nb.address, side))
    return out


def side_effects(f, start, stop, bound=400):
    calls, stores, work, seen = [], [], [start], set()
    while work:
        at = work.pop()
        if at in seen or at == stop or at not in f.ins or len(seen) > bound:
            continue
        seen.add(at)
        i = f.ins[at]
        if i.mnemonic == "call":
            t = f.call_target(i)
            if t is not None:
                k = one_shot_of(t)
                calls.append(NAMES.get(t, "%X" % t) if t in NAMES or not k else
                             "%X(%s)" % (t, k))
            else:
                n = f.iat_name(i)
                calls.append((n.split("!")[-1][:24] if n else "indirect"))
        elif f.store_effect(i):
            op = next(o for o in i.operands if o.type == X.X86_OP_MEM)
            stores.append("%s+%X" % (i.mnemonic, op.mem.disp & 0xFFFFFFFF))
        work.extend(f.succ(i))
    return calls, stores


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("funcs", nargs="*")
    args = ap.parse_args()
    (_pe, base, _img, _text), starts = ct.image()
    if args.funcs:
        funcs = [int(x, 16) for x in args.funcs]
    else:
        funcs = set()
        for a, m, o, s in xrefs.cached_insns("main.dll"):
            if m == "cvttss2si" and "dword ptr [r" in o and "rsp" not in o and "rip" not in o:
                funcs.add(starts[bisect.bisect_right(starts, a - base) - 1])
        funcs = sorted(funcs)
    paced = paced_counters()
    if not args.funcs:
        funcs = sorted(set(funcs) | set(paced))
    import gen_world_anims as gwa
    # a function that runs only on stock ticks (gatefn/gate0, or called only
    # through a call gate) sees each value once
    gated = {rva for _g, kind, rva, *_r in gwa.MANIFEST if kind in ("gatefn", "gate0")}
    gated |= {extra[0] for _g, kind, _rva, _ins, extra, *_r in gwa.MANIFEST
              if kind == "callgate" and isinstance(extra, tuple)}
    rows = []
    for fn in funcs:
        try:
            f = ct.Func(fn)
        except (SystemExit, IndexError):
            continue
        ws = windows_in(f) + (counter_windows_in(f, paced[fn]) if fn in paced else [])
        if not ws:
            continue
        f.dominators()
        f.postdominators()
        for load, disp, kind, vals, cmp_at, br_at, side in ws:
            cross = f.crossing_above(br_at) or (fn in gated)
            calls, stores = side_effects(f, side, f.ipdom.get(br_at))
            one_shot = sorted({c.split("(")[-1].rstrip(")") for c in calls
                               if c in ONE_SHOT or "(" in c})
            rows.append(dict(function="%X" % fn, load="%X" % load, field="+%X" % disp,
                             kind=kind, frames="..".join(str(v) for v in vals),
                             compare="%X" % cmp_at, branch="%X" % br_at,
                             guard=("gated" if fn in gated else "crossing") if cross else "",
                             one_shot=" ".join(one_shot), calls=" ".join(calls[:12]),
                             stores=" ".join(stores[:8])))
    shown = [r for r in rows if args.all or (not r["guard"] and (r["calls"] or r["stores"]))]
    for r in shown:
        print("%(function)s %(compare)s %(field)s %(kind)s %(frames)s %(guard)s | one-shot: "
              "%(one_shot)s | calls %(calls)s | stores %(stores)s" % r)
    c = collections.Counter((r["kind"], bool(r["guard"]), bool(r["one_shot"])) for r in rows)
    print("# %d windows in %d functions: %s" % (len(rows), len({r["function"] for r in rows}),
                                              dict(c)))
    if args.check:
        import gen_world_anims as gwa
        rowed = {rva for _g, kind, rva, *_r in gwa.MANIFEST if kind == "notyet"}
        open_ = [r for r in rows if not r["guard"] and r["one_shot"] and
                 int(r["compare"], 16) not in rowed and int(r["compare"], 16) not in REVIEWED]
        stale = sorted(set(REVIEWED) - {int(r["compare"], 16) for r in rows})
        for r in open_:
            print("OPEN %(function)s %(compare)s %(field)s %(kind)s %(frames)s: %(one_shot)s" % r)
        for x in stale:
            print("STALE review %X: no such window" % x)
        print("frame events: %d unguarded one-shot windows, %d rowed, %d reviewed, %d open" % (
            sum(1 for r in rows if not r["guard"] and r["one_shot"]),
            sum(1 for r in rows if not r["guard"] and r["one_shot"] and
                int(r["compare"], 16) in rowed),
            sum(1 for r in rows if not r["guard"] and r["one_shot"] and
                int(r["compare"], 16) in REVIEWED), len(open_)))
        if open_ or stale:
            sys.exit(1)
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fo:
            w = csv.DictWriter(fo, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
