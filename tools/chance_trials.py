#!/usr/bin/env python3
"""Find the compares a random draw decides in a function, and which way each
one goes when it does nothing.

    .venv/Scripts/python tools/chance_trials.py FUNC [FUNC ...] [--join J ... | --only-joins J ...] [--spec | --plan]

A draw is a call to one of the five generators (random_rolls.csv). Its value
is followed through registers, stack spills, flag-neutral moves and branches,
along every path of the function (a forward data flow to a fixed point; switch
tables are followed), so a draw read by several compares after other tests
(em65's 2C0D22) is found too. Each compare it reaches and the conditional
branch that reads the compare's flags (also through a `jmp`) is printed with
the constant compared against, and each of the branch's two outcomes is
classified against the branch's immediate post-dominator P (where both of its
paths meet again):

* `none`: every path from the outcome reaches P, another draw's compare, a
  join or a return without an effect;
* `effect`: some path meets an effect first: a store outside the stack, an
  indirect call, or a call of a function that stores outside its own stack
  (followed three calls deep; flower_kernel's vector/matrix math counts as an
  effect only when its output is not on the caller's stack; draws are not
  effects).

Joins are the targets of the unconditional `jmp`s that occur at least five
times in the function (a decision chain's common exit), plus any --join;
--only-joins J ... gives them by hand (a shared action block can also be
jumped to five times: em60's 2A990C).
A trial is a branch with exactly one `none` outcome. --spec prints a gate row
for each that has none yet: `notyetb` when CF = 1, ZF = 0 (`comiss k, draw`:
k below the draw) takes the `none` outcome, else `notyet` when ZF = SF = OF
= 0 does. The rows still have to pass the generator's proofs, and whether the
function runs every tick, and the compare with it, has to be read.
"""
import bisect
import collections
import os
import re
import struct
import sys

import capstone
from capstone import x86 as X

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import read_candidates as rc  # noqa: E402
import xrefs  # noqa: E402

RNG_FLOAT = {0x1BD580: "u01", 0x1BD590: "s11", 0x1BD620: "range"}
RNG_INT = {0x1BD480: "i16", 0x1BD6D0: "i32"}
RNG = set(RNG_FLOAT) | set(RNG_INT)
VOLATILE = {"rax", "rcx", "rdx", "r8", "r9", "r10", "r11",
            "xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5"}
COMPARES = ("cmp", "test", "comiss", "ucomiss", "comisd", "ucomisd")
MOVES = ("mov", "movss", "movaps", "movups", "movd", "movq", "movzx", "movsx", "movsxd")
DERIVED = -1    # a tag: the value went through arithmetic after the draw
TBL = re.compile(r"^(\w+), dword ptr \[(\w+) \+ (\w+)\*4 \+ (0x[0-9a-f]+)\]$")
PURE_CRT = ("atan2f", "sqrtf", "sinf", "cosf", "fmodf", "acosf", "asinf", "atanf",
            "powf", "expf", "logf", "floorf", "ceilf", "tanf")
# which way a branch goes under each synthesized flag state (notyet and
# notyetneg leave CF as it was, so they serve only branches that ignore it)
FLAGS = {
    "notyetb": dict(CF=1, ZF=0, SF=0, OF=0, PF=0),
    "notyet": dict(CF=None, ZF=0, SF=0, OF=0, PF=0),
    "notyetneg": dict(CF=None, ZF=0, SF=1, OF=0, PF=0),
}
CF_BRANCHES = ("jb", "jae", "jbe", "ja")
RARE = 0.5    # a trial's success: at most this likely (em85's last trial is 0.5)


def taken(mn, f):
    if f["CF"] is None and mn in CF_BRANCHES:
        return None
    return {
        "jb": f["CF"] == 1, "jae": f["CF"] == 0, "jbe": f["CF"] == 1 or f["ZF"] == 1,
        "ja": f["CF"] == 0 and f["ZF"] == 0, "je": f["ZF"] == 1, "jne": f["ZF"] == 0,
        "jl": f["SF"] != f["OF"], "jge": f["SF"] == f["OF"],
        "jle": f["ZF"] == 1 or f["SF"] != f["OF"], "jg": f["ZF"] == 0 and f["SF"] == f["OF"],
        "js": f["SF"] == 1, "jns": f["SF"] == 0, "jp": f["PF"] == 1, "jnp": f["PF"] == 0,
        "jo": f["OF"] == 1, "jno": f["OF"] == 0,
    }.get(mn)


def canonical(name):
    import survey_fps_followups as sff
    return sff.canonical(name)


_IMAGE = {}


def image():
    """main.dll's mapped image, its imports and the decompile's function
    starts, loaded once"""
    if not _IMAGE:
        _IMAGE["bin"] = xrefs.load_bin("main.dll")
        pe, base = _IMAGE["bin"][0], _IMAGE["bin"][1]
        _IMAGE["imports"] = {a - base: n for a, n in xrefs.import_names(pe).items()}
        src = open(rc.DECOMP, encoding="utf-8", errors="replace").read()
        _IMAGE["starts"] = sorted(int(m.group(1), 16) for m in rc.FUNC_HDR.finditer(src))
    return _IMAGE["bin"], _IMAGE["starts"]


_PURE = {}


class Func:
    def __init__(self, entry):
        (self.pe, self.base, self.img, self.text), starts = image()
        self.imports = _IMAGE["imports"]
        i = bisect.bisect_right(starts, entry) - 1
        if starts[i] != entry:
            raise SystemExit("%X is not a function start (it lies in %X)" % (entry, starts[i]))
        self.entry, self.end = entry, starts[i + 1]
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self.md.detail = True
        self.ins, self.tables = {}, {}
        work = [entry]
        while work:
            at = work.pop()
            while at not in self.ins and self.entry <= at < self.end:
                try:
                    i = next(self.md.disasm(self.img[at:at + 15], at))
                except StopIteration:
                    break
                self.ins[at] = i
                mn = i.mnemonic
                if mn in ("ret", "int3", "ud2"):
                    break
                if mn.startswith("j"):
                    op = i.operands[0]
                    if op.type == X.X86_OP_IMM:
                        if self.entry <= op.imm < self.end:
                            work.append(op.imm)
                    elif op.type == X.X86_OP_REG and mn == "jmp":
                        dests = self.switch_targets(at)
                        self.tables[at] = dests
                        work.extend(dests)
                    if mn == "jmp":
                        break
                at += i.size
        self.order = sorted(self.ins)

    def before(self, at, n):
        k = bisect.bisect_left(self.order, at)
        return self.order[max(0, k - n):k]

    def switch_targets(self, at):
        """the destinations of `jmp reg` from the table MSVC reads just before
        it (`mov r32, [image + idx*4 + table]`)"""
        prev = sorted(a for a in self.ins if a < at)[-8:]
        for a in reversed(prev):
            i = self.ins[a]
            g = TBL.match(i.op_str) if i.mnemonic == "mov" else None
            if not g:
                continue
            tbl = int(g.group(4), 16)
            out = []
            for k in range(1024):
                t = struct.unpack_from("<I", self.img, tbl + 4 * k)[0]
                if not self.entry <= t < self.end:
                    break
                out.append(t)
            return out
        return []

    def succ(self, i):
        mn = i.mnemonic
        out = []
        if mn in ("ret", "int3", "ud2"):
            return out
        if mn.startswith("j"):
            op = i.operands[0]
            if op.type == X.X86_OP_IMM and self.entry <= op.imm < self.end:
                out.append(op.imm)
            elif mn == "jmp" and op.type == X.X86_OP_REG:
                out.extend(t for t in self.tables.get(i.address, ()) if t in self.ins)
            if mn == "jmp":
                return out
        nxt = i.address + i.size
        if nxt in self.ins:
            out.append(nxt)
        return out

    def call_target(self, i):
        if i.mnemonic == "call" and i.operands[0].type == X.X86_OP_IMM:
            return i.operands[0].imm
        return None

    def rip_value(self, i):
        for op in i.operands:
            if op.type == X.X86_OP_MEM and op.mem.base == X.X86_REG_RIP:
                ea = i.address + i.size + op.mem.disp
                if op.size == 4:
                    return struct.unpack_from("<f", self.img, ea)[0]
        return None

    def iat_name(self, i):
        for op in i.operands:
            if op.type == X.X86_OP_MEM and op.mem.base == X.X86_REG_RIP:
                return self.imports.get(i.address + i.size + op.mem.disp)
        return None

    def slot(self, i, op):
        if op.type == X.X86_OP_MEM and op.mem.base == X.X86_REG_RSP and op.mem.index == 0:
            return "rsp%+d" % op.mem.disp
        return None

    # ---- effects ---------------------------------------------------------
    def stack_out(self, call_at):
        """the call's rcx is an address on this function's stack"""
        for a in reversed(self.before(call_at, 12)):
            i = self.ins[a]
            _r, w = i.regs_access()
            if any(i.reg_name(r) in ("rcx", "ecx") for r in w):
                return i.mnemonic == "lea" and i.operands[1].type == X.X86_OP_MEM and \
                    i.operands[1].mem.base == X.X86_REG_RSP
        return False

    def call_effect(self, i):
        """None if the call has no effect outside the stack"""
        t = self.call_target(i)
        if t in RNG:
            return None
        if t is not None:
            return None if pure(t) else "call %X" % t
        name = self.iat_name(i)
        short = name.split("!")[-1] if name else ""
        if short in PURE_CRT:
            return None
        if name and "math@wk" in name:
            if short.startswith("?Get") or "Dot@" in short:
                return None
            return None if self.stack_out(i.address) else "call %s" % short[:40]
        return "call %s" % (short[:40] if name else i.op_str)

    def store_effect(self, i):
        if i.mnemonic in COMPARES or i.mnemonic in ("push", "pop"):
            return None
        for op in i.operands:
            if op.type == X.X86_OP_MEM and op.access & capstone.CS_AC_WRITE and \
                    not self.slot(i, op):
                return "store %s" % i.op_str
        return None

    # ---- the data flow -----------------------------------------------------
    def flow(self):
        """loc -> frozenset(tags) at each instruction's entry; regs and stack
        slots carry draw sites, 'flags' carries compare sites; 'k:reg' holds a
        constant a register was loaded with"""
        state = {self.entry: {}}
        work = collections.deque([self.entry])
        self.compares, self.branches = {}, {}
        while work:
            at = work.popleft()
            i = self.ins[at]
            out = self.transfer(i, dict(state[at]))
            for n in self.succ(i):
                old = state.get(n)
                if old is None:
                    state[n] = dict(out)
                    work.append(n)
                    continue
                merged = dict(old)
                changed = False
                for k, v in out.items():
                    if k.startswith("k:"):
                        if k in merged and merged[k] != v and merged[k] is not None:
                            merged[k] = None
                            changed = True
                        elif k not in merged:
                            merged[k] = v
                            changed = True
                        continue
                    nv = merged.get(k, frozenset()) | v
                    if nv != merged.get(k):
                        merged[k] = nv
                        changed = True
                for k in list(merged):
                    if k.startswith("k:") and k not in out and merged[k] is not None:
                        merged[k] = None
                        changed = True
                if changed:
                    state[n] = merged
                    work.append(n)
        self.state = state

    def transfer(self, i, s):
        mn = i.mnemonic
        tgt = self.call_target(i)
        if mn == "call":
            for r in VOLATILE:
                s.pop(r, None)
                s.pop("k:" + r, None)
            s.pop("flags", None)
            if tgt in RNG_FLOAT:
                s["xmm0"] = frozenset([i.address])
            elif tgt in RNG_INT:
                s["rax"] = frozenset([i.address])
            return s
        reads, writes = i.regs_access()
        reads = {canonical(i.reg_name(r)) for r in reads}
        writes = {canonical(i.reg_name(r)) for r in writes}
        reads.discard("rsp")
        reads.discard("rip")
        zero = mn in ("xor", "sub", "xorps", "pxor", "xorpd") and len(i.operands) == 2 and \
            all(op.type == X.X86_OP_REG for op in i.operands) and \
            i.operands[0].reg == i.operands[1].reg
        src = frozenset()
        if not zero:
            for r in reads:
                src |= s.get(r, frozenset())
            for op in i.operands:
                sl = self.slot(i, op)
                if sl and op.access & capstone.CS_AC_READ:
                    src |= s.get(sl, frozenset())
        if mn in COMPARES:
            if src:
                self.compares.setdefault(i.address, set()).update(src)
                s["flags"] = frozenset([i.address])
            else:
                s.pop("flags", None)
            return s
        if mn.startswith("j") and mn != "jmp":
            if s.get("flags"):
                self.branches.setdefault(i.address, set()).update(s["flags"])
            return s
        if "rflags" in writes:
            s.pop("flags", None)
        writes.discard("rflags")
        writes.discard("rsp")
        if src and mn not in MOVES:
            src = src | {DERIVED}    # arithmetic on the draw: not its raw value
        for r in writes:
            if src:
                s[r] = src
            else:
                s.pop(r, None)
            s.pop("k:" + r, None)
        if mn in ("movss", "movaps", "movd") and len(i.operands) == 2 and \
                i.operands[0].type == X.X86_OP_REG:
            dst = canonical(i.reg_name(i.operands[0].reg))
            v = self.rip_value(i)
            if v is not None:
                s["k:" + dst] = v
            elif i.operands[1].type == X.X86_OP_REG:
                k = s.get("k:" + canonical(i.reg_name(i.operands[1].reg)))
                if k is not None:
                    s["k:" + dst] = k
        for op in i.operands:
            sl = self.slot(i, op)
            if sl and op.access & capstone.CS_AC_WRITE:
                if src:
                    s[sl] = src
                else:
                    s.pop(sl, None)
        return s

    # ---- post-dominators -----------------------------------------------------
    def postdominators(self):
        """immediate post-dominator of every instruction (None: the exit), by
        Cooper, Harvey and Kennedy's iteration on the reversed graph"""
        EXIT = -1
        rsucc = collections.defaultdict(list)   # reversed edges
        succs = {}
        for a, i in self.ins.items():
            ss = self.succ(i)
            succs[a] = ss or [EXIT]
            for n in succs[a]:
                rsucc[n].append(a)
        order, seen = [], {EXIT}
        stack = [(EXIT, iter(rsucc[EXIT]))]
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                stack.pop()
                order.append(node)
                continue
            if nxt not in seen:
                seen.add(nxt)
                stack.append((nxt, iter(rsucc[nxt])))
        order.reverse()
        index = {n: k for k, n in enumerate(order)}
        ipdom = {EXIT: EXIT}

        def intersect(a, b):
            while a != b:
                while index[a] > index[b]:
                    a = ipdom[a]
                while index[b] > index[a]:
                    b = ipdom[b]
            return a
        changed = True
        while changed:
            changed = False
            for n in order[1:]:
                cands = [m for m in succs[n] if m in ipdom]
                if not cands:
                    continue
                new = cands[0]
                for m in cands[1:]:
                    new = intersect(m, new)
                if ipdom.get(n) != new:
                    ipdom[n] = new
                    changed = True
        self.ipdom = {a: (None if p == EXIT else p) for a, p in ipdom.items() if a != EXIT}

    def dominators(self):
        """immediate dominator of every instruction reachable from the entry"""
        preds = collections.defaultdict(list)
        for a, i in self.ins.items():
            for n in self.succ(i):
                preds[n].append(a)
        order, seen = [], {self.entry}
        stack = [(self.entry, iter(self.succ(self.ins[self.entry])))]
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                stack.pop()
                order.append(node)
                continue
            if nxt not in seen:
                seen.add(nxt)
                stack.append((nxt, iter(self.succ(self.ins[nxt]))))
        order.reverse()
        index = {n: k for k, n in enumerate(order)}
        idom = {self.entry: self.entry}

        def intersect(a, b):
            while a != b:
                while index[a] > index[b]:
                    a = idom[a]
                while index[b] > index[a]:
                    b = idom[b]
            return a
        changed = True
        while changed:
            changed = False
            for n in order[1:]:
                cands = [m for m in preds[n] if m in idom]
                if not cands:
                    continue
                new = cands[0]
                for m in cands[1:]:
                    new = intersect(m, new)
                if idom.get(n) != new:
                    idom[n] = new
                    changed = True
        self.idom = idom

    def state_store_above(self, at):
        """an instruction that dominates `at` and stores the actor's state
        bytes (+E34..+E37 through any base): the code below it runs once per
        entry to the state, the next tick dispatching elsewhere"""
        a = at
        while a in self.idom and self.idom[a] != a:
            a = self.idom[a]
            i = self.ins[a]
            for op in i.operands:
                if op.type == X.X86_OP_MEM and op.access & capstone.CS_AC_WRITE and                         op.mem.base not in (X.X86_REG_RSP, X.X86_REG_RIP) and                         0xE34 <= op.mem.disp <= 0xE37:
                    return a
        return None

    MOTION_ADVANCE = (0x4B9C80, 0x239420, 0x4B9B70)   # the advance, cEm's at its rate, start-and-advance

    def motion_end_above(self, at):
        """the call of the motion advance whose "the motion ended" answer
        (al != 0) the code at `at` lies below: drawn every tick after a
        non-looping motion's end, once a loop for a looping one"""
        a = at
        while a in self.idom and self.idom[a] != a:
            prev, a = a, self.idom[a]
            i = self.ins[a]
            if not i.mnemonic.startswith("j") or i.mnemonic == "jmp" or                     i.mnemonic not in ("je", "jne"):
                continue
            seq = self.before(a, 3)
            if len(seq) < 2:
                continue
            t, c = self.ins[seq[-1]], self.ins[seq[-2]]
            if t.mnemonic != "test" or t.op_str != "al, al" or c.mnemonic != "call" or                     self.call_target(c) not in self.MOTION_ADVANCE:
                continue
            ended = i.address + i.size if i.mnemonic == "je" else i.operands[0].imm
            # the ended side must dominate `at`
            b = at
            while b in self.idom and self.idom[b] != b and b != ended:
                b = self.idom[b]
            if b == ended:
                return c.address
        return None

    def crossing_above(self, at):
        """a dominating `cmp r, r` of two truncated fields 4 bytes apart (an
        animation frame and last tick's: `(int)+3854 != (int)+3858`): the
        code below runs once per crossing of an integer frame, at any rate"""
        a = at
        while a in self.idom and self.idom[a] != a:
            a = self.idom[a]
            i = self.ins[a]
            if i.mnemonic != "cmp" or len(i.operands) != 2 or                     any(op.type != X.X86_OP_REG for op in i.operands):
                continue
            loads = {}
            for b in reversed(self.before(a, 8)):
                j = self.ins[b]
                if j.mnemonic == "cvttss2si" and j.operands[1].type == X.X86_OP_MEM and                         j.operands[0].type == X.X86_OP_REG:
                    loads.setdefault(ct_reg(j, j.operands[0].reg), j.operands[1].mem.disp)
            regs = [ct_reg(i, op.reg) for op in i.operands]
            if all(r in loads for r in regs) and abs(loads[regs[0]] - loads[regs[1]]) == 4:
                return a
        return None

    def joins(self, extra=()):
        counts = collections.Counter()
        for i in self.ins.values():
            if i.mnemonic == "jmp" and i.operands[0].type == X.X86_OP_IMM:
                counts[i.operands[0].imm] += 1
        return {t for t, n in counts.items() if n >= 5} | set(extra)

    def effect_free(self, start, stops, bound=600):
        """None when every path from start reaches a stop, another draw's
        compare or a return with no effect; else the first effect seen"""
        work, seen = [start], set()
        while work:
            at = work.pop()
            if at in seen or at in stops or at in self.compares:
                continue
            seen.add(at)
            if len(seen) > bound:
                return "bound"
            i = self.ins.get(at)
            if i is None:
                return "leaves %X" % at
            if i.mnemonic == "call":
                why = self.call_effect(i)
                if why:
                    return "%s at %X" % (why, at)
            else:
                why = self.store_effect(i)
                if why:
                    return "%s at %X" % (why, at)
            work.extend(self.succ(i))
        return None


def ct_reg(ins, reg):
    return canonical(ins.reg_name(reg))


def pure(fn, depth=3):
    """the function stores nothing outside its own stack frame and calls only
    functions that do not either (depth calls deep; draws allowed)"""
    if fn in _PURE:
        return _PURE[fn]
    if fn in RNG:
        return True
    if depth == 0:
        return False
    _PURE[fn] = False   # recursion guard
    try:
        f = Func(fn)
    except (SystemExit, IndexError):
        return False
    ok = True
    for i in f.ins.values():
        if i.mnemonic == "call":
            if f.call_effect(i):
                ok = False
                break
        elif i.mnemonic == "jmp" and i.operands[0].type == X.X86_OP_IMM and \
                not f.entry <= i.operands[0].imm < f.end:
            if not pure(i.operands[0].imm, depth - 1):
                ok = False
                break
        elif i.mnemonic == "jmp" and i.operands[0].type != X.X86_OP_IMM and \
                not f.tables.get(i.address):
            ok = False
            break
        elif f.store_effect(i):
            ok = False
            break
    _PURE[fn] = ok
    return ok


def describe(f, cmp_at, sv):
    i = f.ins[cmp_at]
    text = "%s %s" % (i.mnemonic, i.op_str)
    v = f.rip_value(i)
    if v is not None:
        text += " {%.6g}" % v
    else:
        for op in i.operands:
            if op.type == X.X86_OP_REG:
                k = sv.get("k:" + canonical(i.reg_name(op.reg)))
                if k is not None:
                    text += " {%s=%.6g}" % (i.reg_name(op.reg), k)
    order = ""
    if i.mnemonic in ("comiss", "ucomiss", "cmp") and len(i.operands) == 2:
        drawn = [bool(sv.get(canonical(i.reg_name(op.reg)), frozenset()))
                 if op.type == X.X86_OP_REG else bool(f.slot(i, op) and sv.get(f.slot(i, op)))
                 for op in i.operands]
        order = "draw-second" if drawn == [False, True] else \
            "draw-first" if drawn == [True, False] else "both" if all(drawn) else "?"
    return text, order


def classify(f, joins):
    """[(compare, branch, text, order, (taken, why), (fall, why), rows, P)]"""
    out = []
    for br_at in sorted(f.branches):
        b = f.ins[br_at]
        tk = b.operands[0].imm if b.operands[0].type == X.X86_OP_IMM else None
        ft = b.address + b.size
        p = f.ipdom.get(br_at)
        stops = set(joins) | ({p} if p is not None else set())
        for cmp_at in sorted(f.branches[br_at]):
            sv = f.state.get(cmp_at, {})
            text, order = describe(f, cmp_at, sv)
            out_t = f.effect_free(tk, stops | {cmp_at}) if tk is not None else "indirect"
            out_f = f.effect_free(ft, stops | {cmp_at})
            rows = []
            if (out_t is None) != (out_f is None):
                none_at = tk if out_t is None else ft
                for kind, fl in FLAGS.items():
                    t = taken(b.mnemonic, fl)
                    if t is not None and (tk if t else ft) == none_at:
                        rows.append((kind, none_at))
            out.append((cmp_at, br_at, text, order, (tk, out_t), (ft, out_f), rows, p))
    return out


def probability_taken(f, cmp_at, br):
    """P(the branch is taken) for a float draw against a known constant, or
    for a bit test of an integer draw; None when it cannot be read off"""
    i = f.ins[cmp_at]
    sv = f.state.get(cmp_at, {})
    draws = f.compares.get(cmp_at, ())
    if i.mnemonic not in ("test", "and"):
        # a compare reads the raw draw only when no arithmetic came between
        for op in i.operands:
            if op.type == X.X86_OP_REG and DERIVED in sv.get(canonical(i.reg_name(op.reg)), ()):
                return None
    draws = [d for d in draws if d != DERIVED]
    kinds = {RNG_FLOAT.get(f.call_target(f.ins[d])) or RNG_INT.get(f.call_target(f.ins[d]))
             for d in draws}
    if len(kinds) != 1:
        return None
    kind = kinds.pop()
    if i.mnemonic in ("comiss", "ucomiss") and kind in ("u01", "s11"):
        _text, order = describe(f, cmp_at, sv)
        k = f.rip_value(i)
        if k is None:
            for op in i.operands:
                if op.type == X.X86_OP_REG and not sv.get(canonical(i.reg_name(op.reg))):
                    k = sv.get("k:" + canonical(i.reg_name(op.reg)))
        if k is None or order not in ("draw-first", "draw-second"):
            return None
        below = max(0.0, min(1.0, k if kind == "u01" else (k + 1) / 2))  # P(draw < k)
        cf = below if order == "draw-first" else 1 - below                  # P(CF = 1)
        return {"jb": cf, "jbe": cf, "jae": 1 - cf, "ja": 1 - cf}.get(br.mnemonic)
    if i.mnemonic in ("test", "and") and kind in ("i16", "i32") and             i.operands[1].type == X.X86_OP_IMM:
        zf = 0.5 ** bin(i.operands[1].imm & 0xFFFFFFFF).count("1")
        return {"je": zf, "jne": 1 - zf}.get(br.mnemonic)
    return None


def forced_walk(f, start, stops, forced, bound=900):
    """the first effect on a path from start when every branch in `forced`
    takes its forced side (others both), None if every path reaches a stop
    or a return without one"""
    work, seen = [start], set()
    while work:
        at = work.pop()
        if at in seen or at in stops:
            continue
        seen.add(at)
        if len(seen) > bound:
            return "bound"
        i = f.ins.get(at)
        if i is None:
            return "leaves %X" % at
        why = f.call_effect(i) if i.mnemonic == "call" else f.store_effect(i)
        if not why and i.mnemonic == "jmp" and i.operands[0].type == X.X86_OP_IMM and                 not f.entry <= i.operands[0].imm < f.end and not pure(i.operands[0].imm):
            why = "tail call %X" % i.operands[0].imm
        if why:
            return "%s at %X" % (why, at)
        if at in forced:
            work.append(forced[at])
        else:
            work.extend(f.succ(i))
    return None


def plan(f, joins):
    """the draw branches to gate: each a trial whose rare side (at most RARE
    likely) does something and whose common side, with every other gated
    branch on its common side too, does nothing until the branch's post-
    dominator or a join; then only those still reachable from the entry on a
    held tick (a trial nested in another's success needs no gate), and none
    below a store of the actor's state bytes (an action's start, once),
    below an integer frame crossing test (once per crossing) or below the
    motion advance's "ended" answer (which depends on whether the motion
    loops: those are read by hand).
    Returns (gates {branch: (compare, kind, target, p)}, notes {branch: why})"""
    cand, notes = {}, {}
    for br_at, cmps in f.branches.items():
        b = f.ins[br_at]
        if b.operands[0].type != X.X86_OP_IMM:
            continue
        tk, ft = b.operands[0].imm, b.address + b.size
        cmp_at = min(cmps)
        ci = f.ins[cmp_at]
        pts = [probability_taken(f, c, b) for c in cmps]   # several: flags joined by a jmp
        if b.mnemonic in CF_BRANCHES and ci.mnemonic in ("cmp", "comiss", "ucomiss"):
            kind = "notyetb"
        elif taken(b.mnemonic, FLAGS["notyet"]) is not None and                 ci.mnemonic in ("test", "cmp", "and"):
            kind = "notyet"
        else:
            notes[br_at] = "no flag form for %s %s" % (ci.mnemonic, b.mnemonic)
            continue
        forced = tk if taken(b.mnemonic, FLAGS[kind]) else ft
        rare = ft if forced == tk else tk
        if None in pts:
            notes[br_at] = "probability unknown"
            continue
        p_rare = max(pt if rare == tk else 1 - pt for pt in pts)
        if p_rare > RARE:
            notes[br_at] = "a pick: the gated side's other is %.3g likely" % p_rare
            continue
        cand[br_at] = (cmps, kind, forced, rare, p_rare)
    # one draw read by two compares on one path is a pick among outcomes (4871F0's
    # draw against 0, 0.3 and 0.6), not a run of independent trials
    if not hasattr(f, "idom"):
        f.dominators()

    def dominates(a, b):
        while b in f.idom and f.idom[b] != b:
            b = f.idom[b]
            if b == a:
                return True
        return False
    readers = collections.defaultdict(set)
    for c, ds in f.compares.items():
        for d in ds:
            if d != DERIVED:
                readers[d].add(c)
    picked = set()
    for d, cs in readers.items():
        cs = sorted(cs)
        if any(dominates(a, b) or dominates(b, a) for k, a in enumerate(cs) for b in cs[k + 1:]):
            picked |= set(cs)
    for br_at in list(cand):
        if set(cand[br_at][0]) & picked:
            notes[br_at] = "a pick: its draw is read by another compare on the same path"
            del cand[br_at]
    gated = dict(cand)
    while True:
        forced = {br: v[2] for br, v in gated.items()}
        drop = {}
        for br, (cmps, kind, fw, rare, p) in gated.items():
            stops = set(joins) | ({f.ipdom[br]} if f.ipdom.get(br) else set())
            why = forced_walk(f, fw, stops, forced)
            if why:
                drop[br] = "its held side does something: " + why
                continue
            if forced_walk(f, rare, stops, forced) is None:
                drop[br] = "its success does nothing before the join"
        if not drop:
            break
        for br, why in drop.items():
            notes[br] = why
            del gated[br]
    forced = {br: v[2] for br, v in gated.items()}
    reach, work = set(), [f.entry]
    while work:
        at = work.pop()
        if at in reach or at not in f.ins:
            continue
        reach.add(at)
        work.extend([forced[at]] if at in forced else f.succ(f.ins[at]))
    gates = {}
    if not hasattr(f, "idom"):
        f.dominators()
    for br, (cmps, kind, fw, rare, p) in gated.items():
        if br not in reach:
            notes[br] = "only reached through a gated trial's success"
            continue
        st = f.state_store_above(min(cmps))
        if st is not None:
            notes[br] = "once per state entry: the state store at %X dominates it" % st
            continue
        cr = f.crossing_above(min(cmps))
        if cr is not None:
            notes[br] = "once per frame crossing: the compare at %X dominates it" % cr
            continue
        me = f.motion_end_above(min(cmps))
        if me is not None:
            notes[br] = ("below the motion end the advance at %X reports: once a loop for a "
                         "looping motion, every tick after a non-looping one's end" % me)
            continue
        gates[br] = (sorted(cmps), kind, fw, p)
    return gates, notes


def analyse(entry, extra_joins=(), only=False):
    f = Func(entry)
    f.flow()
    f.postdominators()
    joins = set(extra_joins) if only else f.joins(extra_joins)
    return f, joins, classify(f, joins)


def main():
    argv = sys.argv[1:]
    extra_joins = []
    only = "--only-joins" in argv
    if only:
        argv[argv.index("--only-joins")] = "--join"
    if "--join" in argv:
        k = argv.index("--join")
        j = k + 1
        while j < len(argv) and not argv[j].startswith("--"):
            extra_joins.append(int(argv[j], 16))
            j += 1
        del argv[k:j]
    spec = "--spec" in argv
    planned = "--plan" in argv
    funcs = [int(a, 16) for a in argv if not a.startswith("--")]
    import gen_world_anims as gwa
    rowed = {rva: kind for _g, kind, rva, *_ in gwa.MANIFEST}
    for entry in funcs:
        f, joins, results = analyse(entry, extra_joins, only)
        if planned:
            gates, notes = plan(f, joins)
            print("# %X: %d draw branches, %d gates; joins %s" % (
                entry, len(f.branches), len(gates), " ".join("%X" % j for j in sorted(joins))))
            for br in sorted(set(gates) | set(notes)):
                b = f.ins[br]
                cmps = sorted(f.branches[br])
                text, _order = describe(f, cmps[0], f.state.get(cmps[0], {}))
                if br in gates:
                    cs, kind, fw, p = gates[br]
                    for c in cs:
                        have = rowed.get(c)
                        print("GATE %s %06X notyet:%06X | p %.4g, %s; branch %06X %s%s" % (
                            kind, c, fw, p, text, br, b.mnemonic,
                            "  [HAVE %s]" % have if have else ""))
                else:
                    print("     %06X %-40s br %06X %-4s : %s" % (cmps[0], text[:40], br,
                                                               b.mnemonic, notes[br]))
            continue
        print("# %X: %d instructions, %d switch tables, %d draw compares, %d branches; joins %s" % (
            entry, len(f.ins), len(f.tables), len(f.compares), len(f.branches),
            " ".join("%X" % j for j in sorted(joins))))
        for cmp_at, br_at, text, order, (tk, out_t), (ft, out_f), rows, p in results:
            b = f.ins[br_at]
            have = rowed.get(cmp_at)

            def lab(o):
                return "none" if o is None else "effect(%s)" % o
            print("%06X %-40s %-11s br %06X %-4s T->%06X %s | F->%06X %s | P %s%s%s" % (
                cmp_at, text[:40], order, br_at, b.mnemonic, tk or 0, lab(out_t), ft,
                lab(out_f), "%06X" % p if p else "exit",
                "" if not rows else " | rows " + ", ".join("%s:%X" % r for r in rows),
                " | HAVE " + have if have else ""))
            if spec and rows and not have:
                kind, none_at = next(((k, n) for k, n in rows if k == "notyetb"), rows[0])
                print("SPEC %s %06X notyet:%06X" % (kind, cmp_at, none_at))


if __name__ == "__main__":
    main()
