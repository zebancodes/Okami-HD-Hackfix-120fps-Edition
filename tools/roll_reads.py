#!/usr/bin/env python3
"""Read random_rolls.csv's pending draws: where each runs and what it feeds.

    .venv/Scripts/python tools/roll_reads.py FUNC [FUNC ...]     # reading view
    .venv/Scripts/python tools/roll_reads.py --all OUT.json      # facts for every pending draw
    .venv/Scripts/python tools/roll_reads.py --site SITE [...]   # the facts of single draws

A draw changes with the frame rate only when it is drawn more often at 120
than at 30 and what it decides or sets acts on each draw: a per-tick chance
of an action (`rand < p` every tick: four times the actions), a per-tick
spawn, a per-tick re-roll that something integrates. A draw made once per
event (a state's set-up block, a motion's end that changes the state, an
integer frame crossing, an expired countdown, a hit) is right at any rate as
long as the event is. For each draw this prints:

* `once`: once_blocks' proof, extended to switch tables: the draw can be
  reached only while a phase byte [R + d] == v (a je/jne on the byte, or the
  case of a `switch (byte)` whose table sends only v to that target) and
  every path from it to a return writes the byte with something else;
* `end`, `cross`, `state`: chance_trials' dominating motion-advance "ended"
  answer, integer frame crossing, and store of the actor's state bytes;
* `cmp`: the compares the draw (or a value computed from it) reaches, with
  the branch, and the probability of the taken side where it can be read;
* `store`/`arg`/`ret`: where a value computed from the draw is stored
  outside the stack, which call takes it as an argument, or that the
  function returns it;
* the function's roots: its callers up to the vtable slots that reach them
  (class[slot]; RTTI names from rtti_classes.txt).

Verdicts go to docs/animation/followup_reviews.csv (inventory
random_rolls.csv); tools/survey_fps_followups.py merges them into
random_rolls.csv.
"""
import bisect
import collections
import csv
import json
import os
import pickle
import re
import struct
import sys

import capstone
from capstone import x86 as X

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import chance_trials as ct  # noqa: E402
import gen_turn_callers as gtc  # noqa: E402
import once_blocks as ob  # noqa: E402
import read_candidates as rc  # noqa: E402

DOCS = os.path.join(os.path.dirname(HERE), "docs", "animation")
TBL32 = re.compile(r"^(\w+), dword ptr \[(\w+) \+ (\w+)\*4 \+ (0x[0-9a-f]+)\]$")
TBL8 = re.compile(r"^(\w+), byte ptr \[(\w+) \+ (\w+) \+ (0x[0-9a-f]+)\]$")


# ---- the image, its functions and the call graph ---------------------------

class Image:
    def __init__(self):
        self.img, self.secs, _f, _sha = gtc.load_image()
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self.md.detail = True
        self.roots, self.starts, _e = gtc.pdata_roots(self.img, self.secs)
        c = pickle.load(open(rc.CACHE, "rb"))
        self.callers = c["callers"]
        self.ptrs = c["ptrs"]
        self.text = min(lo for lo, hi, n in c["secs"] if n == ".text"), \
            max(hi for lo, hi, n in c["secs"] if n == ".text")
        src = open(rc.DECOMP, encoding="utf-8", errors="replace").read()
        self.dstarts = sorted(int(m.group(1), 16) for m in rc.FUNC_HDR.finditer(src))
        self.vt = {}
        for line in open(os.path.join(HERE, "rtti_classes.txt")):
            p = line.split()
            if len(p) >= 3:
                m = re.match(r"\.\?AV(.+?)@@", p[1])
                self.vt[int(p[0], 16)] = (m.group(1) if m else p[1]) + \
                    ("" if p[2] == "off=0" else "@" + p[2][4:])
        self._fn = {}

    def dstart(self, a):
        k = bisect.bisect_right(self.dstarts, a) - 1
        return self.dstarts[k] if k >= 0 else None

    def func(self, at):
        """(gtc.Func, Slicer, {indirect jmp: [exact targets]}, switch gates)
        of the pdata function containing `at`"""
        k = bisect.bisect_right(self.starts, at) - 1
        root, frags = self.roots[self.starts[k]]
        if root not in self._fn:
            fn = gtc.Func(self.img, root, frags, self.md)
            sl = gtc.Slicer(self.img, self.secs, fn)
            ind, sw = switches(self, fn, sl)
            self._fn[root] = (fn, sl, ind, sw)
        return self._fn[root]

    def vslot(self, r):
        lo, hi = self.text
        k = r
        while k >= 8 and k not in self.vt and \
                lo <= struct.unpack_from("<Q", self.img, k - 8)[0] - rc.BASE < hi:
            k -= 8
        return self.vt.get(k, "vt%X" % k), (r - k) // 8

    def roots_of(self, fn, depth=6, limit=24):
        """paths from `fn` up its direct callers to the vtable slots (or
        data words) that reach them"""
        out, seen, work = [], set(), [(fn, ())]
        while work and len(out) < limit:
            f, path = work.pop(0)
            if f in seen:
                continue
            seen.add(f)
            chain = " <- ".join("%X" % x for x in path + (f,))
            for r in self.ptrs.get(f, []):
                cls, slot = self.vslot(r)
                out.append("%s @ %s[%d]" % (chain, cls, slot))
            cs = [self.dstart(s) for s in self.callers.get(f, [])]
            if not cs and not self.ptrs.get(f):
                out.append("%s @ (no refs)" % chain)
            if len(path) >= depth:
                if cs:
                    out.append("%s @ (deeper)" % chain)
                continue
            for cf in cs:
                if cf is not None and cf not in seen:
                    work.append((cf, path + (f,)))
        return out


# ---- switch tables ------------------------------------------------------------

def switches(im, fn, sl):
    """For each `jmp reg` of a jump table: its exact targets, and the case
    values that reach each target when the table's index is a phase byte
    (movzx of [R + d], less what the chain subtracted).
    Returns ({jmp: [targets]}, {(R, d, v): [(jmp, target)]})."""
    ind, gates = {}, collections.defaultdict(list)
    img = im.img
    for j in fn.indirect:
        back = ob._straight_back(fn, j)
        load32 = next((i for i in back if i.mnemonic == "mov" and TBL32.match(i.op_str)), None)
        if load32 is None:
            continue
        g = TBL32.match(load32.op_str)
        t32 = int(g.group(4), 16)
        idx = gtc.REG64.get(g.group(3), g.group(3))
        # a byte table in front: movzx idx, byte [base + i + T8]
        load8 = None
        for i in back:
            if i.address >= load32.address:
                continue
            if idx in gtc.writes(i):
                if i.mnemonic == "movzx" and TBL8.match(i.op_str):
                    load8 = i
                break
        targets = []
        k = 0
        limit = 1024
        while k < limit:
            t = struct.unpack_from("<I", img, t32 + 4 * k)[0]
            if t not in fn.ins:
                break
            targets.append(t)
            k += 1
        if not targets:
            continue
        ind[j] = sorted(set(targets))
        if load8 is not None:
            g8 = TBL8.match(load8.op_str)
            t8 = int(g8.group(4), 16)
            src = gtc.REG64.get(g8.group(3), g8.group(3))
            at, reg = load8.address, src
            # the byte table's length: up to the first entry past the dword table
            byte_of = []
            for v in range(256):
                e = img[t8 + v]
                if e >= len(targets):
                    break
                byte_of.append(e)
            cases = {v: targets[e] for v, e in enumerate(byte_of)}
        else:
            at, reg = load32.address, idx
            cases = dict(enumerate(targets))
        origin = byte_origin(sl, at, reg)
        if origin is None:
            continue
        rb, d, kk = origin
        by_target = collections.defaultdict(list)
        for v, t in cases.items():
            by_target[t].append(v + kk)
        for t, vs in by_target.items():
            if len(vs) == 1 and 0 <= vs[0] <= 0xFF:
                gates[(rb, d, vs[0])].append((j, t))
    return ind, gates


def _succs(fn, i, ind, orphan):
    a = i.address
    if a in ind:
        return ind[a]
    if a in orphan:
        return orphan[a]
    return fn.succs(i)


def byte_origin(sl, at, reg):
    """(the base's value, d, k) when `reg` just before `at` is, on every path,
    the byte [R + d] as a movzx loaded it, less k (a switch chain's `sub`,
    `dec`); else None. The slicer follows the register across blocks, which
    once_blocks' straight-line search does not (compares at jump targets)."""
    t = sl.value(at, reg)
    k = 0
    while t is not None and t[0] == "op" and t[2] in ("sub", "add", "dec", "inc"):
        r = t[4]
        if t[2] in ("dec", "inc"):
            k += 1 if t[2] == "dec" else -1
        elif r is not None and r[0] == "imm":
            k += r[2] if t[2] == "sub" else -r[2]
        else:
            return None
        t = t[3]
    if t is None or t[0] != "conv" or t[2] != "movzx" or t[3][0] != "field":
        return None
    load = t[3][1]
    i = sl.fn.ins.get(load)
    if i is None or i.operands[1].type != X.X86_OP_MEM or i.operands[1].size != 1:
        return None
    f = ob._field(i, i.operands[1])
    if f is None:
        return None
    return ob._base(sl, load, f[0]), f[1], k


def _const(sl, at, reg):
    """the integer constant `reg` holds before `at` on every path (an
    immediate move or `xor r, r`), else None"""
    t = sl.value(at, reg)
    if t is None:
        return None
    if t[0] == "imm":
        return t[2]
    if t[0] == "opaque":
        i = sl.fn.ins.get(t[1])
        if i is not None and i.mnemonic in ("xor", "sub") and len(i.operands) == 2 and \
                all(o.type == X.X86_OP_REG for o in i.operands) and \
                i.operands[0].reg == i.operands[1].reg:
            return 0
    return None


def slice_gates(fn, sl):
    """once_blocks.gates, with the compared register's origin found by the
    slicer: {(base, d, v): [(je/jne, successor taken only while == v)]}"""
    out = collections.defaultdict(list)
    for a in fn.order:
        j = fn.ins[a]
        if j.mnemonic not in ("je", "jne") or j.operands[0].type != X.X86_OP_IMM:
            continue
        setter = None
        for i in ob._straight_back(fn, a):
            if ob._writes_flags(i):
                setter = i
                break
        if setter is None:
            continue
        ops = setter.operands
        m = setter.mnemonic
        if m == "cmp" and len(ops) == 2 and ops[0].type == X.X86_OP_MEM and \
                ops[0].size == 1 and ops[1].type == X.X86_OP_REG:
            # `cmp byte [R + d], sil` with sil a known constant (`xor esi, esi`)
            k = _const(sl, setter.address, gtc.reg_key(setter, ops[1].reg))
            fl = ob._field(setter, ops[0])
            if k is not None and fl is not None and 0 <= k <= 0xFF:
                taken, fall = j.operands[0].imm, a + j.size
                if taken != fall:
                    out[(ob._base(sl, setter.address, fl[0]), fl[1], k)].append(
                        (a, taken if j.mnemonic == "je" else fall))
            continue
        if not ops or ops[0].type != X.X86_OP_REG:
            continue
        reg = gtc.reg_key(setter, ops[0].reg)
        if m == "test":
            if len(ops) != 2 or ops[1].type != X.X86_OP_REG or gtc.reg_key(setter, ops[1].reg) != reg:
                continue
            add = 0
        elif m in ("cmp", "sub") and len(ops) == 2 and ops[1].type == X.X86_OP_IMM:
            add = ops[1].imm
        elif m == "dec":
            add = 1
        else:
            continue
        o = byte_origin(sl, setter.address, reg)
        if o is None:
            continue
        base, d, k = o
        v = k + add
        if not 0 <= v <= 0xFF:
            continue
        taken, fall = j.operands[0].imm, a + j.size
        if taken != fall:
            out[(base, d, v)].append((a, taken if j.mnemonic == "je" else fall))
    return out


STATE = (0xE34, 0xE35, 0xE36, 0xE37)


def _trunc_field(sl, at, reg):
    """(base, d) when `reg` before `at` is (int) of the float field [R + d]"""
    t = sl.value(at, reg)
    if t is None or t[0] != "conv" or not t[2].startswith("cvtt") or t[3][0] != "field":
        return None
    i = sl.fn.ins.get(t[3][1])
    if i is None:
        return None
    op = next((o for o in i.operands if o.type == X.X86_OP_MEM), None)
    f = ob._field(i, op) if op is not None else None
    return (ob._base(sl, i.address, f[0]), f[1]) if f else None


_ROWS = {}


def world_rows():
    """{site: kind} of docs/animation/world_anims.csv"""
    if not _ROWS:
        for r in csv.DictReader(open(os.path.join(DOCS, "world_anims.csv"), encoding="utf-8")):
            _ROWS[int(r["site"], 16)] = r["kind"]
    return _ROWS


GATING = ("notyet", "notyetb", "notyetneg", "notyetend", "hold", "notyett")


def paced_guard(f, site):
    """the nearest dominating conditional branch whose compare has a
    world_anims gating row (notyet, notyetb, notyetneg: between stock ticks
    the compare reads the held side), as (compare, kind); a draw below it
    runs only when the paced test passes, at stock cadence. Also a gatefn on
    the function itself (its body runs on stock ticks only)."""
    rows = world_rows()
    if rows.get(f.entry) in ("gatefn", "gate0"):
        return f.entry, rows[f.entry]

    def dominates(x, y):
        while y in f.idom and f.idom[y] != y and y != x:
            y = f.idom[y]
        return y == x
    a = site
    while a in f.idom and f.idom[a] != a:
        a = f.idom[a]
        i = f.ins[a]
        if not i.mnemonic.startswith("j") or i.mnemonic == "jmp" or \
                i.operands[0].type != X.X86_OP_IMM:
            continue
        for c in f.before(a, 4)[::-1]:
            ci = f.ins[c]
            if X.X86_REG_EFLAGS in ci.regs_access()[1]:
                kind = rows.get(c)
                if kind in GATING:
                    t = ct.taken(i.mnemonic, ct.FLAGS[kind])
                    held = i.operands[0].imm if t else i.address + i.size
                    other = i.address + i.size if t else i.operands[0].imm
                    if t is not None and held != other and dominates(other, site):
                        return c, kind
                break
    return None


def crossing(im, f, site):
    """the dominating compare `(int)[R + d] != (int)[R + d +- 4]` (a frame and
    last tick's copy) whose "not equal" side dominates `site`: drawn once per
    integer crossing of the frame, at any rate"""
    fn, sl, _ind, _sw = im.func(site)
    a = site
    while a in f.idom and f.idom[a] != a:
        a = f.idom[a]
        i = f.ins[a]
        if i.mnemonic != "cmp" or len(i.operands) != 2 or a not in fn.ins:
            continue
        regs = [gtc.reg_key(i, op.reg) if op.type == X.X86_OP_REG else None for op in i.operands]
        if None in regs:
            continue
        x, y = (_trunc_field(sl, a, r) for r in regs)
        if not x or not y or x[0] != y[0] or abs(x[1] - y[1]) != 4:
            continue
        j = f.ins.get(a + i.size)
        if j is None or j.mnemonic not in ("je", "jne") or j.operands[0].type != X.X86_OP_IMM:
            continue
        ne = j.operands[0].imm if j.mnemonic == "jne" else j.address + j.size
        b = site
        while b in f.idom and f.idom[b] != b and b != ne:
            b = f.idom[b]
        if b == ne:
            return a
    return None


def ends_state(im, site):
    """the writes that end the actor's state or phase on every path from
    `site` to a return: a state request (an immediate store over +E35, the
    state, as `mov word/dword [R + E34], imm`) or a phase advance (`inc`/
    `add imm` on +E36 or +E37), on the object the function was handed; None
    when some path has neither"""
    fn, sl, ind, _sw = im.func(site)
    if site not in fn.ins:
        return None
    orphan = ob._indirect(fn)
    i0 = fn.ins[site]
    done, work, hits = set(), [(site + i0.size, False)], set()
    while work:
        a, ended = work.pop()
        if (a, ended) in done:
            continue
        done.add((a, ended))
        if a not in fn.ins:
            if not ended:
                return None
            continue
        i = fn.ins[a]
        if not ended and i.operands and i.operands[0].type == X.X86_OP_MEM and \
                i.operands[0].access & capstone.CS_AC_WRITE:
            f = ob._field(i, i.operands[0])
            if f is not None and ob._base(sl, a, f[0]) == "param(rcx)":
                lo, size = f[1], i.operands[0].size
                m = i.mnemonic
                if m == "mov" and len(i.operands) == 2 and i.operands[1].type == X.X86_OP_IMM \
                        and lo <= 0xE35 < lo + size and lo >= 0xE34:
                    ended = True
                elif m in ("inc", "add") and size == 1 and lo in (0xE36, 0xE37) and \
                        (m == "inc" or (i.operands[1].type == X.X86_OP_IMM and
                                        i.operands[1].imm & 0xFF)):
                    ended = True
                if ended:
                    hits.add(a)
        if i.mnemonic in ("ret", "retf"):
            if not ended:
                return None
            continue
        for s in _succs(fn, i, ind, orphan):
            work.append((s, ended))
    return sorted(hits) or None


def _request(sl, i, base):
    """an immediate store over the state byte +E35 of the same object
    (`mov word [R + E34], 1`, `mov dword [R + E34], 0x301`): a state request,
    after which the phase bytes belong to the requested state"""
    if i.mnemonic != "mov" or len(i.operands) != 2 or \
            i.operands[1].type != X.X86_OP_IMM or i.operands[0].type != X.X86_OP_MEM:
        return False
    f = ob._field(i, i.operands[0])
    return f is not None and 0xE34 <= f[1] <= 0xE35 < f[1] + i.operands[0].size and \
        ob._base(sl, i.address, f[0]) == base


def once(im, site):
    """once_blocks.once with switch-table gates and exact table successors;
    a state request after the phase's advance keeps it advanced"""
    fn, sl, ind, sw = im.func(site)
    if site not in fn.ins:
        return None
    orphan = ob._indirect(fn)
    allg = collections.defaultdict(list)
    for gs in (ob.gates(fn, sl), slice_gates(fn, sl), sw):
        for key, edges in gs.items():
            allg[key].extend(e for e in edges if e not in allg[key])
    for (base, d, v), edges in sorted(allg.items(), key=lambda kv: (str(kv[0][0]), kv[0][1], kv[0][2])):
        blocked = set(edges)
        seen, work = set(), [fn.root]
        while work:
            a = work.pop()
            if a in seen or a not in fn.ins:
                continue
            seen.add(a)
            for s in _succs(fn, fn.ins[a], ind, orphan):
                if (a, s) not in blocked:
                    work.append(s)
        if site in seen:
            continue
        # From the gated edges on, every path that passes the site must reach
        # a return with the byte advanced (before or after the site).
        # adv: the byte was advanced past v; req: after the advance, a state
        # request: later writes of the byte set the requested state's phase;
        # past: the path went through the site
        work = [(t, False, False, False) for _j, t in edges]
        done, ok, wrote = set(), True, set()
        while work and ok:
            a, adv, req, past = work.pop()
            if (a, adv, req, past) in done:
                continue
            done.add((a, adv, req, past))
            if a not in fn.ins:
                ok = adv or not past
                continue
            past = past or a == site
            i = fn.ins[a]
            if adv and not req and d in STATE and _request(sl, i, base):
                req = True
            w = None if req else ob._write(sl, i, base, d, v)
            if w == "advance":
                adv = True
                wrote.add(a)
            elif w == "back":
                adv = False
            if i.mnemonic in ("ret", "retf"):
                ok = adv or not past
                continue
            for s in _succs(fn, i, ind, orphan):
                work.append((s, adv, req, past))
        if ok and wrote:
            return "once per phase: only while [%s + 0x%X] == %d (%s), advanced at %s" % (
                base, d, v, ", ".join("%X" % e[0] for e in sorted(edges)),
                ", ".join("%X" % w for w in sorted(wrote)))
    return None


def _entry_plus(sl, i, base, d, first_gate):
    """k when the register `i` stores to [base + d] holds that byte, as a movzx
    loaded it before the first gate (the dispatch), plus k; else None"""
    reg = gtc.reg_key(i, i.operands[1].reg)
    t = sl.value(i.address, reg)
    k = 0
    while t is not None and t[0] == "op" and t[2] in ("add", "sub", "inc", "dec"):
        r = t[4]
        if t[2] in ("inc", "dec"):
            k += 1 if t[2] == "inc" else -1
        elif r is not None and r[0] == "imm":
            k += r[2] if t[2] == "add" else -r[2]
        else:
            return None
        t = t[3]
    if t is None or t[0] != "conv" or t[2] != "movzx" or t[3][0] != "field":
        return None
    load = t[3][1]
    li = sl.fn.ins.get(load)
    if li is None or load > first_gate or li.operands[1].size != 1:
        return None
    f = ob._field(li, li.operands[1])
    if f is None or f[1] != d or ob._base(sl, load, f[0]) != base:
        return None
    return k


def once_chain(im, site):
    """once() for set-up chains (`case 0: ...; phase++; case 1: ...; phase++`):
    the byte's value is followed from the function's entry, through the gated
    edges (taking one fixes it), `inc`/`add imm`/`mov imm` writes and state
    requests; the draw runs once per phase when it is reached only along gated
    edges and every path through it ends with the byte off every value the
    draw was reached with (or after a state request)"""
    fn, sl, ind, sw = im.func(site)
    if site not in fn.ins:
        return None
    orphan = ob._indirect(fn)
    allg = collections.defaultdict(dict)    # (base, d) -> {edge: v}
    for gs in (ob.gates(fn, sl), slice_gates(fn, sl), sw):
        for (base, d, v), edges in gs.items():
            for e in edges:
                allg[(base, d)][e] = v
    for (base, d), gated in sorted(allg.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        first_gate = min(a for a, _s in gated)
        # state: (addr, val, entry values or None, past, req); val "E" = the
        # entry value, "T" = unknown
        work = [(fn.root, "E", None, False, False)]
        done, at_site, ends, ok, steps = set(), set(), [], True, 0
        while work and ok:
            a, val, bset, past, req = work.pop()
            key = (a, val, bset, past, req)
            if key in done:
                continue
            done.add(key)
            steps += 1
            if steps > 20000:
                ok = False
                break
            if a not in fn.ins:
                if past:
                    ends.append((val, req))
                continue
            if a == site:
                if bset is None:
                    ok = False      # reached without a gated edge
                    break
                past = True
                at_site |= bset
            i = fn.ins[a]
            if not req and past and d in STATE and _request(sl, i, base):
                req = True
            if not req:
                w = ob._write(sl, i, base, d, -1)
                if w is not None:
                    m = i.mnemonic
                    if m == "inc" and isinstance(val, int):
                        val = (val + 1) & 0xFF
                    elif m == "add" and isinstance(val, int) and \
                            i.operands[1].type == X.X86_OP_IMM:
                        val = (val + i.operands[1].imm) & 0xFF
                    elif m == "mov" and i.operands[1].type == X.X86_OP_IMM:
                        lo = ob._field(i, i.operands[0])[1]
                        val = (i.operands[1].imm >> (8 * (d - lo))) & 0xFF
                    elif m == "mov" and i.operands[1].type == X.X86_OP_REG and \
                            i.operands[0].size == 1 and bset is not None and len(bset) == 1:
                        # `inc cl; mov [R + d], cl`: the byte as loaded before the
                        # dispatch (this path's entry value), plus k
                        o = _entry_plus(sl, i, base, d, first_gate)
                        val = "T" if o is None else (next(iter(bset)) + o) & 0xFF
                    else:
                        val = "T"
            if i.mnemonic in ("ret", "retf"):
                if past:
                    ends.append((val, req))
                continue
            for s in _succs(fn, i, ind, orphan):
                v = gated.get((a, s))
                nval, nb = val, bset
                if v is not None:
                    if isinstance(val, int):
                        if val != v:
                            continue        # this edge needs another value
                    elif val == "E":
                        nval, nb = v, frozenset([v]) if bset is None else bset & {v}
                        if not nb:
                            continue
                work.append((s, nval, nb, past, req))
        if not ok or not at_site or not ends:
            continue
        if all(req or (isinstance(val, int) and val not in at_site) for val, req in ends):
            return "once per phase: [%s + 0x%X] in {%s} leads to it, and every path on leaves " \
                   "it elsewhere or requests a state" % (
                       base, d, ", ".join(str(v) for v in sorted(at_site)))
    return None


# ---- what a draw feeds ----------------------------------------------------------

ARGS = ("rcx", "rdx", "r8", "r9", "xmm0", "xmm1", "xmm2", "xmm3")


def uses(f):
    """{draw: [(kind, at, text)]}: stores outside the stack, call arguments
    and returns of a value computed from the draw (chance_trials' flow)"""
    out = collections.defaultdict(list)
    for at in f.order:
        i = f.ins[at]
        s = f.state.get(at)
        if s is None:
            continue
        mn = i.mnemonic
        if mn == "call":
            t = f.call_target(i)
            if t in ct.RNG:
                continue
            name ="%X" % t if t is not None else (f.iat_name(i) or i.op_str).split("!")[-1][:40]
            for r in ARGS:
                for d in s.get(r, ()):
                    if d != ct.DERIVED:
                        out[d].append(("arg", at, "%s to %s" % (r, name)))
            continue
        if mn in ("ret",):
            for d in s.get("rax", frozenset()) | s.get("xmm0", frozenset()):
                if d != ct.DERIVED:
                    out[d].append(("ret", at, "returned"))
            continue
        if mn in ct.COMPARES or mn in ("push", "pop"):
            continue
        reads, _w = i.regs_access()
        src = set()
        for r in reads:
            src |= s.get(ct.canonical(i.reg_name(r)), frozenset())
        for op in i.operands:
            if op.type == X.X86_OP_MEM and op.access & capstone.CS_AC_WRITE and \
                    not f.slot(i, op) and src:
                for d in src:
                    if d != ct.DERIVED:
                        out[d].append(("store", at, "%s %s" % (mn, i.op_str)))
    return out


# ---- per function ---------------------------------------------------------------

def facts(im, entry, sites):
    """{site: {...}} for the draws `sites` of the decompile's function `entry`"""
    f = ct.Func(entry)
    f.flow()
    f.postdominators()
    f.dominators()
    joins = f.joins()
    use = uses(f)
    reach = collections.defaultdict(list)
    for c, ds in f.compares.items():
        for d in ds:
            if d != ct.DERIVED:
                reach[d].append(c)
    br_of = collections.defaultdict(list)
    for br, cs in f.branches.items():
        for c in cs:
            br_of[c].append(br)
    try:
        gates, notes = ct.plan(f, joins)
    except Exception as e:    # noqa: BLE001 - a planner failure is a fact too
        gates, notes = {}, {"error": repr(e)}
    out = {}
    for s in sites:
        d = {}
        if s not in f.ins:
            d["error"] = "not decoded in %X" % entry
            out[s] = d
            continue
        d["once"] = once(im, s) or once_chain(im, s)
        d["ends"] = ends_state(im, s)
        d["end"] = f.motion_end_above(s)
        d["cross"] = crossing(im, f, s)
        d["state"] = f.state_store_above(s)
        g = paced_guard(f, s)
        d["guard"] = ("%06X %s" % g) if g else None
        cmps = []
        for c in sorted(reach.get(s, [])):
            for br in br_of.get(c, []):
                b = f.ins[br]
                text, order = ct.describe(f, c, f.state.get(c, {}))
                p = ct.probability_taken(f, c, b)
                g = gates.get(br)
                n = notes.get(br)
                cmps.append(dict(cmp=c, br=br, text=text, order=order, mn=b.mnemonic, p=p,
                                 plan=("GATE %s" % g[1]) if g else (n or "")))
        d["cmps"] = cmps
        d["uses"] = use.get(s, [])
        out[s] = d
    return f, out


def pending(all_rows=False):
    rows = list(csv.DictReader(open(os.path.join(DOCS, "random_rolls.csv"), encoding="utf-8")))
    return [r for r in rows if all_rows or r["review"] == "pending"]


VERDICTS = ("patched", "once", "event", "stock", "mixed_guard", "dead")


def mech(d):
    """(verdict, why) when the facts alone settle the draw, else None"""
    if d.get("error"):
        return None
    if d.get("once"):
        return "once", "roll_reads: " + d["once"]
    if d.get("cross"):
        return "event", ("roll_reads: below the integer frame crossing at %s (its \"not equal\" "
                         "side): drawn once per crossing" % d["cross"])
    if d.get("end") and d.get("ends"):
        return "event", ("roll_reads: below the motion end the advance at %s reports, and every "
                         "path on requests a state or advances the phase (%s): once per end"
                         % (d["end"], ", ".join(d["ends"])))
    if d.get("ends"):
        return "once", ("roll_reads: every path from the draw requests a state or advances the "
                        "phase (%s): drawn once per state or phase" % ", ".join(d["ends"]))
    if d.get("guard"):
        at, kind = d["guard"].split()
        if kind in ("gatefn", "gate0"):
            return "event", ("roll_reads: its function runs on stock ticks only (%s %s), so the "
                             "draw keeps stock cadence" % (kind, at))
        return "event", ("roll_reads: below the test at %s, whose %s row reads the held side "
                         "between stock ticks: drawn only when the test passes on a stock tick, "
                         "at stock cadence" % (at, kind))
    return None


def read_spec(path):
    """[(verdict, why, [sites])] from `verdict | why | SITE SITE ...` lines"""
    out = []
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3 or parts[0] not in VERDICTS or not parts[2]:
            raise SystemExit("%s:%d: want `verdict | why | SITE ...` with a verdict in %s"
                             % (path, n, ", ".join(VERDICTS)))
        out.append((parts[0], parts[1], parts[2].split()))
    return out


def add(paths):
    """append the specs' verdicts to followup_reviews.csv (random_rolls.csv
    inventory); every site must be a pending draw, once"""
    rr = {r["site"]: r for r in pending(True)}
    p = os.path.join(DOCS, "followup_reviews.csv")
    have = {r["site"]: (r["verdict"], r["evidence"])
            for r in csv.DictReader(open(p, encoding="utf-8"))
            if r["inventory"] == "random_rolls.csv"}
    new = []
    for path in paths:
        for verdict, why, sites in read_spec(path):
            for s in sites:
                if s not in rr:
                    raise SystemExit("%s: %s is not a draw in random_rolls.csv" % (path, s))
                if s in have:
                    if have[s] == (verdict, why):
                        continue    # added from this line before
                    raise SystemExit("%s: %s already has another review" % (path, s))
                have[s] = (verdict, why)
                new.append(dict(inventory="random_rolls.csv", site=s, verdict=verdict,
                                evidence=why))
    with open(p, "a", encoding="utf-8", newline="") as f:
        csv.DictWriter(f, fieldnames=("inventory", "site", "verdict", "evidence")).writerows(new)
    print("added %d reviews" % len(new))


def show(im, entry, sites, kinds):
    f, fx = facts(im, entry, sites)
    print("#### %X: %d pending draws" % (entry, len(sites)))
    for r in im.roots_of(entry)[:12]:
        print("   root " + r)
    for s in sites:
        d = fx[s]
        print("  %06X %-14s" % (s, kinds.get(s, "")), end="")
        if "error" in d:
            print(d["error"])
            continue
        tags = []
        if d["once"]:
            tags.append(d["once"])
        if d["end"]:
            tags.append("below motion end %X" % d["end"])
        if d["ends"] and not d["once"]:
            tags.append("ends the state at %s" % " ".join("%X" % a for a in d["ends"]))
        if d["cross"]:
            tags.append("below crossing %X" % d["cross"])
        if d["state"]:
            tags.append("below state store %X" % d["state"])
        if d.get("guard"):
            tags.append("below paced test %s" % d["guard"])
        print("; ".join(tags) or "-")
        for c in d["cmps"]:
            print("        cmp %06X %-34s %-11s %s %06X p(taken)=%s  %s" % (
                c["cmp"], c["text"][:34], c["order"], c["mn"], c["br"],
                "?" if c["p"] is None else "%.3g" % c["p"], c["plan"]))
        for kind, at, text in d["uses"][:6]:
            print("        %s %06X %s" % (kind, at, text))


def main():
    argv = sys.argv[1:]
    if argv and argv[0] == "--add":
        add(argv[1:])
        return
    if argv and argv[0] == "--mech":
        # the facts of --all OUT.json -> a spec of what they settle alone
        fx = json.load(open(argv[1]))
        groups = collections.defaultdict(list)
        for s, d in sorted(fx.items()):
            m = mech(d)
            if m:
                groups[m].append(s)
        with open(argv[2], "w", encoding="utf-8") as f:
            f.write("# roll_reads --mech: draws the facts settle alone\n")
            for (verdict, why), sites in sorted(groups.items(), key=lambda kv: kv[1][0]):
                f.write("%s | %s | %s\n" % (verdict, why, " ".join(sites)))
        print("%d draws in %d lines" % (sum(len(v) for v in groups.values()), len(groups)))
        return
    im = Image()
    if argv and argv[0] == "--all":
        rows = pending()
        by_fn = collections.defaultdict(list)
        for r in rows:
            by_fn[int(r["function"], 16)].append(int(r["site"], 16))
        out = {}
        for k, (entry, sites) in enumerate(sorted(by_fn.items())):
            try:
                _f, fx = facts(im, entry, sorted(sites))
            except (SystemExit, Exception) as e:    # noqa: BLE001
                fx = {s: dict(error=repr(e)[:200]) for s in sites}
            for s, d in fx.items():
                d = dict(d)
                for c in d.get("cmps", []):
                    c["cmp"], c["br"] = "%06X" % c["cmp"], "%06X" % c["br"]
                d["uses"] = [(kind, "%06X" % at, text) for kind, at, text in d.get("uses", [])]
                if d.get("ends"):
                    d["ends"] = ["%06X" % a for a in d["ends"]]
                for key in ("end", "cross", "state"):
                    if d.get(key) is not None:
                        d[key] = "%06X" % d[key]
                d["function"] = "%06X" % entry
                out["%06X" % s] = d
            if k % 50 == 0:
                print(k, len(by_fn), flush=True)
        json.dump(out, open(argv[1], "w"), indent=1)
        print("wrote %d draws" % len(out))
        return
    if argv and argv[0] == "--site":
        rows = {int(r["site"], 16): r for r in pending(True)}
        for a in argv[1:]:
            s = int(a, 16)
            entry = int(rows[s]["function"], 16)
            show(im, entry, [s], {s: rows[s]["kind"]})
        return
    rows = pending()
    kinds = {int(r["site"], 16): r["kind"] for r in rows}
    by_fn = collections.defaultdict(list)
    for r in rows:
        by_fn[int(r["function"], 16)].append(int(r["site"], 16))
    for a in argv:
        entry = int(a, 16)
        show(im, entry, sorted(by_fn.get(entry, [])), kinds)


if __name__ == "__main__":
    main()
