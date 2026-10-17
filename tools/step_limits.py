#!/usr/bin/env python3
"""Tests of a step the patch scales against a limit it does not.

    .venv/Scripts/python tools/step_limits.py [--csv OUT] [--only FN,...]
    .venv/Scripts/python tools/step_limits.py --check [--break limsq]

At 120 a row makes a step s times stock's (s = 1/N) and the tick runs N
times as often. A test of that step against a limit in stock units then
decides differently: the brush (16C7E0) drops a cursor move whose squared
length is under 16 and puts the cursor back on its last point, and a
gamepad's quarter step was always under it, so the cursor did not move at
120 (found in play, 2026-10-15; the limits are `limsq` rows now).

Every comiss/ucomiss/comisd/ucomisd and minss/maxss/minsd/maxsd in a function
where the patch scales a value is read: each side is sliced backwards
(trace_steps.Slicer: both sides of every branch, stack slots, the kernel's
cVec lanes) and written as a polynomial in s over the slice's leaves.
s goes where each conversion puts it: a world row's operand, result or
literal (src, srcx, pre, dst, step, dstarg, argscale, dstn, lin, sq, limsq,
blend, blendr, srcblend, immstore), phase_steps.h's literals, the launch
velocities' 1 / s, the air and swim accelerations' second time scale, the
slope and animation detours, a read of the time scale and the run's
kJogParams. A global the function stored earlier on the way is its stored
value, so x - prev cancels to the step (16DB2D); cVec::squareMag and
GetLength are the sum of the lanes' squares. A test is flagged when one side
of some pairing of the two slices' alternatives has every term at s^k
(k != 0) and the other side is nonzero and free of s: at 120 they compare as
stock never does. A side that is 0 is a sign test and does not depend on s.

The slices do not follow a path: alternatives of the two sides pair freely,
so a pairing can be one the game never takes (the brush's mouse limit 0.1
with a gamepad's move), and a field the slice cannot see into reads free of
s even when the game keeps it per frame (pl00 +E48). REVIEWED lists each
flagged test, the s-free sides it was read with and why it is right.
--check (in tools/run_suite.sh) fails on a flagged test or pairing REVIEWED
does not have, and on an entry no longer flagged; --break limsq reads the
brush's limits unscaled and must fail.
"""
import argparse
import csv
import hashlib
import os
import struct
import sys
import time

from capstone import x86_const as X

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import trace_steps as ts  # noqa: E402

# where a world row puts its s on the slice, and the power
ROW = {"src": ("right", 1), "srcx": ("srcx", 1), "pre": ("left", 1), "dst": ("result", 1),
       "step": ("result", 1), "dstarg": ("result", 1), "argscale": ("result", 1),
       "dstn": ("result", -1), "lin": ("leaf", 1), "sq": ("leaf", 2), "blend": ("leaf", 1),
       "limsq": ("leaf", 2), "blendr": ("result", 1), "srcblend": ("right", 1),
       "immstore": ("leaf", 1)}
# the other families that scale a value continuously
FAMILY = {"phase_steps.h": ("leaf", 1), "launch_velocities.h": ("result", -1),
          "kAirAccelSites": ("leaf", 1), "kSwimAccelSites": ("leaf", 1),
          "kSlopeSites": ("result", 1), "kAnimSites": ("result", 1)}
TESTS = {"comiss", "ucomiss", "comisd", "ucomisd"}
CLAMPS = {"minss", "maxss", "minsd", "maxsd"}
MAG = {"?squareMag@cVec@math@wk@@QEBAMXZ": ("sq", "rcx"),
       "?GetLength@cVec@math@wk@@SAMAEBV123@@Z": ("len", "rcx"),
       "?DotSame@cVec@math@wk@@SAMAEBV123@@Z": ("sq", "rcx")}
MAXT, MAXALT, MAXPAIR = 48, 24, 10
UNK = (None, ("?",))          # a term of unknown power

SCALED = "a scaled constant"     # the s side is a constant a row scaled: any s-free side
TURN_CLAMP = ("a turn clamp: the angle left to turn, free of s, limited to +- the most a "
              "tick turns times s (an argscale or lin row): the per-frame step of the "
              "approach, the right form")
E48 = ("pl00 +E48 is a per-frame speed (the port moves her by it every tick): its tests "
       "against a limit the rows put in the same units (srcx divides it by s, lin scales "
       "the limit), read when each row was added")
# test -> (the s-free sides it was read with, why it is right)
REVIEWED = {
    0x16DC73: (("0.1", SCALED),
               "the brush's dead zone, 16 x s^2 (limsq 16DB50): against it a gamepad's move "
               "(s x stock's) is kept as stock's is; the mouse's own glide onto the pointer "
               "at rest (7E7204, an unpaced 0.7 blend) is per frame, not scaled, so at 120 it "
               "settles within 1 instead of 4 and records a point or two more (ink drains at "
               "most once a stock tick); 0.1 is the mouse's limit while it moves (16DC3F), "
               "never with a still mouse's gamepad move"),
    0x16DCA7: (("0.1", SCALED), "the brush's move back, 64 x s^2 (limsq 16DB59): as 16DC73"),
    0x27E7A4: (("10",), "em2d's step (this tick's move from 27E79E) against |10|: srcx 27E7A4 "
                        "compares it / s with stock's 10"),
    0x27E9CC: ((SCALED,), "em2d's step tests, the limit 10 x s (lin 27E9C4)"),
    0x27EA64: ((SCALED,), "em2d's step tests, the limit 10 x s (lin 27E9C4)"),
    0x3B46B8: (("f[rdi+E18]",), "pl00 +E18 is a saved +E48 (3B3FF0: E18 = E48), per frame "
                                "like it; the port tests it against 5 x the time scale"),
    0x4874D0: ((SCALED,), "cDogLikeHm's heading: 0.1 x s (lin 4874B6) is both the step and "
                          "the snap's bound, so it snaps within one step as stock does"),
}
for _a, _side in ((0x20E264, "wrap@20E252"), (0x20E26C, "wrap@20E252"),
                  (0x20E2BE, "wrap@20E2AC"), (0x20E2C6, "wrap@20E2AC"),
                  (0x5BCA4F, SCALED), (0x5BCA5C, SCALED), (0x5C24B1, SCALED), (0x5C24BE, SCALED)):
    REVIEWED[_a] = ((_side,), TURN_CLAMP)
# eight classes' copies of one turn helper: the angle to a point (the call at +47) less
# the facing +B0, clamped, then the heading's own clamp (the wrap at +B8)
for _fn in (0x26B920, 0x2836F0, 0x2B5250, 0x2C9300, 0x5CCD90, 0x5DD910, 0x5EA280, 0x5F4730):
    for _a in (_fn + 0x5E, _fn + 0x66):
        REVIEWED[_a] = (("callret@%X + f[rbx+B0]" % (_fn + 0x47),), TURN_CLAMP)
    for _a in (_fn + 0xCA, _fn + 0xD2):
        REVIEWED[_a] = (("wrap@%X" % (_fn + 0xB8),), TURN_CLAMP)
for _a, _side in ((0x3A7874, "3"), (0x3B2128, SCALED), (0x3B2DFA, "f[rdi+E48]"),
                  (0x3B5B0C, SCALED), (0x3CA808, "1"), (0x3CE9B7, "0.05"), (0x3CE9CC, SCALED),
                  (0x476BE2, "0.1"), (0x476E1B, "1"), (0x47AA1C, "f[rsi+E48]")):
    REVIEWED[_a] = ((_side,), E48)


# -- polynomials in s: {(power, (symbols...)): coefficient} -----------------------

def P(spow, *syms, c=1.0):
    return {(spow, tuple(sorted(syms))): c}


def norm(p):
    return {k: c for k, c in p.items() if abs(c) > 1e-12}


def add(p, q, sign=1.0):
    r = dict(p)
    for k, c in q.items():
        r[k] = r.get(k, 0.0) + sign * c
    return norm(r)


def mul(p, q, a=0):
    if UNK in p or UNK in q:
        return {UNK: 1.0}
    r = {}
    for (s1, y1), c1 in p.items():
        for (s2, y2), c2 in q.items():
            k = (s1 + s2, tuple(sorted(y1 + y2)))
            r[k] = r.get(k, 0.0) + c1 * c2
    r = norm(r)
    return r if len(r) <= MAXT else opaque(r, "big", a)


def scale(p, k):
    return {(None if s is None else s + k, y): c for (s, y), c in p.items()}


def powers(p):
    return {s for s, _y in p}


def pure(p):
    ps = powers(p)
    return next(iter(ps)) if len(ps) == 1 and None not in ps else None


def opaque(p, tag, a):
    """a value with p's one power, named by the instruction that made it"""
    d = pure(p)
    return {UNK: 1.0} if d is None else P(d, "%s@%X" % (tag, a))


def text(p):
    """a polynomial as text, every term, in a fixed order"""
    out = []
    for (sp, y), c in sorted(p.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        coef = ("%g" % c) if not y or abs(c) != 1 else ("-" if c < 0 else "")
        out.append("%s%s%s" % (coef, "*" if y and coef not in ("", "-") else "", "*".join(y)) +
                   ("*s^%g" % sp if sp else ""))
    return " + ".join(out) if out else "0"


def fbits(t):
    """`mov dword [m], imm32` stores a float's bits: read that way"""
    if isinstance(t, tuple) and t and t[0] == "imm" and isinstance(t[2], int) and             0 <= t[2] < 1 << 32:
        return ("fbits", t[1], struct.unpack("<f", struct.pack("<I", t[2]))[0])
    return t


def leaf_key(t):
    k = t[0]
    if k == "field":
        return "f[%s+%X]%s" % (t[2], t[3], "[%s]" % t[4] if t[4] else "")
    if k == "global":
        return "g%X" % t[2]
    if k == "stackin":
        return "in%X" % t[2]
    if k == "param":
        return "p%s" % t[1]
    if k == "rate":
        return "rate:%s" % t[2]
    return "%s@%X" % (k, t[1]) if len(t) > 1 and isinstance(t[1], int) else str(k)


class Eval:
    """the alternatives of a slice, each a polynomial in s"""

    def __init__(self, tr, ignore=()):
        self.tr, self.ignore = tr, set(ignore)
        self.memo, self.gmemo = {}, {}

    def row(self, a):
        """(where, power) of the conversion at instruction a, or None"""
        r = self.tr.rows.get(a)
        if r is not None and r["status"] == "selected" and r["kind"] in ROW:
            return None if r["kind"] in self.ignore else ROW[r["kind"]]
        for fam, _k in self.tr.patch_at(a):
            if fam in FAMILY:
                return FAMILY[fam]
        return None

    def alts(self, t, sl, depth=0):
        key = (id(t), id(sl))
        hit = self.memo.get(key)
        if hit is not None and hit[0] is t:
            return hit[1]
        out, seen = [], set()
        for p in self._alts(t, sl, depth):
            k = frozenset(p.items())
            if k not in seen:
                seen.add(k)
                out.append(p)
        # the pure ones first: a cap must not drop the step's own alternative
        out.sort(key=lambda p: (len(powers(p)), None in powers(p), len(p), text(p)))
        out = out[:MAXALT]
        self.memo[key] = (t, out)
        return out

    def _alts(self, t, sl, depth):
        if depth > 60 or not isinstance(t, tuple) or not t:
            return [{UNK: 1.0}]
        k = t[0]
        a = t[1] if len(t) > 1 and isinstance(t[1], int) else None
        rw = self.row(a) if a is not None else None
        if k == "phi":
            r = []
            for x in t[1]:
                r += self.alts(x, sl, depth + 1)
            return r
        if k == "imm":
            return [P(0, c=float(t[2])) if t[2] else {}]
        if k == "fbits":
            return [P(0, c=t[2]) if t[2] else {}]
        if k == "const":
            v = t[3]
            p = ({} if v == 0 else P(0, c=float(v))) if isinstance(v, float) else P(0, "k%X" % t[2])
            if rw and rw[0] == "leaf":
                p = scale(p, rw[1])
            return [p]
        if k == "rate":
            p = P(1, "ts") if t[2] == "time scale" else P(0, leaf_key(t))
            if rw and rw[0] == "leaf":
                p = scale(p, rw[1])
            return [p]
        if k == "global" and t[2] in self.tr.data_params:
            return [P(1, leaf_key(t))]
        if k == "global" and sl is not None:
            stored = self.global_stores(sl, a, t[2])
            if stored:
                r = []
                for v in stored:
                    r += self.alts(v, sl, depth + 1) if v is not None else [P(0, leaf_key(t))]
                return r
        if k == "stack":
            return self.alts(fbits(t[3]), sl, depth + 1)
        if k.startswith("lane"):
            return self.alts(t[2], sl, depth + 1)
        if k == "wrap":
            return [opaque(p, "wrap", a) for p in self.alts(t[2], sl, depth + 1)]
        if k == "callret":
            tgt = t[3]
            m = MAG.get(tgt) if isinstance(tgt, str) else None
            if m is not None and sl is not None and sl.stack is not None:
                lanes = [self.alts(sl.lane_of(a, m[1], c, 0), sl, depth + 1) for c in range(3)]
                r = []
                for x in lanes[0][:3]:
                    for y in lanes[1][:3]:
                        for z in lanes[2][:3]:
                            s2 = add(add(mul(x, x, a), mul(y, y, a)), mul(z, z, a))
                            if m[0] == "len":
                                d = pure(s2)
                                s2 = P(d / 2, "len@%X" % a) if d is not None and d % 2 == 0 \
                                    else {UNK: 1.0}
                            r.append(s2)
                return r or [{UNK: 1.0}]
            return [P(0, leaf_key(t))]
        if k == "conv":
            inner = self.alts(t[3], sl, depth + 1)
            if rw and rw[0] == "result":
                inner = [scale(p, rw[1]) for p in inner]
            return inner
        if k == "op":
            m, left, right = t[2], t[3], t[4]
            L = self.alts(left, sl, depth + 1) if left is not None else [{}]
            R = self.alts(right, sl, depth + 1) if right is not None else [{}]
            if rw:
                where, pw = rw
                if where == "right" or (where == "srcx" and m in ("addss", "subss")):
                    R = [scale(p, pw) for p in R]
                elif where == "left":
                    L = [scale(p, pw) for p in L]
            if m in ("mulss", "mulsd") and left == right:
                out = [mul(x, x, a) for x in L]       # a square stays on one path
            else:
                out = [self.binop(m, x, y, right, a) for x in L[:MAXPAIR] for y in R[:MAXPAIR]]
            if rw and rw[0] == "result":
                out = [scale(p, rw[1]) for p in out]
            return out
        if k in ("field", "global", "param", "stackin", "callmem", "table", "lea", "addr",
                 "stackaddr", "flag", "clobber"):
            return [P(0, leaf_key(t))]
        return [{UNK: 1.0}]

    def global_stores(self, sl, at, rva):
        """the values the function stored to the global rva on the way to the
        load at `at` (None for a path from the entry); [] if it stores none"""
        key = (sl.fn.root, at, rva)
        if key in self.gmemo:
            return self.gmemo[key]
        fn, out, seen, found = sl.fn, [], set(), False
        work = list(fn.preds.get(at, []))
        while work:
            a = work.pop()
            if a in seen:
                continue
            seen.add(a)
            si = fn.ins[a]
            hit = None
            for so in si.operands:
                if so.type == X.X86_OP_MEM and so.access & 2 and ts.gtc.rip_target(si, so) == rva:
                    hit = so
            if hit is not None:
                found = True
                out.append(fbits(sl.stored(si, hit, 0)) if si.mnemonic in ts.MOVES else None)
                continue
            ps = fn.preds.get(a, [])
            if not ps:
                out.append(None)
            work.extend(ps)
        res = out if found else []
        self.gmemo[key] = res
        return res

    def binop(self, m, x, y, right, a):
        if m in ("addss", "addsd", "add", "addps", "paddd"):
            return add(x, y)
        if m in ("subss", "subsd", "sub", "subps", "psubd"):
            return add(x, y, -1.0)
        if m in ("mulss", "mulsd", "mulps", "imul"):
            return mul(x, y, a)
        if m in ("divss", "divsd", "divps"):
            if not y:
                return {UNK: 1.0}
            if len(y) == 1 and UNK not in y:
                (s2, y2), c2 = next(iter(y.items()))
                return mul(x, {(-s2, tuple("1/" + v for v in y2)): 1.0 / c2}, a)
            dx, dy = pure(x), pure(y)
            return P(dx - dy, "div@%X" % a) if dx is not None and dy is not None else {UNK: 1.0}
        if m in ("sqrtss", "sqrtsd"):
            d = pure(x)
            return P(d / 2, "sqrt@%X" % a) if d is not None and d % 2 == 0 else {UNK: 1.0}
        if m in ("andps", "andpd"):
            return opaque(x, "abs", a) if x else {}   # abs by a sign mask keeps the power
        if m in ("xorps", "xorpd"):
            if right is not None and right[0] == "const":
                return {k: -c for k, c in x.items()}  # a sign flip
            return {UNK: 1.0}
        if m in CLAMPS:
            dx, dy = pure(x), pure(y)
            return P(dx, "clamp@%X" % a) if dx is not None and dx == dy else {UNK: 1.0}
        return {UNK: 1.0}


def side_key(text_):
    """an s-free side as REVIEWED names it: its text, or #hash for a long one"""
    return text_ if len(text_) <= 60 else "#" + hashlib.sha1(text_.encode()).hexdigest()[:8]


def pairing(px, py):
    """(verdict, the s-free side) when the pair decides differently at 120"""
    if not px or not py:
        return None                    # a test against 0 does not depend on s
    dx, dy = pure(px), pure(py)
    if dx is None or dy is None or dx == dy:
        return None
    if dx != 0 and dy != 0:
        return "s^%g vs s^%g" % (dx, dy), ""
    step, free = (px, py) if dx else (py, px)
    if all(not y for _s, y in step):
        return "s^%g vs a limit" % (dx or dy), SCALED    # a constant a row scaled
    return "s^%g vs a limit" % (dx or dy), side_key(text(free))


def roots_scaled(tr):
    roots = set()
    for site, r in tr.rows.items():
        if r["status"] == "selected" and r["kind"] in ROW:
            fn = tr.func(site)
            if fn is not None:
                roots.add(fn.root)
    for s, _e, fam in tr.ranges:
        if fam in FAMILY:
            fn = tr.func(s)
            if fn is not None:
                roots.add(fn.root)
    return roots


def survey(tr, ignore=(), only=None):
    """[(fn, site, instruction, {(verdict, free side)}, left tree, right tree)], counts"""
    ev = Eval(tr, ignore)
    roots = only if only else roots_scaled(tr)
    found, ntests = [], 0
    for root in sorted(roots):
        fn, sl = tr.func(root), tr.slicer(root)
        if fn is None or sl is None:
            continue
        for a in fn.order:
            i = fn.ins[a]
            m, ops = i.mnemonic, i.operands
            if (m not in TESTS and m not in CLAMPS) or len(ops) != 2 or \
                    ops[0].type != X.X86_OP_REG:
                continue
            ntests += 1
            lt = sl.value(a, ts.gtc.reg_key(i, ops[0].reg))
            rt = sl.opnd(i, ops[1], 0)
            L, R = ev.alts(lt, sl), ev.alts(rt, sl)
            rw = ev.row(a)
            if rw and rw[0] == "srcx" and m in TESTS:
                L = [scale(p, -rw[1]) for p in L]     # srcx compares xmmD / s
            pairs = {v for x in L for y in R for v in [pairing(x, y)] if v}
            if pairs:
                found.append((root, a, "%s %s" % (m, i.op_str), pairs, lt, rt))
    return found, len(roots), ntests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--break", dest="broken", choices=("limsq",),
                    help="read the brush's limits unscaled: --check must fail")
    ap.add_argument("--only", default="", help="functions, comma-separated hex")
    ap.add_argument("--csv", default=None)
    args = ap.parse_args()
    t0 = time.time()
    tr = ts.Tracer()
    only = {int(x, 16) for x in args.only.split(",") if x} or None
    found, nfn, ntests = survey(tr, ignore=("limsq",) if args.broken else (), only=only)
    render = ts.Render(tr, limit=260)
    problems, seen = [], set()
    for root, a, ins, pairs, lt, rt in found:
        seen.add(a)
        rv = REVIEWED.get(a)
        new = sorted(p for p in pairs if rv is None or p[1] not in rv[0])
        tag = "PROBLEM " if new else "reviewed"
        print("%s %X %X  %-38s %s" % (tag, root, a, ins,
                                       " | ".join("%s: %s" % p for p in sorted(pairs))[:300]))
        if new:
            problems.append("%X %s: %s" % (a, ins, "; ".join("%s against %s" % p for p in new)))
    if only is None:
        for a in sorted(set(REVIEWED) - seen):
            problems.append("stale entry %X: no longer flagged" % a)
            print("PROBLEM  stale entry %X" % a)
    print("%d functions, %d tests and clamps, %d flagged: %d reviewed, %d problems (%.0f s)" % (
        nfn, ntests, len(found), len(found) - sum(1 for p in problems if not p.startswith("stale")),
        len(problems), time.time() - t0))
    for p in problems:
        print("  " + p)
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["fn", "site", "instruction", "pairings", "reviewed", "left", "right"])
            for root, a, ins, pairs, lt, rt in found:
                w.writerow(["%X" % root, "%X" % a, ins,
                            " | ".join("%s: %s" % p for p in sorted(pairs)),
                            REVIEWED[a][1] if a in REVIEWED else "",
                            render(lt)[:260], render(rt)[:260]])
    if args.check and problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
