#!/usr/bin/env python3
"""Countdowns that end early between stock ticks.

    .venv/Scripts/python tools/early_countdowns.py [--csv OUT] [--all]

A countdown a family paces (a count row, the action, memory or lea timers,
integer_skips) holds each value for N ticks at N times the rate. Two shapes
then act before stock does:

  before   a test of the field against 0 that runs before its decrement on
           the same tick (the action timers' `test ax, ax; je` at the top,
           a `cmp word [F], 0`): it reads 0 on every tick after the stock
           tick that stored the 0, so its zero side acts up to N - 1 ticks
           before stock's next tick, where stock acts (3/4 of a stock tick
           at 120), and a countdown reloaded there loses that much a cycle;
  register a count row on the store alone, the decrement in a register
           before it: on the ticks between, the decrement still runs and a
           test of its result (or its flags) after the store reads 0 a tick
           after the stored 1.

For every countdown in sites.csv (a step of -1) that coverage.csv counts
covered, the field's other accesses in its function (same displacement,
the load's base register) are read: a compare with 0, or a load the next
instructions test against 0, whose branch's zero side reaches an effect (a
store outside the stack, a call, chance_trials' rules) before the branch's
post-dominator. A test that a world row already gates (any notyet kind, a
count, hold) or in a gatefn/gate0 function is left out; --all lists them.
Only a transient zero is listed: every path of the zero side re-arms the
field with a nonzero value (an immediate, or a register set from one on the
path) before the branch's post-dominator. A countdown that rests at 0, whose
zero side is its idle behaviour every tick (a hit lock's unlocked path),
must not read "not yet" between stock ticks: the active path would run on
N - 1 of every N ticks while it idles. A store of the actor's state bytes
(+E34..+E37) is not enough to show the zero is passing: until 2026-10-12 it
counted, and 101 of the 131 rows it chose could leave a countdown resting at
0 with its active path running between stock ticks (smoke puffs piling up
over a battle's enemies at 60 and 120). A test behind an event
edge (event_counters.event_gated: the motion advance's "ended" answer, a
press) is left too: it runs once a loop of a looping motion, and a "not
yet" there would drop the loop ends that fall between stock ticks.

--check (in tools/run_suite.sh) fails on a listed zero test that no row
gates and REVIEWED does not explain, and on a "not yet" row (notyet,
notyetneg, notyetb, notyett) on the zero test of a countdown that rests at
0; --spec writes the rows for the rest (misc_reading/fps_followups11.spec
has them).
"""
import argparse
import collections
import csv
import os
import sys

from capstone import x86 as X

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import chance_trials as ct  # noqa: E402
import event_counters as ec  # noqa: E402

DOCS = os.path.join(os.path.dirname(HERE), "docs", "animation")
PACING = ("world_anims.h", "action_timers.h", "memory_timers.h", "lea_timers.h",
          "integer_skips.h")
GATING = ("notyet", "notyetneg", "notyetb", "notyetend", "notyett", "hold", "count", "countlast",
          "count2", "callgate", "callend")
# which way a branch goes when the value it tests is 0 (test r, r / cmp x, 0)
ZERO_TAKEN = {"je": True, "jne": False, "jle": True, "jg": False, "jbe": True, "ja": False,
              "js": False, "jns": True, "jl": False, "jge": True}
# early zero tests left as they are: test -> why
REVIEWED = {
    0x13A934: "the skip check's watchdog 13A930 (integer_skips.h counts it on stock ticks): its "
              "reload comes up to 3 ticks early, a system counter with nothing to see",
    0x1487E6: "the options' controller setting +90 (integer_skips.h): a guarded countdown whose "
              "end calls 148290 up to 3 ticks early, in a menu",
}
# not-yet rows the rule above calls resting at 0, read by hand: the rows from before
# 2026-10-11 (all shipped in 1.0.1 and played) move a state machine on at the zero, through
# a dispatch the rule does not follow (their readings are in world_anims.csv); and four
# whose reload the rule cannot prove nonzero. A new row of this shape fails --check.
RESTING_REVIEWED = {
    0x1DC570: "an03's random target: the zero side reloads the wait from a draw (90..345), a register the rule cannot prove nonzero",
    0x203248: "an0c's wander countdown: reloaded from a draw on the zero side",
    0x205C24: "every animal's head-look timer +1175: reloaded from a draw on the zero side",
    0x5DC89C: "an equality with 30 on the decremented copy (effect 0x32 starts once), not a countdown resting at 0",
    **{a: "a row from before 2026-10-11 (1.0.1), read when it was added" for a in (
        0x16CA1F, 0x1D60E7, 0x1D9334, 0x1DD689, 0x1E0F3C, 0x1E3B79, 0x1E7409, 0x1EA34F,
        0x1EC41A, 0x1EC998, 0x1ED64F, 0x1F4D49, 0x1FB154, 0x1FEA5A, 0x2030D7, 0x203196,
        0x21ABD6, 0x22E615, 0x2A4E35, 0x2D7DB0, 0x2D7DFA, 0x2D8442, 0x2D852C, 0x33AA89,
        0x33D386, 0x382C1D, 0x382E31, 0x383EE5, 0x3930D0, 0x396F90, 0x3984DA, 0x39913C,
        0x399D75, 0x3A65AF, 0x3BB625, 0x3BFB76, 0x3CCE59, 0x3CD07C, 0x3CD1E5, 0x3D03F0,
        0x3D0895, 0x3D1082, 0x3D12E1, 0x3D145C, 0x3D1624, 0x3D1778, 0x3D1895, 0x41E1F8,
        0x41EF12, 0x467D25, 0x48A061, 0x491261, 0x495F3C, 0x50E91C, 0x55F505, 0x55F54F,
        0x55FBB0, 0x55FC9E, 0x563522, 0x570411, 0x5704A0, 0x598C32, 0x65176D,
    )},
}
# the world group a countdown's notyet joins, by the census group of its site
WORLD_GROUP = {"enemies": "actor", "animals": "actor", "player and weapons": "player", "people": "human",
               "effects": "effect"}
TIMERS = ("action_timers.h", "memory_timers.h", "lea_timers.h")
# rows that make a test read "not yet" between stock ticks: on a countdown
# that rests at 0 they run its active path on N - 1 of every N ticks
NOT_YET_KINDS = ("notyet", "notyetneg", "notyetb", "notyett")
# which way it goes for a positive result, "not finished" (ZF = SF = OF = 0)
POSITIVE_TAKEN = {"je": False, "jne": True, "jle": False, "jg": True, "jbe": False, "ja": True,
                  "js": False, "jns": True, "jl": False, "jge": True}


def world_rows(groups=None):
    rows = {}
    for r in csv.DictReader(open(os.path.join(DOCS, "world_anims.csv"), encoding="utf-8")):
        if r["status"] == "selected":
            rows[int(r["site"], 16)] = r["kind"]
            if groups is not None:
                groups[int(r["site"], 16)] = r["group"]
    return rows


def not_yet_side(br):
    """where the branch goes with ZF = SF = OF = 0 (a positive, unfinished count)"""
    return br.operands[0].imm if POSITIVE_TAKEN[br.mnemonic] else br.address + br.size


def flag_source(f, br):
    """the instruction whose flags `br` reads: back over plain moves"""
    at = None
    for a in reversed([x for x in f.order if x < br.address][-6:]):
        i = f.ins[a]
        if i.mnemonic in ("test", "cmp", "sub", "add", "dec", "and"):
            return a
        if i.mnemonic not in ("mov", "movzx", "movsx", "lea"):
            return None
    return at


def mem_of(i):
    for op in i.operands:
        if op.type == X.X86_OP_MEM:
            return op
    return None


def branch_after(f, at, reg=None, limit=4):
    """the conditional branch reading the flags set at `at` (a compare), past
    flag-neutral moves; None if something else writes the flags first"""
    i = f.ins.get(at)
    k = 0
    nxt = at + i.size
    while k < limit:
        j = f.ins.get(nxt)
        if j is None:
            return None
        if j.mnemonic in ZERO_TAKEN and j.operands[0].type == X.X86_OP_IMM:
            return j
        if j.mnemonic.startswith("j") or j.mnemonic in ("call", "ret"):
            return None
        if j.mnemonic not in ("mov", "movzx", "movsx", "movss", "lea", "movaps"):
            return None
        nxt += j.size
        k += 1
    return None


def zero_tests(f, field_base, disp, size):
    """[(access, compare, branch)]: each compare of the field against 0 in f"""
    out = []
    for at in f.order:
        i = f.ins[at]
        m = mem_of(i)
        if m is None or m.mem.disp != disp or m.mem.index or \
                i.reg_name(m.mem.base) != field_base or m.size != size:
            continue
        ops = i.operands
        if i.mnemonic == "cmp" and len(ops) == 2 and ops[1].type == X.X86_OP_IMM and \
                ops[1].imm == 0:
            br = branch_after(f, at)
            if br is not None:
                out.append((at, at, br))
            continue
        if i.mnemonic in ("mov", "movzx", "movsx") and ops[0].type == X.X86_OP_REG:
            r = ops[0].reg
            nxt = at + i.size
            for _ in range(4):
                j = f.ins.get(nxt)
                if j is None:
                    break
                jo = j.operands
                if j.mnemonic == "test" and len(jo) == 2 and jo[0].type == jo[1].type == \
                        X.X86_OP_REG and ct_same(i, r, j, jo[0].reg) and ct_same(i, r, j, jo[1].reg):
                    br = branch_after(f, nxt)
                    if br is not None:
                        out.append((at, nxt, br))
                    break
                if j.mnemonic == "cmp" and len(jo) == 2 and jo[0].type == X.X86_OP_REG and \
                        ct_same(i, r, j, jo[0].reg) and jo[1].type == X.X86_OP_IMM and jo[1].imm == 0:
                    br = branch_after(f, nxt)
                    if br is not None:
                        out.append((at, nxt, br))
                    break
                _rd, wr = j.regs_access()
                if any(ct_same(i, r, j, w) for w in wr) or j.mnemonic.startswith("j") or \
                        j.mnemonic in ("call", "ret"):
                    break
                nxt += j.size
    return out


def ct_same(i, r, j, s):
    """registers r of i and s of j are the same register (any width)"""
    import gen_integer_skips as gis
    return gis.canon(i, r) == gis.canon(j, s)


REG_FAMILY = {}
for _fam in (("rax", "eax", "ax", "al"), ("rbx", "ebx", "bx", "bl"), ("rcx", "ecx", "cx", "cl"),
             ("rdx", "edx", "dx", "dl"), ("rsi", "esi", "si", "sil"), ("rdi", "edi", "di", "dil"),
             ("rbp", "ebp", "bp", "bpl")) + tuple(
        ("r%d" % n, "r%dd" % n, "r%dw" % n, "r%db" % n) for n in range(8, 16)):
    for _r in _fam:
        REG_FAMILY[_r] = _fam[0]


def transient(f, start, stops, base, disp, bound=900):
    """every path from start re-arms [base + disp] with a value known to be
    nonzero (an immediate, or a register last set from one on that path)
    before a stop, a return or leaving the function.

    A store of the state bytes alone is no proof: the test can still run on
    the next tick (a handler outside any switch on them, a state that comes
    back to it, a store of the same state), and with the field resting at 0
    a "not yet" then runs the active path on N - 1 of every N ticks: an
    effect kept spawning (seen in play, 2026-10-12: smoke puffs piling up
    over a battle's enemies at 60 and 120). Neither is a store of 0, or of a
    register that holds 0 (a function's zero register)."""
    work, seen = [(start, ())], set()
    while work:
        at, consts = work.pop()
        if (at, consts) in seen:
            continue
        seen.add((at, consts))
        if len(seen) > bound or at in stops or at not in f.ins:
            return False
        i = f.ins[at]
        m = mem_of(i)
        known = dict(consts)
        if m is not None and m.access & 2 and i.mnemonic != "cmp" and \
                i.reg_name(m.mem.base) == base and not m.mem.index and m.mem.disp == disp:
            src = i.operands[1] if i.mnemonic == "mov" and len(i.operands) == 2 else None
            if src is not None and src.type == X.X86_OP_IMM and src.imm != 0:
                continue                # re-armed with a nonzero constant
            if src is not None and src.type == X.X86_OP_REG and \
                    known.get(REG_FAMILY.get(i.reg_name(src.reg))) not in (None, 0):
                continue                # re-armed from a register holding one
            return False
        if i.mnemonic in ("ret", "retf") or i.mnemonic == "jmp" and \
                i.operands[0].type == X.X86_OP_IMM and not f.entry <= i.operands[0].imm < f.end:
            return False
        # the constants registers hold along this path (a call returns in
        # rax and may change every volatile register)
        _rd, wr = i.regs_access()
        for w in wr:
            fam = REG_FAMILY.get(i.reg_name(w))
            if fam is not None:
                known.pop(fam, None)
        if i.mnemonic == "call":
            for fam in ("rax", "rcx", "rdx", "r8", "r9", "r10", "r11"):
                known.pop(fam, None)
        if i.mnemonic == "mov" and len(i.operands) == 2 and i.operands[0].type == X.X86_OP_REG \
                and i.operands[1].type == X.X86_OP_IMM:
            fam = REG_FAMILY.get(i.reg_name(i.operands[0].reg))
            if fam is not None:
                known[fam] = i.operands[1].imm
        elif i.mnemonic == "xor" and len(i.operands) == 2 and \
                i.operands[0].type == i.operands[1].type == X.X86_OP_REG and \
                i.operands[0].reg == i.operands[1].reg:
            fam = REG_FAMILY.get(i.reg_name(i.operands[0].reg))
            if fam is not None:
                known[fam] = 0
        nxt = tuple(sorted(known.items()))
        work.extend((s, nxt) for s in f.succ(i))
    return True


def field_written(f, start, stops, base, disp, bound=900):
    """the first store to [base + disp] on a path from start before a stop"""
    work, seen = [start], set()
    while work:
        at = work.pop()
        if at in seen or at in stops or at not in f.ins:
            continue
        seen.add(at)
        if len(seen) > bound:
            return None
        i = f.ins[at]
        m = mem_of(i)
        if m is not None and m.access & 2 and m.mem.disp == disp and                 i.reg_name(m.mem.base) == base and i.mnemonic != "cmp":
            return at
        work.extend(f.succ(i))
    return None


def write_spec(path, found):
    """manifest_rows spec lines: notyett for a timer family's countdown,
    notyet in the count row's group for the world's, by group; one row per
    flag source (two hits can share one)"""
    by_group, seen = collections.defaultdict(list), set()
    for r in found:
        if r["flag_at"] in seen or not r["group"]:
            continue
        seen.add(r["flag_at"])
        why = "%s: %s's countdown %s (%s): its zero side (%s) acted up to 3 ticks before " \
              "stock's next tick; between stock ticks it reads not yet%s" % (
                  r["function"], r["field"], r["countdown"], r["family"], r["effect"],
                  ", and the cycle it reloads keeps its stock length" if r["reload"] else "")
        if r["family"] in TIMERS:
            line = "notyett %s (0x%s,0x%s) | %s" % (r["flag_at"], r["not_yet"], r["dec_at"], why)
        elif r["family"].startswith("world_anims.h"):
            line = "notyet %s notyet:%s | %s" % (r["flag_at"], r["not_yet"], why)
        else:
            continue
        by_group[r["group"]].append(line)
    with open(path, "w", encoding="utf-8", newline="\n") as fo:
        fo.write("# early_countdowns.py --spec: a countdown's zero test read as not yet between "
                 "stock ticks\n")
        for g in sorted(by_group):
            fo.write("group %s\n" % g)
            for line in by_group[g]:
                fo.write(line + "\n")
    print("spec: %d rows in %s" % (sum(len(v) for v in by_group.values()), path))


def reaches(f, a, b, avoid=(), bound=4000):
    """b can be reached from a's successors without passing `avoid`"""
    work, seen = [n for n in f.succ(f.ins[a])], set()
    while work:
        x = work.pop()
        if x == b:
            return True
        if x in seen or x in avoid or x not in f.ins:
            continue
        seen.add(x)
        if len(seen) > bound:
            return False
        work.extend(f.succ(f.ins[x]))
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--spec", help="write manifest_rows spec lines for the hits")
    ap.add_argument("--check", action="store_true",
                    help="fail on an early zero test with neither a row nor a review")
    args = ap.parse_args()
    row_group = {}
    import gen_integer_skips as gis
    timer_ranges = [r for r in gis.patched_ranges() if r[2] in TIMERS]
    sites = list(csv.DictReader(open(os.path.join(DOCS, "sites.csv"), encoding="utf-8")))
    cov = {r["site"]: r for r in csv.DictReader(open(os.path.join(DOCS, "coverage.csv"),
                                                     encoding="utf-8"))}
    rows = world_rows(row_group)
    gated_fns = {a for a, k in rows.items() if k in ("gatefn", "gate0")}
    found, funcs, resting = [], {}, []
    stats = collections.Counter()
    for s in sites:
        if s["shape"] != "counter" or s["step"] != "-1":
            continue
        c = cov.get(s["site"], {})
        if c.get("status") != "covered" or not c.get("family", "").startswith(PACING):
            continue
        fn = int(s["function"], 16)
        if fn not in funcs:
            try:
                f = ct.Func(fn)
                f.postdominators()
                funcs[fn] = f
            except (SystemExit, Exception):
                funcs[fn] = None
        f = funcs[fn]
        if f is None:
            stats["no function"] += 1
            continue
        if not s["load"]:
            stats["no load"] += 1
            continue
        load, store = int(s["load"], 16), int(s["site"], 16)
        li = f.ins.get(load)
        m = mem_of(li) if li is not None else None
        if m is None or m.mem.index or m.mem.base in (0, X.X86_REG_RIP, X.X86_REG_RSP):
            stats["no field"] += 1
            continue
        base, disp, size = li.reg_name(m.mem.base), m.mem.disp, m.size
        stats["countdowns"] += 1
        for acc, cmp_at, br in zero_tests(f, base, disp, size):
            zero_side = br.operands[0].imm if ZERO_TAKEN[br.mnemonic] else br.address + br.size
            # before the decrement on the same tick: the test is the load
            # itself, or it reaches the load without passing the store
            before = acc == load or (acc != store and reaches(f, br.address, load, {store}))
            if not before:
                continue
            stop = {f.ipdom.get(br.address)} - {None}
            effect = ct.forced_walk(f, zero_side, stop | {load, store}, {})
            if not effect:
                continue
            if not transient(f, zero_side, stop | {load}, base, disp):
                stats["resting at 0"] += 1
                if (rows.get(cmp_at) or rows.get(acc)) in NOT_YET_KINDS and                         cmp_at not in RESTING_REVIEWED and acc not in RESTING_REVIEWED:
                    resting.append("%X in %X: %s countdown %s/%s rests at 0 under a %s row" % (
                        cmp_at, fn, "[%s + %X]" % (base, disp), s["load"], s["site"],
                        rows.get(cmp_at) or rows.get(acc)))
                continue
            if ec.event_gated([cmp_at]):
                stats["behind an event edge"] += 1
                continue
            reload = field_written(f, zero_side, stop | {load, store}, base, disp)
            gate = rows.get(cmp_at) or rows.get(acc) or ("gatefn" if fn in gated_fns else "")
            gated = gate in GATING or gate in ("gatefn",)
            if (gated or cmp_at in REVIEWED) and not args.all:
                stats["gated" if gated else "reviewed"] += 1
                continue
            fam = c["family"]
            # what paces it: a timer family's range over its load or store, or
            # a count row on its load .. store (the decrement or the store),
            # wins over the family coverage names for the candidate
            fam = next((label for lo, hi, label in timer_ranges
                        if lo <= store < hi or lo <= load < hi), fam)
            count_at = next((a for a in f.order if load <= a <= store and
                             rows.get(a) in ("count", "countlast", "count2")), None)
            if count_at is not None:
                fam = "world_anims.h"
            group = row_group.get(count_at) if fam == "world_anims.h" \
                else WORLD_GROUP.get(c.get("group"), "objects")
            # a world-paced countdown must be a count row's (a call or literal
            # family paces no integer countdown)
            if fam.startswith("world_anims.h") and count_at is None:
                group = ""
            found.append(dict(test="%X" % cmp_at, branch="%X %s" % (br.address, br.mnemonic),
                              function="%X" % fn, field="[%s + %X]/%d" % (base, disp, size),
                              countdown="%s/%s" % (s["load"], s["site"]),
                              family=fam, zero_side="%X" % zero_side,
                              effect=effect, reload="reload %X" % reload if reload else "",
                              gated=gate, flag_at="%X" % cmp_at,
                              not_yet="%X" % not_yet_side(br), dec_at=s["site"],
                              group=group or ""))
    # the register shape: a count row on the store alone, its flags or register read after
    for s in sites:
        if s["shape"] != "counter" or s["step"] != "-1" or s["load"] in (s["site"], ""):
            continue
        store = int(s["site"], 16)
        if rows.get(store) not in ("count", "count2", "countlast"):
            continue
        fn = int(s["function"], 16)
        f = funcs.get(fn)
        if f is None or store not in f.ins:
            continue
        si = f.ins[store]
        nxt = store + si.size
        for _ in range(4):
            j = f.ins.get(nxt)
            if j is None:
                break
            if j.mnemonic in ZERO_TAKEN and j.operands[0].type == X.X86_OP_IMM:
                if rows.get(store) and not args.all and rows.get(j.address) in GATING:
                    break
                # the event side: where a result at or below 0 goes
                zero_side = j.address + j.size if POSITIVE_TAKEN[j.mnemonic] else j.operands[0].imm
                stop = {f.ipdom.get(j.address)} - {None}
                effect = ct.forced_walk(f, zero_side, stop, {})
                src = flag_source(f, j)
                li = f.ins.get(int(s["load"], 16))
                lm = mem_of(li) if li is not None else None
                if lm is None or not transient(f, zero_side, stop | {int(s["load"], 16)},
                                               li.reg_name(lm.mem.base), lm.mem.disp):
                    stats["resting at 0 (register)"] += 1
                    if src is not None and rows.get(src) in NOT_YET_KINDS and                             src not in RESTING_REVIEWED:
                        resting.append("%X in %X: register countdown %s/%s rests at 0 under a "
                                       "%s row" % (src, fn, s["load"], s["site"], rows.get(src)))
                    break
                if src is not None and ec.event_gated([src]):
                    stats["behind an event edge (register)"] += 1
                    break
                if effect and src is not None and rows.get(src) not in GATING:
                    found.append(dict(test="%X" % j.address, branch="%X %s" % (j.address, j.mnemonic),
                                      function="%X" % fn, field="register",
                                      countdown="%s/%s" % (s["load"], s["site"]),
                                      family="world_anims.h count (store)", zero_side="%X" % zero_side,
                                      effect=effect, reload="", gated="", flag_at="%X" % src,
                                      not_yet="%X" % not_yet_side(j), dec_at=s["site"],
                                      group=row_group.get(store, "")))
                break
            if j.mnemonic.startswith("j") or j.mnemonic in ("call", "ret"):
                break
            _rd, wr = j.regs_access()
            if any(j.reg_name(w) in ("rflags", "eflags") for w in wr):
                if j.mnemonic in ("test", "cmp"):
                    nxt += j.size
                    continue
                break
            nxt += j.size
    for k, v in sorted(stats.items()):
        print("%s: %d" % (k, v))
    print("early zero tests: %d" % len(found))
    print("by family: %s" % dict(collections.Counter(r["family"] for r in found)))
    print("reloaded at the zero test: %d" % sum(bool(r["reload"]) for r in found))
    for r in found:
        print("  %(test)s %(branch)-12s in %(function)s %(field)-18s countdown %(countdown)s "
              "(%(family)s) zero -> %(zero_side)s: %(effect)s %(reload)s %(gated)s" % r)
    if args.spec:
        write_spec(args.spec, found)
    for r in resting:
        print("RESTING " + r)
    if args.check:
        bad = [r for r in found if not r["gated"] and int(r["test"], 16) not in REVIEWED]
        for r in bad:
            print("OPEN %(test)s in %(function)s: %(field)s countdown %(countdown)s" % r)
        print("early countdowns: %d open, %d not-yet rows on a countdown resting at 0" % (
            len(bad), len(resting)))
        return 1 if bad or resting else 0
    if args.csv:
        with open(args.csv, "w", encoding="utf-8", newline="") as fo:
            wr = csv.DictWriter(fo, fieldnames=list(found[0]) if found else ["test"])
            wr.writeheader()
            wr.writerows(found)


if __name__ == "__main__":
    sys.exit(main())
