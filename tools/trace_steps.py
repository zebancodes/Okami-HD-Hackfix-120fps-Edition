#!/usr/bin/env python3
"""Where an update's step comes from: a backward trace through the code.

    .venv/Scripts/python tools/trace_steps.py SITE [SITE ...]        # one card per store
    .venv/Scripts/python tools/trace_steps.py --field FN DISP        # who writes +DISP
    .venv/Scripts/python tools/trace_steps.py --uses FN DISP         # who adds +DISP in
    .venv/Scripts/python tools/trace_steps.py --open FILE [--out CSV]
    .venv/Scripts/python tools/trace_steps.py --check [--break rows] # the suite's check

The off-path audit of 2026-10-09 left 319 updates whose step adds a field or
a register (misc_reading/open_unscaled_field_steps.txt). It found each step's
source by looking back 24 instructions in address order, so it could not tell
the step from the update's own old value (`addss xmm0, [rbx+294]` is usually
the accumulation, the step already in xmm0), it missed a step computed before
the census load or on another branch, and it stopped at a field without asking
what the field holds. This answers those three questions.

  value     The stored value's expression, sliced backwards through the
            function's control flow (gen_turn_callers.Slicer's walk: both
            sides of every branch, a `jmp reg` to its own switch table,
            non-volatile registers across calls), through stack slots by
            their frame offset (vec_flow.Frame, StackAddrs) and through the
            kernel's cVec functions that write a slot (operator*(float), +=,
            -=, *=, the constructors, + and -). The leaves are constants,
            fields, call results and parameters.
  self      The leaf that reads the store's own location: same displacement
            and index, and a base with the same reaching definitions (or the
            same value). The tree is split along the additions on the way to
            it: x = x + a - b gives the steps +a and -b. A clamp (minss,
            maxss) or the angle wrap 13F2E0 around the sum is looked through;
            x = x * k is a factor; x += (t - x) * k, the self inside a step, a
            blend. A store with no self leaf is a set, not an accumulation.
  patches   Every instruction of a step's tree (its definitions, the stack
            stores that carried it, the add that joins it to the sum) is
            looked up in every family's patched ranges and in world_anims.csv
            for the row's kind. A patch there means the step is converted on
            its own path (lin on its literal, dst or zfirst on its multiply,
            count on its add ...); a gatefn or gate0 at the function's entry
            paces the whole update.
  sources   Each leaf of an unconverted step is followed out of its function:
            a parameter to every direct caller's argument, a call result to the
            callee's returns (the CRT's math and the engine helpers by name),
            and a field to every store of that displacement in a function the
            same classes own (tools/animation_inventory.py's owners), or by a
            kernel call given its address, each with its stored value's tree,
            its census status and its patches.

The batch form reads the sites in the first column of FILE and writes one row
per site: the verdict the trace supports (scaled, gated, wrap, unscaled,
partly, blend, factor, set, complex), the reasons a step counts converted and
each unconverted step's leaves. It decides nothing by itself: a reading
starts from it, and the verdicts go to docs/animation/reads.csv
(tools/add_reads.py). `--check` (in tools/run_suite.sh) traces every census
site coverage counts covered and fails on any whose trace is not converted
and that has neither a reading nor a census exclusion; `--break rows` takes
the world rows away and must fail. Everything is cached in
tools/.disasm_cache/trace_steps.pkl, keyed by main.dll's SHA-1 (`--rebuild`).
"""
import argparse
import bisect
import collections
import contextlib
import csv
import io
import os
import pickle
import re
import struct
import sys

import capstone
from capstone import x86_const as X

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_turn_callers as gtc  # noqa: E402
import vec_flow as vf  # noqa: E402
from gen_shadow_mode import REG64, load_image  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, ".."))
DOCS = os.path.join(ROOT, "docs", "animation")
CACHE = os.path.join(HERE, ".disasm_cache", "trace_steps.pkl")
DECOMP = os.path.expanduser(r"~\tools\main_decompiled.c")

WRAP = 0x13F2E0
# angle wraps, xmm0 in and out: 13F2E0 to (-pi, pi]; 193550 the same with
# fmodf past 128 (the effects' rotations)
WRAPS = {WRAP, 0x193550}
NAMES = {
    0x13F2E0: "wrap angle", 0x23AD90: "slow-motion factor (1, or 0.25 in slow motion)",
    0x2DA410: "forward step", 0x2DA3F0: "move by matrix", 0x2DA510: "FixTurnRate blend",
    0x2DA570: "clamped approach", 0x2DDF90: "clamped angle to point", 0x20CFD0: "joint by index",
    0x20E210: "turn toward point", 0x20E290: "turn toward angle", 0x4B9C80: "motion advance",
    0x1BD590: "random float [0, 1)", 0x239420: "advance; animation ended?",
}
TIMESCALE, MODE, FPS_BYTE, FLAG60, FRAME = 0xB6AC38, 0xB6AC45, 0xB6AC44, 0xB6AC40, 0xB6AC20
RATE = {TIMESCALE: "time scale", MODE: "mode byte", FPS_BYTE: "fps byte",
        FLAG60: "60 fps flag", FRAME: "frame counter"}
MODE_TABLE = (0x7A8150, 0x7A8338)
# pure lookups: the same arguments give the same pointer (step_flow.GETTERS)
GETTERS = {0x20CFD0: ("rcx", "rdx"), 0x20CF90: ("rcx", "rdx")}
TURN = 0x2DA510        # FixTurnRate converts k at the entry for every caller
MAX_DEPTH = 40
VOL_XMM = {"xmm%d" % i for i in range(6)}
VOL_GPR = {"rax", "rcx", "rdx", "r8", "r9", "r10", "r11"}
ARG_GPR = ("rcx", "rdx", "r8", "r9")
TBL = re.compile(r"^(\w+), dword ptr \[(\w+) \+ (\w+)\*4 \+ (0x[0-9a-f]+)\]$")

MOVES = {"mov", "movss", "movsd", "movd", "movq", "movaps", "movups", "movapd", "movupd",
         "movdqa", "movdqu", "movlps", "movhps"}
CONVS = {"movzx", "movsx", "movsxd", "cvtss2sd", "cvtsd2ss", "cvtsi2ss", "cvtsi2sd",
         "cvtdq2ps", "cvttss2si", "cvtss2si", "cvttsd2si", "cvtsd2si", "cvtps2pd", "cvtpd2ps",
         "cvttps2dq", "cvtps2dq"}
UNARY = {"sqrtss", "sqrtsd", "rsqrtss", "rcpss", "sqrtps"}
BINOPS = {"addss", "subss", "mulss", "divss", "minss", "maxss", "addsd", "subsd", "mulsd",
          "divsd", "minsd", "maxsd", "addps", "subps", "mulps", "divps", "minps", "maxps",
          "andps", "andnps", "orps", "xorps", "andpd", "xorpd", "add", "sub", "imul", "and",
          "or", "xor", "shl", "shr", "sar", "sal", "adc", "sbb", "unpcklps", "shufps",
          "pand", "por", "pxor", "paddd", "psubd"}
ADDS = {"addss", "addsd", "add", "addps", "adc", "paddd"}
SUBS = {"subss", "subsd", "sub", "subps", "sbb", "psubd"}
MULS = {"mulss", "mulsd", "mulps", "imul", "divss", "divsd", "divps", "shl", "sal", "shr", "sar"}
CLAMPS = {"minss", "maxss", "minsd", "maxsd", "minps", "maxps"}

# flower_kernel's cVec functions: which argument a call writes (16 bytes) and
# how; tools/vec_flow.py documents each from the kernel's code
K_MULF = "??DcVec@math@wk@@QEBA?AV012@M@Z"            # out(rdx).xyz = this(rcx).xyz * xmm2, w 1
K_MULEQ = "??XcVec@math@wk@@QEAAAEAV012@M@Z"          # this(rcx).xyz *= xmm1, w kept
K_ADDEQ = "??YcVec@math@wk@@QEAAAEAV012@AEBV012@@Z"   # this(rcx).xyz += other(rdx).xyz
K_SUBEQ = "??ZcVec@math@wk@@QEAAAEAV012@AEBV012@@Z"   # this(rcx).xyz -= other(rdx).xyz
K_CTOR4 = "??0cVec@math@wk@@QEAA@MMMM@Z"              # this(rcx) = (xmm1, xmm2, xmm3, arg 5)
K_CTOR0 = "??0cVec@math@wk@@QEAA@XZ"                  # this(rcx) = (0, 0, 0, 1)
K_COPY = "??0cVec@math@wk@@QEAA@AEBV012@@Z"           # this(rcx).xyz = other(rdx).xyz, w 1
K_ASSIGN = "??4cVec@math@wk@@QEAAAEAV012@AEBV012@@Z"  # this(rcx).xyz = other(rdx).xyz, w kept
K_SUB = "??GcVec@math@wk@@QEBA?AV012@AEBV012@@Z"      # out(rdx).xyz = this(rcx) - other(r8)
K_ADD = "??HcVec@math@wk@@QEBA?AV012@AEBV012@@Z"      # out(rdx).xyz = this(rcx) + other(r8)
K_DIVF = "??KcVec@math@wk@@QEBA?AV012@M@Z"            # out(rdx).xyz = this(rcx).xyz / xmm2
K_APPLY = "?Apply@cMatrix@math@wk@@SAXAEAVcVec@23@AEBV123@AEBV423@@Z"
KERNEL_OUT = {K_MULF: "rdx", K_MULEQ: "rcx", K_ADDEQ: "rcx", K_SUBEQ: "rcx", K_CTOR4: "rcx",
              K_CTOR0: "rcx", K_COPY: "rcx", K_ASSIGN: "rcx", K_SUB: "rdx", K_ADD: "rdx",
              K_DIVF: "rdx", K_APPLY: "rcx"}
KERNEL_SHORT = {K_MULF: "cVec*f", K_MULEQ: "cVec*=f", K_ADDEQ: "cVec+=", K_SUBEQ: "cVec-=",
                K_CTOR4: "cVec(x,y,z,w)", K_CTOR0: "cVec()", K_COPY: "cVec(copy)",
                K_ASSIGN: "cVec=", K_SUB: "cVec-cVec", K_ADD: "cVec+cVec", K_DIVF: "cVec/f",
                K_APPLY: "Matrix::Apply"}

# world row kinds that convert a value on the step's own path (the rest pace
# tests and counters; they still count as a patch on the path, listed by kind)
SCALE_KINDS = {"src", "dst", "pre", "srcx", "lin", "step", "dstarg", "argscale", "immstore",
               "dstn", "sq", "scaledadd", "callscale", "callvec", "zfirst", "zlast", "ufirst",
               "ulast", "count", "count2", "countlast", "blend", "blendr", "srcblend",
               "callblend", "root", "srcroot", "mulstore", "imuln", "smode", "floor1",
               "mulflag"}
GATE_KINDS = {"gatefn", "gate0"}


# ---------------------------------------------------------------------------
# trees
# ---------------------------------------------------------------------------
# ("op", a, mnemonic, left, right)      ("conv", a, mnemonic, inner)
# ("phi", (alternatives...))            ("wrap", a, inner)   the angle wrap's xmm0
# ("const", a, rva, value)  .rdata      ("imm", a, value)
# ("field", a, base, disp, index, scale, size, base_tree)
# ("global", a, rva)  .data             ("rate", a, name)    ("table", a, rva)
# ("lea", a, rva)                       ("addr", a, base_tree, index_tree, scale, disp)
# ("stack", a, offset, inner, (store addresses...))          ("stackin", a, offset)
# ("callret", a, reg, target)           ("callmem", a, target, offset)
# ("param", reg)  ("cycle"|"deep"|"orphan"|"nodef"|"stack?"|"opaque"|"flag", a, ...)

def node_addrs(t, out=None):
    """every instruction address a tree names"""
    if out is None:
        out = set()
    if not isinstance(t, tuple) or not t:
        return out
    k = t[0]
    if k == "phi":
        for x in t[1]:
            node_addrs(x, out)
        return out
    if len(t) > 1 and isinstance(t[1], int):
        out.add(t[1])
    if k == "op":
        node_addrs(t[3], out)
        node_addrs(t[4], out)
    elif k in ("conv",):
        node_addrs(t[3], out)
    elif k == "wrap":
        node_addrs(t[2], out)
    elif k == "stack":
        node_addrs(t[3], out)
        out.update(t[4])
    elif k == "field":
        pass                     # the base's own definitions are not the value's
    elif k == "addr":
        node_addrs(t[2], out)
        node_addrs(t[3], out)
    return out


def leaves(t):
    if not isinstance(t, tuple) or not t:
        return
    k = t[0]
    if k == "phi":
        for x in t[1]:
            yield from leaves(x)
    elif k == "op":
        yield from leaves(t[3])
        yield from leaves(t[4])
    elif k == "conv":
        yield from leaves(t[3])
    elif k == "wrap":
        yield from leaves(t[2])
    elif k == "stack":
        yield from leaves(t[3])
    else:
        yield t


OPSYM = {"addss": "+", "addsd": "+", "add": "+", "addps": "+", "subss": "-", "subsd": "-",
         "sub": "-", "subps": "-", "mulss": "*", "mulsd": "*", "mulps": "*", "imul": "*",
         "divss": "/", "divsd": "/", "divps": "/"}


class Render:
    """Compact infix text for a tree; marks patched instructions {kind}."""

    def __init__(self, tr, limit=900):
        self.tr, self.limit = tr, limit

    def __call__(self, t, depth=0):
        s = self._r(t, depth)
        return s if len(s) <= self.limit else s[:self.limit] + " ..."

    def mark(self, a):
        p = self.tr.patch_at(a)
        return "{%s}" % ",".join(sorted({k for _f, k in p})) if p else ""

    def base(self, t, depth):
        if t is None:
            return "?"
        if t[0] == "param":
            return t[1] + ".in"
        return self._r(t, depth + 1)

    def _r(self, t, depth):
        if depth > 14:
            return "..."
        if not isinstance(t, tuple) or not t:
            return "-"
        k = t[0]
        if k == "phi":
            alts = []
            for x in t[1]:
                s = self._r(x, depth + 1)
                if s not in alts:
                    alts.append(s)
            return alts[0] if len(alts) == 1 else "phi(" + " | ".join(alts) + ")"
        if k == "op":
            a, m, L, R = t[1], t[2], t[3], t[4]
            mk = self.mark(a)
            if R is None:
                return "%s(%s)%s" % (m, self._r(L, depth + 1), mk)
            sym = OPSYM.get(m)
            if sym:
                return "(%s %s %s)%s" % (self._r(L, depth + 1), sym, self._r(R, depth + 1), mk)
            return "%s(%s, %s)%s" % (m, self._r(L, depth + 1), self._r(R, depth + 1), mk)
        if k == "conv":
            if t[2] in ("cvtss2sd", "cvtsd2ss", "movzx", "movsx", "movsxd", "cdqe", "cwde"):
                return self._r(t[3], depth) + self.mark(t[1])
            return "%s(%s)%s" % (t[2], self._r(t[3], depth + 1), self.mark(t[1]))
        if k == "wrap":
            return "wrap(%s)" % self._r(t[2], depth + 1)
        if k == "const":
            v = t[3]
            vs = ("%.7g" % v) if isinstance(v, float) else ("#%X" % v if isinstance(v, int) else str(v))
            return "%s@%X%s" % (vs, t[2], self.mark(t[1]))
        if k == "imm":
            v = t[2]
            return ("#%X" % v if v >= 0 else "-#%X" % -v) + self.mark(t[1])
        if k == "field":
            _k, a, base, disp, index, scale, size, btree = t
            ix = ""
            if index:
                ix = " + %s*%d" % (index, scale)
            b = self.base(btree, depth) if btree is not None else base
            ds = ("+%X" % disp) if disp >= 0 else ("-%X" % -disp)
            return "[%s%s%s]@%X%s" % (b, ix, ds, a, self.mark(a))
        if k == "global":
            return "g[%X]@%X%s" % (t[2], t[1], self.mark(t[1]))
        if k == "rate":
            return "RATE(%s)@%X" % (t[2], t[1])
        if k == "table":
            return "modetable[%X]@%X%s" % (t[2], t[1], self.mark(t[1]))
        if k == "lea":
            return "&%X" % t[2]
        if k == "addr":
            b = self.base(t[2], depth) if t[2] is not None else ""
            ix = " + %s*%d" % (self._r(t[3], depth + 1), t[4]) if t[3] is not None else ""
            return "&(%s%s%+X)" % (b, ix, t[5])
        if k == "stack":
            return "stk%+X<%s>%s" % (t[2], self._r(t[3], depth + 1), self.mark(t[1]))
        if k == "stackin":
            return "stackarg%+X" % t[2]
        if k == "callret":
            tg = t[3]
            nm = self.tr.callee_name(tg)
            if len(t) > 4:
                # a pure getter: named by its arguments, so two lookups of
                # the same joint render alike
                return "%s(%s)" % (nm, ", ".join(self._r(x, depth + 1) for x in t[4]))
            return "ret(%s)@%X" % (nm, t[1])
        if k == "callmem":
            return "written_by(%s)@%X" % (self.tr.callee_name(t[2]), t[1])
        if k == "param":
            return "%s.in" % t[1]
        if k == "stackaddr":
            return "&stk%+X" % t[2]
        if len(t) > 1 and isinstance(t[1], int):
            return "%s@%X" % (k, t[1])
        return str(t)


# ---------------------------------------------------------------------------
# the slicer
# ---------------------------------------------------------------------------

class Slicer(gtc.Slicer):
    def __init__(self, tr, fn):
        super().__init__(tr.img, tr.secs, fn)
        self.tr = tr
        self.memo, self.busy = {}, set()
        # only the code reachable from the entry: a switch table inside the
        # function decodes as pushes that would fail the frame
        self.frame = vf.Frame(fn, vf.reachable(fn, fn.succ))
        self.stack = vf.StackAddrs(fn, self.frame, tr.iat, fn.succ) if self.frame.ok else None

    # -- registers ----------------------------------------------------------
    def value(self, at, reg, depth=0):
        key = (at, reg)
        if key in self.memo:
            return self.memo[key]
        if key in self.busy:
            return ("cycle", at, reg)
        if depth > MAX_DEPTH:
            return ("deep", at, reg)
        self.busy.add(key)
        try:
            alts = []
            for kind, a in self.defs(at, reg):
                if kind == "def":
                    v = self.from_def(a, reg, depth)
                elif kind == "call":
                    v = self.call_value(a, reg, depth)
                elif kind == "entry":
                    v = ("param", reg)
                else:
                    v = ("orphan", a, reg)
                if v not in alts:
                    alts.append(v)
            if not alts and at == self.fn.root:
                alts.append(("param", reg))
            t = ("nodef", at, reg) if not alts else alts[0] if len(alts) == 1 else \
                ("phi", tuple(alts))
        finally:
            self.busy.discard(key)
        self.memo[key] = t
        return t

    def call_value(self, a, reg, depth):
        i = self.fn.ins[a]
        tgt = self.tr.callee(i)
        if reg == "xmm0" and tgt in WRAPS:
            return ("wrap", a, self.value(a, "xmm0", depth + 1))
        if reg in ("rax", "xmm0"):
            if tgt in self.tr.ret_arg:
                # the kernel returns the out pointer it was given
                return self.value(a, self.tr.ret_arg[tgt], depth + 1)
            if tgt in GETTERS and reg == "rax":
                return ("callret", a, reg, tgt,
                        tuple(self.value(a, r, depth + 1) for r in GETTERS[tgt]))
            return ("callret", a, reg, tgt)
        return ("clobber", a, reg)

    def opnd(self, i, op, depth):
        if op.type == X.X86_OP_MEM:
            return self.mem(i, op, depth)
        if op.type == X.X86_OP_REG:
            return self.value(i.address, gtc.reg_key(i, op.reg), depth + 1)
        return ("imm", i.address, op.imm)

    def from_def(self, a, reg, depth):
        i = self.fn.ins[a]
        self.touched.add(a)
        m, ops = i.mnemonic, i.operands
        d = depth + 1
        if len(ops) == 2 and ops[0].type == X.X86_OP_REG and ops[1].type == X.X86_OP_REG and \
                ops[0].reg == ops[1].reg and m in ("xorps", "pxor", "xorpd", "xor", "sub",
                                                   "subss", "subps"):
            return ("imm", a, 0)
        if m == "lea":
            mm = ops[1].mem
            t = gtc.rip_target(i, ops[1])
            if t is not None:
                return ("lea", a, t)
            off = self.stack_off(i, ops[1])
            if off is not None and off != "?":
                return ("stackaddr", a, off)
            base = self.value(a, gtc.reg_key(i, mm.base), d) if mm.base else None
            idx = self.value(a, gtc.reg_key(i, mm.index), d) if mm.index else None
            return ("addr", a, base, idx, mm.scale, mm.disp)
        if m in MOVES and len(ops) == 2:
            v = self.opnd(i, ops[1], d)
            if ops[1].type == X.X86_OP_REG and self.tr.patch_at(a):
                # a converted copy (dst on `movaps xmm1, xmm2`): keep it visible
                return ("conv", a, m, v)
            return v
        if m in CONVS and len(ops) == 2:
            return ("conv", a, m, self.opnd(i, ops[1], d))
        if m in ("cdq", "cqo", "cdqe", "cwde", "cwd"):
            return ("conv", a, m, self.value(a, "rax", d))
        if m in ("inc", "dec", "neg", "not") and len(ops) == 1:
            return ("op", a, m, self.value(a, reg, d), None)
        if m == "imul" and len(ops) == 3:
            return ("op", a, "imul", self.opnd(i, ops[1], d), self.opnd(i, ops[2], d))
        if m.startswith("cmov") and len(ops) == 2:
            return ("phi", (self.value(a, reg, d), self.opnd(i, ops[1], d)))
        if m.startswith("set"):
            return ("flag", a, m)
        if m in UNARY and len(ops) == 2:
            return ("op", a, m, self.opnd(i, ops[1], d), None)
        if m in BINOPS and len(ops) >= 1:
            left = self.value(a, reg, d)
            right = self.opnd(i, ops[1], d) if len(ops) > 1 else None
            return ("op", a, m, left, right)
        return ("opaque", a, "%s %s" % (m, i.op_str))

    # -- memory --------------------------------------------------------------
    def stack_off(self, i, op):
        if self.stack is None or op.type != X.X86_OP_MEM:
            return None
        return self.stack.operand(i, op)

    def mem(self, i, op, depth):
        a = i.address
        t = gtc.rip_target(i, op)
        if t is not None:
            return self.tr.rip_leaf(a, t, op.size)
        off = self.stack_off(i, op)
        if off == "?":
            return ("stack?", a, 0)
        if off is not None:
            return self.stack_value(a, off, op.size or 4, depth)
        mm = op.mem
        base = gtc.reg_key(i, mm.base) if mm.base else None
        index = gtc.reg_key(i, mm.index) if mm.index else None
        if mm.disp in RATE and base and not index:
            return ("rate", a, RATE[mm.disp])
        if MODE_TABLE[0] <= mm.disp < MODE_TABLE[1]:
            return ("table", a, mm.disp)
        btree = self.value(a, base, depth + 1) if base else None
        if btree is not None and btree[0] == "lea" and btree[2] == 0:
            # image-base relative: a global or a table entry
            return self.tr.rip_leaf(a, mm.disp, op.size) if not index else \
                ("global", a, mm.disp)
        return ("field", a, base, mm.disp, index, mm.scale, op.size, btree)

    def stack_value(self, at, off, size, depth, start_after=False):
        """What the frame slot [off, off + size) holds just before `at`."""
        fn = self.fn
        out, stores, seen = [], [], set()
        work = list(fn.preds.get(at, [])) if not start_after else [at]
        while work:
            a = work.pop()
            if a in seen:
                continue
            seen.add(a)
            si = fn.ins[a]
            if si.mnemonic == "call":
                w = self.call_writes(si, off, size, depth)
                if w is not None:
                    out.append(w)
                    continue
            hit = None
            for so in si.operands:
                if so.type == X.X86_OP_MEM and so.access & capstone.CS_AC_WRITE:
                    o2 = self.stack.operand(si, so)
                    if o2 == "?":
                        hit = ("partial", so)
                    elif o2 is not None and o2 < off + size and off < o2 + (so.size or 8):
                        if o2 == off:
                            hit = ("exact", so)
                        elif o2 < off and off + size <= o2 + so.size and \
                                si.mnemonic in ("movaps", "movups", "movdqa", "movdqu"):
                            hit = ("lane", so, (off - o2) // 4)
                        else:
                            hit = ("partial", so)
            if hit is not None:
                stores.append(a)
                if hit[0] == "exact":
                    out.append(self.stored(si, hit[1], depth))
                elif hit[0] == "lane":
                    out.append(("lane%d" % hit[2], a, self.stored(si, hit[1], depth)))
                else:
                    out.append(("stack?", a, off))
                continue
            ps = fn.preds.get(a, [])
            if not ps:
                out.append(("stackin", a, off))
            work.extend(ps)
        if not out:
            out.append(("stackin", at, off))
        inner = out[0] if len(out) == 1 else ("phi", tuple(out))
        return ("stack", at, off, inner, tuple(stores))

    def stored(self, si, memop, depth):
        """the value a store instruction writes"""
        m, ops = si.mnemonic, si.operands
        src = [o for o in ops if o is not memop]
        if m in MOVES and src:
            return self.opnd(si, src[0], depth + 1)
        return ("opaque", si.address, "%s %s" % (m, si.op_str))

    def call_writes(self, si, off, size, depth):
        """A call given a stack address that may write [off, off + size)."""
        tgt = self.tr.callee(si)
        a = si.address
        holders = {}
        for r in ARG_GPR:
            b = self.stack.reg(a, r)
            if b is not None:
                holders[r] = b
        out_reg = KERNEL_OUT.get(tgt)
        if out_reg is not None:
            b = holders.get(out_reg)
            if b is None or not (b <= off < b + 16):
                return None          # the kernel only reads its other arguments
            c = (off - b) // 4
            return self.kernel_lane(si, tgt, c, depth)
        if isinstance(tgt, str):
            return None              # other imports read their pointers
        # a pointer in an argument register, or in this call's stack arguments
        # (a fifth or later argument holding &slot): the callee may write it
        if any(b - 0x40 <= off < b + 0x40 for b in holders.values()) or \
                self.passed_on_stack(si, off):
            return ("callmem", a, tgt, off)
        return None

    def passed_on_stack(self, si, off):
        """a stack address near off stored into this call's outgoing argument
        area (rsp + 0x20 ..) since the previous call"""
        if not any(b <= off < b + 0x40 for b in self.stack.escaped):
            return False
        fn = self.fn
        seen, work = set(), list(fn.preds.get(si.address, []))
        while work:
            x = work.pop()
            if x in seen:
                continue
            seen.add(x)
            i = fn.ins[x]
            if i.mnemonic == "call":
                continue
            ops = i.operands
            if i.mnemonic == "mov" and len(ops) == 2 and ops[0].type == X.X86_OP_MEM and \
                    ops[1].type == X.X86_OP_REG:
                o2 = self.stack.operand(i, ops[0])
                if isinstance(o2, int) and self.frame.rsp + 0x20 <= o2 < self.frame.rsp + 0x80:
                    b = self.stack.reg(x, gtc.reg_key(i, ops[1].reg))
                    if b is not None and b <= off < b + 0x40:
                        return True
            work.extend(fn.preds.get(x, []))
        return False

    def lane_of(self, a, reg, c, depth):
        """the float at [reg + 4c] just before instruction a"""
        b = self.stack.reg(a, reg) if self.stack else None
        if b is not None:
            return self.stack_value(a, b + 4 * c, 4, depth + 1)
        base = self.value(a, reg, depth + 1)
        return ("field", a, reg, 4 * c, None, 1, 4, base)

    def kernel_lane(self, si, tgt, c, depth):
        a = si.address
        if c == 3 and tgt in (K_MULF, K_SUB, K_ADD, K_DIVF, K_COPY, K_CTOR0):
            return ("imm", a, 1)
        if tgt == K_MULF:
            return ("op", a, "mulss", self.lane_of(a, "rcx", c, depth), self.value(a, "xmm2", depth + 1))
        if tgt == K_DIVF:
            return ("op", a, "divss", self.lane_of(a, "rcx", c, depth), self.value(a, "xmm2", depth + 1))
        if tgt == K_MULEQ:
            if c == 3:
                return self.lane_of(a, "rcx", c, depth)
            return ("op", a, "mulss", self.lane_of(a, "rcx", c, depth), self.value(a, "xmm1", depth + 1))
        if tgt in (K_ADDEQ, K_SUBEQ):
            if c == 3:
                return self.lane_of(a, "rcx", c, depth)
            return ("op", a, "addss" if tgt == K_ADDEQ else "subss",
                    self.lane_of(a, "rcx", c, depth), self.lane_of(a, "rdx", c, depth))
        if tgt in (K_ADD, K_SUB):
            return ("op", a, "addss" if tgt == K_ADD else "subss",
                    self.lane_of(a, "rcx", c, depth), self.lane_of(a, "r8", c, depth))
        if tgt in (K_COPY, K_ASSIGN):
            if c == 3 and tgt == K_ASSIGN:
                return self.lane_of(a, "rcx", c, depth)
            return self.lane_of(a, "rdx", c, depth)
        if tgt == K_CTOR0:
            return ("imm", a, 0)
        if tgt == K_CTOR4:
            if c < 3:
                return self.value(a, ("xmm1", "xmm2", "xmm3")[c], depth + 1)
            if self.frame.ok:
                # the fifth argument, at the call's rsp + 0x20
                return self.stack_value(a, self.frame.rsp + 0x20, 4, depth + 1)
            return ("stack?", a, 0x20)
        return ("callmem", a, tgt, c * 4)


# ---------------------------------------------------------------------------
# the tracer: image, functions, patches, census, owners, the store index
# ---------------------------------------------------------------------------

class Tracer:
    def __init__(self, rebuild=False):
        self.img, self.secs, _f, self.sha = load_image()
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self.md.detail = True
        self.roots, _starts, ents = gtc.pdata_roots(self.img, self.secs)
        self.frag = sorted((b, e) for b, e, _u in ents)
        self.frag_lo = [b for b, _e in self.frag]
        self.funcs, self.slicers = {}, {}
        self._load_cache(rebuild)
        self.ret_arg = {K_MULF: "rdx", K_SUB: "rdx", K_ADD: "rdx", K_DIVF: "rdx",
                        K_MULEQ: "rcx", K_ADDEQ: "rcx", K_SUBEQ: "rcx", K_CTOR4: "rcx",
                        K_CTOR0: "rcx", K_COPY: "rcx", K_ASSIGN: "rcx"}
        self._patches()
        self._census()

    # -- cache: imports, thunks, owners, stores, callers ---------------------
    def _load_cache(self, rebuild):
        c = None
        if not rebuild and os.path.exists(CACHE):
            try:
                c = pickle.load(open(CACHE, "rb"))
                if c.get("sha") != self.sha or c.get("version") != 4:
                    c = None
            except Exception:
                c = None
        if c is None:
            c = self._build_cache()
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            # written aside and renamed: suite jobs may build it at once
            tmp = "%s.%d" % (CACHE, os.getpid())
            with open(tmp, "wb") as f:
                pickle.dump(c, f, protocol=4)
            os.replace(tmp, CACHE)
        self.iat = c["iat"]
        self.thunks = c["thunks"]
        self.owners = c["owners"]
        self.stores = c["stores"]
        self.callers = c["callers"]
        self.vtslots = c["vtslots"]
        self.dstarts = c["dstarts"]

    def _build_cache(self):
        print("building %s (once per main.dll) ..." % os.path.relpath(CACHE, ROOT),
              file=sys.stderr)
        import gen_world_anims as gwa
        iat = gwa.iat_names()
        lo, hi = self.secs[".text"]
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        md.detail = False
        thunks, stores, callers = {}, collections.defaultdict(list), collections.defaultdict(list)
        prev = collections.deque(maxlen=8)
        mem_re = re.compile(r"^(?:byte|word|dword|qword|xmmword) ptr \[([^\]]+)\]")
        lea_re = re.compile(r"^(r[a-z0-9]+), \[([^\]]+)\]$")
        no_write = {"cmp", "test", "comiss", "ucomiss", "comisd", "ucomisd", "push", "call",
                    "jmp", "bt", "prefetcht0", "prefetchnta", "nop", "lea"}
        pos = lo
        while pos < hi:
            end = min(hi, pos + 0x10000)
            last = pos
            for a, s, mn, op in md.disasm_lite(bytes(self.img[pos:end + 16]), pos):
                if a >= end:
                    break
                last = a + s
                if mn == "jmp" and op.startswith("qword ptr [rip +"):
                    t = a + s + int(op.split("+ ")[1].rstrip("]"), 16)
                    if t in iat:
                        thunks[a] = iat[t]
                if mn == "call":
                    t = None
                    if op.startswith("0x"):
                        t = int(op, 16)
                    elif op.startswith("qword ptr [rip +"):
                        t = iat.get(a + s + int(op.split("+ ")[1].rstrip("]"), 16))
                    if t is not None:
                        callers[t].append(a)
                        # a kernel call writing through a lea'd field address
                        if isinstance(t, str) and t in KERNEL_OUT:
                            for pa, pmn, pop in prev:
                                g = lea_re.match(pop) if pmn == "lea" else None
                                if g and REG64.get(g.group(1), g.group(1)) == KERNEL_OUT[t]:
                                    d = _disp_of(g.group(2))
                                    if d is not None:
                                        stores[d[0]].append((a, "call", t, pa))
                        prev.clear()
                elif mn not in no_write and not mn.startswith("j"):
                    g = mem_re.match(op)
                    if g:
                        d = _disp_of(g.group(1))
                        if d is not None:
                            stores[d[0]].append((a, mn, op, None))
                prev.append((a, mn, op))
            pos = last if last > pos else pos + 1
        owners = self._owners(md)
        # the vtable slots each function sits in
        vtslots = collections.defaultdict(list)
        try:
            import animation_inventory as ai
            classes, vt = ai.load_rtti(os.path.join(HERE, "rtti_classes.txt"))
            for f, lst in vt.items():
                vtslots[f] = lst
        except Exception as e:      # noqa: BLE001
            print("  no rtti slots: %s" % e, file=sys.stderr)
        import coverage_report as cr
        return dict(sha=self.sha, version=4, iat=iat, thunks=thunks, owners=dict(owners),
                    stores=dict(stores), callers=dict(callers), vtslots=dict(vtslots),
                    dstarts=cr.function_starts(DECOMP))

    def _owners(self, md):
        """function -> owner classes, computed as tools/animation_inventory.py does"""
        import animation_inventory as ai
        classes, vt = ai.load_rtti(os.path.join(HERE, "rtti_classes.txt"))
        dc = ai.Decomp(DECOMP)
        owners = collections.defaultdict(set)
        for cls, fns in classes.items():
            for f in fns:
                owners[f].add(cls)
            roots = [f for f in fns if f in dc.funcs and len(vt.get(f, [])) <= 3]
            for f in dc.reach(roots, maxcallers=2, depth=4):
                owners[f].add(cls)
        return {f: frozenset(c) for f, c in owners.items()}

    # -- patches and census --------------------------------------------------
    def _patches(self):
        import check_patch_sites as cps
        cimg, _l, _h = cps.load_image()
        with contextlib.redirect_stdout(io.StringIO()):
            sites, _det, loads = cps.all_sites(cimg)
        rng = [(r, r + max(ln, 1), fam) for r, (fam, ln, _raw) in sites.items()]
        rng += [(r, r + len(raw), "hoisted_decay.h") for r, raw in loads]
        rng.sort()
        self.ranges = rng
        self.range_lo = [r[0] for r in rng]
        self.rows, self.win_rows = {}, collections.defaultdict(list)
        for r in csv.DictReader(open(os.path.join(DOCS, "world_anims.csv"), encoding="utf-8")):
            self.rows[int(r["site"], 16)] = r
            if re.match(r"^[0-9A-F]+$", r["window"] or ""):
                self.win_rows[int(r["window"], 16)].append(r)
        self.menu_rows = {}
        p = os.path.join(DOCS, "menu_transitions.csv")
        if os.path.exists(p):
            for r in csv.DictReader(open(p, encoding="utf-8")):
                try:
                    self.menu_rows[int(r["site"], 16)] = r
                except (KeyError, ValueError):
                    pass
        # .data parameters the DLL rewrites (dinput8_proxy.cpp's kJogParams):
        # a read of one is the player movement's own conversion
        # the mode table's pairs mode_constants.h rewrites ({g^ts, g}): a read
        # at [mode - 1] with the mode byte pinned to 1 gets the converted slot
        self.mode_pairs = set(gtc.mode_pairs())
        self.data_params = {}
        src = open(os.path.join(ROOT, "src", "dinput8_proxy.cpp"), encoding="utf-8").read()
        g = re.search(r"kJogParams\[\] = \{(.*?)\n\};", src, re.S)
        for m in re.finditer(r'\{0x([0-9A-F]+), [-0-9.e]+f, [-\w]+, "([^"]+)"\}',
                             g.group(1) if g else ""):
            self.data_params[int(m.group(1), 16)] = "kJogParams (%s)" % m.group(2)

    def _census(self):
        def load(name):
            p = os.path.join(DOCS, name)
            return {r["site"]: r for r in csv.DictReader(open(p, encoding="utf-8"))} \
                if os.path.exists(p) else {}
        self.sites = load("sites.csv")
        self.cov = load("coverage.csv")
        self.reads = load("reads.csv")
        self.cls = load("classification.csv")

    def patch_at(self, a, relocated=False):
        """[(family, kind)] of every patch that converts the instruction at a.
        A world window converts only its row's own instruction; the others it
        relocates come back (with relocated=True) as `in <kind> window <site>`."""
        fn = self.func(a)
        size = fn.ins[a].size if fn is not None and a in fn.ins else 1
        out = []
        k = bisect.bisect_right(self.range_lo, a + size - 1) - 1
        while k >= 0 and self.ranges[k][1] > a - 64:
            s, e, fam = self.ranges[k]
            k -= 1
            if not (s < a + size and a < e):
                continue
            if fam == "world_anims.h":
                rows = self.win_rows.get(s, [])
                own = [r for r in rows if int(r["site"], 16) == a]
                if own:
                    out.append((fam, own[0]["kind"]))
                elif relocated:
                    out.append((fam, "in %s window %s" % (
                        "/".join(r["kind"] for r in rows) or "?", "/".join(r["site"] for r in rows))))
                continue
            if fam.startswith("world_anims"):
                row = self.rows.get(a) or self.rows.get(s)
                out.append((fam, row["kind"] if row else fam))
                continue
            if fam.startswith("menu_transitions"):
                row = self.menu_rows.get(a) or self.menu_rows.get(s)
                if row and fam == "menu_transitions.h" and int(row["site"], 16) != a \
                        and not relocated:
                    continue             # relocated with a row of its window
                out.append((fam, "menu " + row["kind"] if row else fam.replace(".h", "")))
                continue
            out.append((fam, fam.replace(".h", "")))
        return out

    def census(self, a):
        key = "%X" % a
        s, c, r = self.sites.get(key), self.cov.get(key), self.reads.get(key)
        if not s:
            return ""
        txt = "%s %s" % (c["status"] if c else "?", s["shape"])
        if c and c.get("family"):
            txt += " (%s)" % c["family"]
        if r:
            txt += " read:%s" % r["verdict"]
        return txt

    # -- functions -----------------------------------------------------------
    def func(self, rva):
        k = bisect.bisect_right(self.frag_lo, rva) - 1
        if k < 0 or not (self.frag[k][0] <= rva < self.frag[k][1]):
            # a leaf function has no unwind entry: the decompile's bounds
            j = bisect.bisect_right(self.dstarts, rva) - 1
            if j < 0:
                return None
            root = self.dstarts[j]
            end = self.dstarts[j + 1] if j + 1 < len(self.dstarts) else root + 0x1000
            k2 = bisect.bisect_right(self.frag_lo, root)
            if k2 < len(self.frag_lo):
                end = min(end, self.frag_lo[k2])
            if not root <= rva < end:
                return None
            frags = [(root, end)]
        else:
            root, frags = self.roots[self.frag[k][0]]
        fn = self.funcs.get(root)
        if fn is None:
            fn = gtc.Func(self.img, root, frags, self.md)
            self._edges(fn)
            self.funcs[root] = fn
        return fn

    def _edges(self, fn):
        """direct edges; a `jmp reg` to its own switch table's destinations
        (tables the parser cannot read keep Func's every-indirect-jump preds)"""
        succ = {}
        unresolved = []
        for k, a in enumerate(fn.order):
            i = fn.ins[a]
            ss = [x for x in fn.succs(i) if x in fn.ins]
            if i.mnemonic == "jmp" and i.operands[0].type != X.X86_OP_IMM:
                ss = []
                for j in range(k - 1, max(-1, k - 7), -1):
                    pi = fn.ins[fn.order[j]]
                    g = TBL.match(pi.op_str) if pi.mnemonic == "mov" else None
                    if g:
                        tbl = int(g.group(4), 16)
                        for e in range(4096):
                            t = struct.unpack_from("<I", self.img, tbl + 4 * e)[0]
                            if t not in fn.ins:
                                break
                            ss.append(t)
                        break
                if not ss:
                    unresolved.append(a)
            succ[a] = ss
        preds = collections.defaultdict(list)
        for a, ss in succ.items():
            for s in ss:
                preds[s].append(a)
        if unresolved:
            for a in fn.order:
                if a != fn.root and not preds.get(a):
                    preds[a] = list(unresolved)
        fn.succ = succ
        fn.preds = preds

    def slicer(self, rva):
        fn = self.func(rva)
        if fn is None:
            return None
        sl = self.slicers.get(fn.root)
        if sl is None:
            sl = self.slicers[fn.root] = Slicer(self, fn)
        return sl

    def callee(self, i):
        op = i.operands[0]
        if op.type == X.X86_OP_IMM:
            return self.thunks.get(op.imm, op.imm)
        if op.type == X.X86_OP_MEM and op.mem.base == X.X86_REG_RIP:
            return self.iat.get(gtc.rip_target(i, op))
        return None

    def callee_name(self, t):
        if t is None:
            return "indirect"
        if isinstance(t, str):
            return KERNEL_SHORT.get(t, t)
        nm = NAMES.get(t)
        return "%X %s" % (t, nm) if nm else "%X" % t

    def section(self, t):
        for name, (a, b) in self.secs.items():
            if a <= t < b:
                return name
        return None

    def rip_leaf(self, a, t, size):
        if t in RATE:
            return ("rate", a, RATE[t])
        if MODE_TABLE[0] <= t < MODE_TABLE[1]:
            return ("table", a, t)
        if self.section(t) == ".rdata":
            if size == 8:
                v = struct.unpack_from("<d", self.img, t)[0]
            elif size in (1, 2):
                v = int.from_bytes(self.img[t:t + size], "little")
            else:
                raw = struct.unpack_from("<I", self.img, t)[0]
                v = struct.unpack_from("<f", self.img, t)[0]
                if raw and not (1e-9 < abs(v) < 1e9):
                    v = raw
            return ("const", a, t, v)
        return ("global", a, t)

    def owner_of(self, rva):
        fn = self.func(rva)
        return self.owners.get(fn.root, frozenset()) if fn is not None else frozenset()

    def fn_label(self, root):
        own = sorted(self.owners.get(root, ()))
        slots = self.vtslots.get(root, [])
        s = "%X" % root
        if own:
            s += " [%s%s]" % (" ".join(own[:4]), " +%d" % (len(own) - 4) if len(own) > 4 else "")
        if slots:
            s += " vt%s" % ",".join(sorted({str(i) for _c, i in slots})[:3])
        return s


def _disp_of(expr):
    """(disp, base, index) of an address expression `rbx + rsi*8 + 0x1444`, or
    None for the stack, rip and absolute addresses"""
    parts = [p.strip() for p in re.split(r"(?=[+-])", expr.replace(" ", "")) if p.strip()]
    disp, base, index = 0, None, None
    for p in parts:
        sign = -1 if p.startswith("-") else 1
        p = p.lstrip("+-")
        if re.match(r"^(0x[0-9a-f]+|\d+)$", p):
            disp += sign * int(p, 0)
        elif "*" in p:
            index = p.split("*")[0]
        elif base is None:
            base = p
        else:
            index = p
    if base is None or base in ("rsp", "esp", "rip"):
        return None
    return disp, base, index


# ---------------------------------------------------------------------------
# the store's own location, and the split into steps
# ---------------------------------------------------------------------------

class Alt:
    def __init__(self):
        self.self_seen = False
        self.steps = []          # (sign, tree, join address, blend?)
        self.factors = []        # (join address, tree)
        self.clamps = []
        self.wraps = []
        self.set = None
        self.complex = None

    def copy(self):
        n = Alt()
        n.self_seen = self.self_seen
        n.steps, n.factors = list(self.steps), list(self.factors)
        n.clamps, n.wraps = list(self.clamps), list(self.wraps)
        n.set, n.complex = self.set, self.complex
        return n


class Site:
    """One store and its value's trace."""

    def __init__(self, tr, site):
        self.tr, self.site = tr, site
        self.sl = tr.slicer(site)
        self.ok = False
        self.why = ""
        if self.sl is None:
            self.why = "no function"
            return
        fn = self.sl.fn
        i = fn.ins.get(site)
        if i is None:
            self.why = "not an instruction start"
            return
        self.ins = i
        mops = [o for o in i.operands if o.type == X.X86_OP_MEM and o.access & capstone.CS_AC_WRITE]
        if not mops:
            self.why = "no memory write at %X (%s %s)" % (site, i.mnemonic, i.op_str)
            return
        self.mop = mops[0]
        mm = self.mop.mem
        self.base = gtc.reg_key(i, mm.base) if mm.base else None
        self.index = gtc.reg_key(i, mm.index) if mm.index else None
        self.disp, self.scale, self.size = mm.disp, mm.scale, self.mop.size
        self.fn = fn
        self.tree = self._value()
        self.alts = split(self.tree, self.is_self)
        self.ok = True

    def _value(self):
        i, sl = self.ins, self.sl
        m = i.mnemonic
        a = i.address
        src = [o for o in i.operands if o is not self.mop]
        old = ("field", a, self.base, self.disp, self.index, self.scale, self.size,
               sl.value(a, self.base) if self.base else None)
        if m in MOVES:
            if not src:
                return ("opaque", a, i.op_str)
            return sl.opnd(i, src[0], 0)
        if m in ("inc", "dec", "neg", "not"):
            return ("op", a, m, old, None)
        if m in BINOPS and src:
            return ("op", a, m, old, sl.opnd(i, src[0], 0))
        return ("opaque", a, "%s %s" % (m, i.op_str))

    def is_self(self, leaf):
        if leaf[0] != "field":
            return False
        _k, a, base, disp, index, scale, size, btree = leaf
        if disp != self.disp or (index is None) != (self.index is None):
            return False
        if a == self.site:
            return True
        if index is not None and index != self.index:
            return False
        sl = self.sl
        if base == self.base and base is not None:
            if sorted(sl.defs(a, base)) == sorted(sl.defs(self.site, base)):
                return True
        r = Render(self.tr)
        mine = sl.value(self.site, self.base) if self.base else None
        return mine is not None and btree is not None and r(btree) == r(mine)


def contains_self(t, selfp):
    return any(selfp(x) for x in leaves(t))


def split(t, selfp):
    """[Alt]: the store's value as the self leaf plus steps, one per path"""
    k = t[0] if isinstance(t, tuple) and t else None
    if k == "phi":
        out = []
        for x in t[1]:
            out.extend(split(x, selfp))
        return out
    if k == "stack":
        return split(t[3], selfp)
    if k == "field" and selfp(t):
        a = Alt()
        a.self_seen = True
        return [a]
    if k == "wrap":
        alts = split(t[2], selfp)
        for a in alts:
            a.wraps.append(t[1])
        return alts
    if k == "conv" and t[2] in ("cvtss2sd", "cvtsd2ss", "movzx", "movsx", "movsxd", "cdqe",
                                "cwde", "cvtps2pd", "cvtpd2ps"):
        return split(t[3], selfp)
    if k == "op":
        _o, at, m, L, R = t
        sL = contains_self(L, selfp)
        sR = R is not None and contains_self(R, selfp)
        if m in ("inc", "dec") and sL:
            alts = split(L, selfp)
            for a in alts:
                a.steps.append((1 if m == "inc" else -1, ("imm", at, 1), at, False))
            return alts
        if m in ADDS or m in SUBS:
            sign = 1 if m in ADDS else -1
            if sL and not sR:
                alts = split(L, selfp)
                for a in alts:
                    a.steps.append((sign, R, at, False))
                return alts
            if sR and not sL and m in ADDS:
                alts = split(R, selfp)
                for a in alts:
                    a.steps.append((1, L, at, False))
                return alts
            if sL and sR:
                # x + (t - x) k, x - (x - t) k: the self on one side whole
                for whole, other, sg in ((L, R, sign), (R, L, 1)):
                    if whole[0] == "field" and selfp(whole) and (sg == 1 or whole is L):
                        a = Alt()
                        a.self_seen = True
                        a.steps.append((sg, other, at, True))
                        return [a]
                a = Alt()
                a.complex = t
                return [a]
            if sR and not sL:
                a = Alt()
                a.complex = t
                return [a]
        if m in CLAMPS and sL and not sR:
            alts = split(L, selfp)
            for a in alts:
                a.clamps.append((m, R))
            return alts
        if m in CLAMPS and sR and not sL:
            alts = split(R, selfp)
            for a in alts:
                a.clamps.append((m, L))
            return alts
        if m in MULS and (sL != sR):
            inner, other = (L, R) if sL else (R, L)
            alts = split(inner, selfp)
            for a in alts:
                a.factors.append((at, other, m))
            return alts
        if m in ("and", "or", "andps", "pand") and sL and not sR:
            alts = split(L, selfp)
            for a in alts:
                a.clamps.append((m, R))
            return alts
    if t is not None and contains_self(t, selfp):
        a = Alt()
        a.complex = t
        return [a]
    a = Alt()
    a.set = t
    return [a]


# ---------------------------------------------------------------------------
# verdicts and sources
# ---------------------------------------------------------------------------

def step_patches(tr, step_tree, join):
    addrs = node_addrs(step_tree)
    addrs.add(join)
    out = []
    for a in sorted(addrs):
        for fam, kind in tr.patch_at(a):
            out.append((a, fam, kind))
    return out


YES, PART, NO = 2, 1, 0


# helpers whose result is a step clamped to a limit argument: the result is
# converted when the limit is (2DDF90: sign x min(|angle to the point - xmm1|,
# xmm3), its code)
CLAMP_HELPERS = {0x2DDF90: "xmm3"}
# the same through out-pointers: 2DE0A0 writes two turn deltas through its
# 7th and 8th arguments, each clamped to its 5th or 6th (stack arguments at
# the call's rsp + 0x20 and + 0x28); converted when both limits are
CLAMP_MEM_HELPERS = {0x2DE0A0: (0x20, 0x28)}


def converted(tr, t, memo=None, ones=False, why=None):
    """Does every path of the value t go through a converting patch? YES, PART
    (some paths, or one term of a sum) or NO. A patch at a node's instruction
    converts what that instruction produces (lin on its literal, dst or zfirst
    on its multiply, count on its add, step on the field's load); a product is
    converted by either factor, a quotient by its dividend, a sum or a clamp
    only by both sides, a choice only by every alternative. Zero needs nothing;
    nor does 1.0 when `ones` (a blend's factor of 1 is a snap). Two engine
    conversions count too: a product with the time scale (the port's own
    `x ts`) and a clamp helper's result whose limit is converted. A choice
    one of whose constants mode_constants.h rewrites is the engine's mode
    selection (the mode byte is pinned): converted. `why` collects the
    reasons."""
    if memo is None:
        memo = {}
    key = (id(t), ones)
    if key in memo:
        return memo[key]
    memo[key] = NO
    v = _converted(tr, t, memo, ones, why)
    memo[key] = v
    return v


def _converted(tr, t, memo, ones, why):
    if not isinstance(t, tuple) or not t:
        return NO
    k = t[0]

    def note(s):
        if why is not None and s not in why:
            why.append(s)
    if k == "phi":
        if any(x[0] == "const" and any(kd == "mode_constants" for _f, kd in tr.patch_at(x[1]))
               for x in t[1] if isinstance(x, tuple) and x):
            note("mode-selected constant")
            return YES
        vs = {converted(tr, x, memo, ones, why) for x in t[1]}
        return YES if vs == {YES} else NO if vs == {NO} else PART
    if len(t) > 1 and isinstance(t[1], int):
        p = tr.patch_at(t[1])
        if p:
            note("%X %s" % (t[1], "/".join(kd for _f, kd in p)))
            return YES
    if k in ("const", "imm"):
        v = t[3] if k == "const" else t[2]
        if v == 0 or (ones and v == 1):
            return YES
        return NO
    if k == "rate" and t[2] == "time scale":
        note("the port's time scale %X" % t[1])
        return YES
    if k == "callret" and t[3] in CLAMP_HELPERS:
        sl = tr.slicer(t[1])
        lim = sl.value(t[1], CLAMP_HELPERS[t[3]])
        c = converted(tr, lim, memo, False, why)
        if c == YES:
            note("%X's limit %s converted" % (t[1], CLAMP_HELPERS[t[3]]))
        return c
    if k == "callmem" and t[2] in CLAMP_MEM_HELPERS:
        sl = tr.slicer(t[1])
        if sl.frame.ok:
            cs = [converted(tr, sl.stack_value(t[1], sl.frame.rsp + o, 4, 0), memo, False, why)
                  for o in CLAMP_MEM_HELPERS[t[2]]]
            if min(cs) == YES:
                note("%X's limits converted" % t[1])
            return min(cs)
        return NO
    if k == "table" and t[2] in tr.mode_pairs:
        note("mode_constants.h's pair %X" % t[2])
        return YES
    if k == "field" and isinstance(t[7], tuple) and t[7][0] == "lea" and \
            t[7][2] + t[3] in tr.mode_pairs:
        note("mode_constants.h's pair %X" % (t[7][2] + t[3]))
        return YES
    if k == "global" and t[2] in tr.data_params:
        note("%s %X" % (tr.data_params[t[2]], t[2]))
        return YES
    if k == "callret" and t[3] == TURN:
        note("FixTurnRate converts 2DA510's k at its entry")
        return YES
    if k == "op":
        m, L, R = t[2], t[3], t[4]
        if R is None:
            return converted(tr, L, memo, ones, why) if m in ("neg", "not") else NO
        if m in CLAMPS and callable(ones):
            # a blend clamped to a limit: min(limit, t - x); the side holding
            # the remaining distance is a snap, the limit must be converted
            sides = [converted(tr, x, memo, ones, why) if not contains_self(x, ones) else YES
                     for x in (L, R)]
            return min(sides)
        cl, cr = converted(tr, L, memo, ones, why), converted(tr, R, memo, ones, why)
        if m in ("mulss", "mulsd", "mulps", "imul"):
            return max(cl, cr)
        if m in ("divss", "divsd", "divps", "shl", "sal", "shr", "sar"):
            return cl
        if m in ADDS or m in SUBS or m in CLAMPS:
            return min(cl, cr)
        if m in ("xorps", "andps", "andnps", "orps"):
            return cl if R[0] == "const" else min(cl, cr)
        return min(cl, cr)
    if k == "conv":
        return converted(tr, t[3], memo, ones, why)
    if k == "wrap":
        return converted(tr, t[2], memo, ones, why)
    if k == "stack":
        return converted(tr, t[3], memo, ones, why)
    return NO


def unconverted_leaves(tr, t, out=None, ones=False):
    """the leaves of the paths of t that no patch converts"""
    if out is None:
        out = []
    if not isinstance(t, tuple) or not t or converted(tr, t, ones=ones) == YES:
        return out
    k = t[0]
    if k == "phi":
        for x in t[1]:
            unconverted_leaves(tr, x, out, ones)
    elif k == "op":
        unconverted_leaves(tr, t[3], out, ones)
        if t[4] is not None and t[2] not in ("divss", "divsd", "divps"):
            unconverted_leaves(tr, t[4], out, ones)
    elif k in ("conv", "stack"):
        unconverted_leaves(tr, t[3], out, ones)
    elif k == "wrap":
        unconverted_leaves(tr, t[2], out, ones)
    elif t not in out:
        out.append(t)
    return out


WRAP_SIZES = (1.0, 2.0, 3.1415927, 6.2831855, 180.0, 360.0, 0x10000, 0x8000)


def const_value(tr, s, t):
    """the constant a step tree is, or None"""
    while isinstance(t, tuple) and t and t[0] in ("stack", "conv"):
        t = t[3]
    if isinstance(t, tuple) and t and t[0] == "const" and isinstance(t[3], (int, float)):
        return float(t[3])
    if isinstance(t, tuple) and t and t[0] == "imm":
        return float(t[2])
    if isinstance(t, tuple) and t and t[0] == "phi":
        vs = {const_value(tr, s, x) for x in t[1]}
        return vs.pop() if len(vs) == 1 else None
    return None


def is_wrap(tr, s, sign, st, join):
    """A constant step whose add runs only when a compare of the running value
    against a bound sent it there: `if (u > 1) u -= 1`, `if (p >= 240) p -=
    240`, `if (a > 0x400) a -= 0x800`. The block holding the add is entered
    from a conditional branch whose flags come from a comiss/ucomiss/cmp
    reading the add's own destination register (or the field itself), and the
    step is the bound, twice the bound, or a period (1, 2, pi, 2 pi, 180, 360,
    0x8000, 0x10000)."""
    v = const_value(tr, s, st)
    if v is None or v == 0:
        return False
    fn = s.fn
    ji = fn.ins.get(join)
    if ji is None or not ji.operands or ji.operands[0].type != X.X86_OP_REG:
        return False
    acc = gtc.reg_key(ji, ji.operands[0].reg)
    jccs = []
    a, n = join, 0
    while n < 8:
        ps = fn.preds.get(a, [])
        if len(ps) != 1:
            break
        p = fn.ins[ps[0]]
        if p.mnemonic.startswith("j") or p.address + p.size != a:
            if p.mnemonic.startswith("j") and p.mnemonic != "jmp":
                jccs.append(p)
            break
        a, n = ps[0], n + 1
    else:
        return False
    if not jccs:
        for pa in fn.preds.get(a, []):
            p = fn.ins[pa]
            if p.mnemonic.startswith("j") and p.mnemonic != "jmp":
                jccs.append(p)
    for p in jccs:
        ok, bound = _guard(fn, p, acc, s)
        if not ok:
            continue
        if any(abs(abs(v) - w) < 1e-4 * max(1.0, w) for w in WRAP_SIZES):
            return True
        if bound is not None and bound != 0 and \
                any(abs(abs(v) - m * abs(bound)) < 1e-4 * abs(v) for m in (1, 2)):
            return True
    return False


def _guard(fn, jcc, acc, s):
    """(True, bound) when the flags jcc tests come from a compare reading acc
    (or the field); bound is the compare's other side when it is a constant"""
    a = jcc.address
    for _ in range(4):
        ps = fn.preds.get(a, [])
        if len(ps) != 1:
            return False, None
        a = ps[0]
        i = fn.ins[a]
        if i.mnemonic in ("comiss", "ucomiss", "comisd", "ucomisd", "cmp", "test"):
            hit, other = False, None
            for op in i.operands:
                if op.type == X.X86_OP_REG and gtc.reg_key(i, op.reg) == acc:
                    hit = True
                elif op.type == X.X86_OP_MEM and op.mem.disp == s.disp and \
                        op.mem.base != X.X86_REG_RIP:
                    hit = True
                else:
                    other = op
            if not hit:
                return False, None
            bound = None
            if other is not None:
                if other.type == X.X86_OP_IMM:
                    bound = float(other.imm)
                else:
                    t = s.sl.opnd(i, other, 0)
                    bound = const_value(None, s, t)
            return True, bound
        if "rflags" in {i.reg_name(r) for r in i.regs_access()[1]}:
            return False, None
    return False, None


def step_verdict(tr, s, sign, st, join, blend, why):
    p = tr.patch_at(join)
    if p:
        why.append("%X %s" % (join, "/".join(k for _f, k in p)))
        return "scaled"
    c = converted(tr, st, ones=s.is_self if blend else False, why=why)
    if c == YES:
        return "scaled"
    if is_wrap(tr, s, sign, st, join):
        why[:] = ["a guarded add of the wrap's size"]
        return "wrap"
    if c == PART:
        return "partly"
    return "blend" if blend else "unscaled"


def fn_gate(tr, fn, depth=0):
    """a gatefn/gate0 row at the function's entry, a task wait the function
    calls that task_waits.h paces (the task's loop runs a stock tick's worth
    of ticks per wait), or every direct call of the function gated: a
    callgate on the call, or a caller gated the same way (two levels)"""
    for fam, kind in tr.patch_at(fn.root):
        if kind in GATE_KINDS:
            return kind
    for a in fn.order:
        i = fn.ins[a]
        if i.mnemonic in ("call", "jmp") and any(f == "task_waits.h" for f, _k in tr.patch_at(a)):
            return "task_waits %X" % a
    sites = tr.callers.get(fn.root, [])
    if not sites or depth >= 2 or tr.vtslots.get(fn.root):
        return None
    why = []
    for c in sites:
        if any(k in ("callgate", "gatefn") for _f, k in tr.patch_at(c)):
            why.append("callgate %X" % c)
            continue
        cf = tr.func(c)
        g = fn_gate(tr, cf, depth + 1) if cf is not None else None
        if g is None:
            return None
        why.append("%X %s" % (cf.root, g))
    return "callers: " + "; ".join(why)


def classify(tr, s):
    """(verdict, [lines]) for a Site"""
    gate = fn_gate(tr, s.fn)
    verdicts, lines = [], []
    r = Render(tr)
    sp = tr.patch_at(s.site)
    if sp:
        # count on the store, mulstore, immstore: the whole update converted
        kinds = "/".join(k for _f, k in sp)
        return "scaled", ["store %X %s" % (s.site, kinds)]
    for n, a in enumerate(s.alts):
        tag = "path %d" % (n + 1)
        if a.complex is not None:
            verdicts.append("complex")
            lines.append("%s: complex %s" % (tag, r(a.complex)))
            continue
        if a.set is not None:
            # a reset beside the update's steps, or a value a converted call
            # (callscale, callblend) or a converted expression produces
            why = []
            c = converted(tr, a.set, why=why)
            v = "scaled" if c == YES else "set"
            verdicts.append(v)
            lines.append("%s: set = %s%s" % (tag, r(a.set), (" -> scaled [" + ", ".join(why) + "]")
                                             if v == "scaled" else ""))
            continue
        extras = []
        if a.factors:
            extras.append("factors " + ", ".join("%s %s" % (m, r(f)) for _at, f, m in a.factors))
        if a.clamps:
            extras.append("clamps " + ", ".join("%s %s" % (m, r(c)) for m, c in a.clamps))
        if a.wraps:
            extras.append("wrapped")
        if not a.steps:
            if a.factors:
                why = []
                cs = [YES if tr.patch_at(at) else converted(tr, f, why=why)
                      for at, f, _m in a.factors]
                ok = max(cs) == YES
                verdicts.append("scaled" if ok else "factor")
                extras.append("factor %s%s" % ("converted" if ok else "unconverted",
                                               (" [" + ", ".join(why) + "]") if why else ""))
            else:
                verdicts.append("copy")
            lines.append("%s: x = x%s" % (tag, ("; " + "; ".join(extras)) if extras else ""))
            continue
        for sign, st, join, blend in a.steps:
            why = []
            v = step_verdict(tr, s, sign, st, join, blend, why)
            verdicts.append(v)
            lines.append("%s: %s %s%s at %X -> %s%s" % (
                tag, "+" if sign > 0 else "-", "blend " if blend else "", r(st), join, v,
                (" [" + ", ".join(why) + "]") if why else ""))
        if extras:
            lines.append("%s: %s" % (tag, "; ".join(extras)))
    order = ["unscaled", "partly", "blend", "complex", "set", "factor", "copy", "wrap", "scaled"]
    if not verdicts:
        verdict = "?"
    elif gate:
        verdict = "gated(%s)" % gate
    else:
        vs = set(verdicts)
        if "set" in vs and vs - {"set"}:
            vs.discard("set")            # a reset beside the steps
        verdict = next(v for v in order if v in vs)
        if verdict in ("unscaled", "partly", "blend") and "scaled" in vs:
            verdict += "+scaled"
        if verdict == "wrap" and "scaled" in vs:
            verdict = "scaled"           # the steps are converted; the rest wraps
    return verdict, lines


def unscaled_leaves(tr, s):
    """the leaves of every step's paths no patch converts, deduplicated"""
    out = []
    for a in s.alts:
        for sign, st, join, blend in a.steps:
            if step_verdict(tr, s, sign, st, join, blend, []) in ("scaled", "wrap"):
                continue
            for lf in unconverted_leaves(tr, st, ones=s.is_self if blend else False):
                if lf not in out:
                    out.append(lf)
    return out


def describe_leaf(tr, s, lf, deep=True):
    """[lines] on where one leaf comes from"""
    r = Render(tr)
    k = lf[0]
    if k == "field":
        if s.is_self(lf):
            return ["%s: the update's own field" % r(lf)]
        lines = ["%s: field +%X" % (r(lf), lf[3])]
        if deep:
            lines += ["  " + x for x in field_writers(tr, s.fn.root, lf[3], lf[6], limit=14)]
        return lines
    if k == "const":
        return ["%s: constant %s" % (r(lf), "(patched)" if tr.patch_at(lf[1]) else "(unpatched)")]
    if k == "imm":
        return ["%s: immediate" % r(lf)]
    if k == "callret":
        lines = ["%s: returned by %s" % (r(lf), tr.callee_name(lf[3]))]
        if deep and isinstance(lf[3], int) and lf[3] not in NAMES:
            lines += ["  " + x for x in callee_returns(tr, lf[3], lf[2])]
        return lines
    if k == "param":
        lines = ["%s: argument of %X" % (lf[1], s.fn.root)]
        if deep:
            lines += ["  " + x for x in caller_args(tr, s.fn.root, lf[1])]
        return lines
    return ["%s" % r(lf)]


def callee_returns(tr, target, reg, limit=4, depth=0):
    """what a function returns in reg, at each ret; a tail jump to another
    function is followed (two levels)"""
    sl = tr.slicer(target)
    if sl is None:
        return ["(no function at %X)" % target]
    r = Render(tr, limit=300)
    out = []
    for a in sl.fn.order:
        if a not in sl.frame.live if hasattr(sl.frame, "live") else False:
            continue
        i = sl.fn.ins[a]
        if i.mnemonic == "ret":
            out.append("ret %X: %s" % (a, r(sl.value(a, reg))))
        elif i.mnemonic == "jmp" and i.operands[0].type == X.X86_OP_IMM and \
                i.operands[0].imm not in sl.fn.ins:
            t = tr.thunks.get(i.operands[0].imm, i.operands[0].imm)
            out.append("tail jump %X to %s" % (a, tr.callee_name(t)))
            if depth < 2 and isinstance(t, int):
                out += ["  " + x for x in callee_returns(tr, t, reg, limit, depth + 1)]
        if len(out) >= limit * 3:
            break
    return out or ["(no ret)"]


def caller_args(tr, root, reg, limit=8):
    sites = tr.callers.get(root, [])
    out = []
    r = Render(tr, limit=300)
    for c in sites[:limit]:
        sl = tr.slicer(c)
        if sl is None or c not in sl.fn.ins:
            continue
        out.append("call %X in %s: %s = %s" % (c, tr.fn_label(sl.fn.root), reg,
                                               r(sl.value(c, reg))))
    if len(sites) > limit:
        out.append("... %d more callers" % (len(sites) - limit))
    if not sites:
        slots = tr.vtslots.get(root, [])
        out.append("no direct callers%s" % (
            "; vtable slots " + ", ".join("%s[%d]" % cs for cs in slots[:6]) if slots else ""))
    return out


def field_writers(tr, fn_root, disp, size=4, limit=20, classes=None):
    """stores of +disp in functions the reading function's classes own"""
    own = tr.owners.get(fn_root, frozenset()) if classes is None else classes
    cands = tr.stores.get(disp, [])
    keep, other = [], 0
    for a, mn, op, lea in cands:
        fn = tr.func(a)
        if fn is None:
            continue
        o2 = tr.owners.get(fn.root, frozenset())
        if fn.root == fn_root or (own and o2 & own) or (not own and not o2 and
                                                        _near(tr, fn.root, fn_root)):
            keep.append((a, mn, op, lea, fn))
        else:
            other += 1
    r = Render(tr, limit=260)
    out = []
    for a, mn, op, lea, fn in keep[:limit]:
        sl = tr.slicer(a)
        if mn == "call":
            what = "%s on &[..+%X] (lea %X)" % (KERNEL_SHORT.get(op, op), disp, lea)
        else:
            i = fn.ins.get(a)
            if i is None:
                continue
            try:
                st = Site(tr, a)
                if st.ok:
                    vv, _l = classify(tr, st)
                    what = "%s: %s" % (vv, r(st.tree))
                else:
                    what = "%s %s" % (mn, op)
            except RecursionError:
                what = "%s %s (too deep)" % (mn, op)
        cen = tr.census(a)
        pt = tr.patch_at(a)
        out.append("%X in %s: %s%s%s" % (a, tr.fn_label(fn.root), what,
                                         ("  <<" + cen) if cen else "",
                                         ("  P " + ",".join(k for _f, k in pt)) if pt else ""))
    if len(keep) > limit:
        out.append("... %d more writers" % (len(keep) - limit))
    out.append("(%d stores of +%X elsewhere, in functions of other classes)" % (other, disp))
    return out


def field_uses(tr, fn_root, disp, limit=40):
    """Every store, in a function the reading function's classes own, whose
    value takes a step from +disp (not its own field): where a velocity is
    integrated. Each with its trace's verdict for that step."""
    own = tr.owners.get(fn_root, frozenset())
    roots = {fn_root} | {f for f, o in tr.owners.items() if own and o & own}
    r = Render(tr, limit=220)
    out = []
    for root in sorted(roots):
        fn = tr.func(root)
        if fn is None or fn.root != root:
            continue
        for a in fn.order:
            i = fn.ins[a]
            if not any(op.type == X.X86_OP_MEM and op.access & capstone.CS_AC_WRITE and
                       op.mem.base not in (X.X86_REG_RSP, X.X86_REG_RIP) for op in i.operands):
                continue
            try:
                s = Site(tr, a)
            except RecursionError:
                continue
            if not s.ok or s.disp == disp:
                continue
            hits = []
            for al in s.alts:
                for sign, st, join, blend in al.steps:
                    if any(lf[0] == "field" and lf[3] == disp for lf in leaves(st)):
                        v = step_verdict(tr, s, sign, st, join, blend, [])
                        hits.append("%s%s at %X -> %s" % ("+" if sign > 0 else "-", r(st), join, v))
            if hits:
                cen = tr.census(a)
                out.append("%X in %s: [%s+%X] %s%s" % (a, tr.fn_label(root), s.base, s.disp,
                                                     "; ".join(hits), ("  <<" + cen) if cen else ""))
                if len(out) >= limit:
                    return out + ["... (limit)"]
    return out or ["(no store takes a step from +%X in these classes' functions)" % disp]


def _near(tr, f1, f2):
    """unowned helpers: the writer calls or is called by the reader"""
    return f2 in {tr.func(c).root for c in tr.callers.get(f1, []) if tr.func(c)} or \
        f1 in {tr.func(c).root for c in tr.callers.get(f2, []) if tr.func(c)}


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------

def card(tr, site, deep=True):
    s = Site(tr, site)
    r = Render(tr)
    out = []
    fn = s.sl.fn if s.sl else None
    out.append("==== %X  %s" % (site, tr.fn_label(fn.root) if fn else "?"))
    if not s.ok:
        out.append("  " + s.why)
        return out, "?", s
    i = s.ins
    out.append("  store: %s %s   %s" % (i.mnemonic, i.op_str, tr.census(site)))
    out.append("  value: %s" % r(s.tree))
    verdict, lines = classify(tr, s)
    out += ["  " + ln for ln in lines]
    out.append("  verdict: %s" % verdict)
    if deep and verdict not in ("scaled",) and not verdict.startswith("gated"):
        for lf in unscaled_leaves(tr, s):
            out += ["    " + x for x in describe_leaf(tr, s, lf)]
    return out, verdict, s


def batch(tr, path, out_csv):
    entries = collections.OrderedDict()
    for ln in open(path, encoding="utf-8"):
        if not ln.strip() or ln.startswith("#") or ln.startswith("{"):
            continue
        p = [x.strip() for x in ln.split("|")]
        try:
            site = int(p[0].split()[0], 16)
        except ValueError:
            continue
        entries.setdefault(site, []).append(p)
    rows, tally = [], collections.Counter()
    for site, ps in entries.items():
        try:
            lines, verdict, s = card(tr, site, deep=False)
        except RecursionError:
            lines, verdict, s = ["==== %X too deep" % site], "?", None
        cl = tr.cls.get("%X" % site, {})
        rd = tr.reads.get("%X" % site, {})
        if verdict.split("+")[0] in ("unscaled", "partly", "blend", "set", "factor") and \
                cl.get("decision") == "exclude":
            # the census set it aside (state, pointer, input): listed, not a step
            verdict = "excluded(%s)" % cl.get("static_class", "?")
            lines[-1] = "  verdict: %s (%s)" % (verdict, cl.get("static_reason", ""))
        tally[verdict.split("(")[0]] += 1
        uns = []
        if s is not None and s.ok and verdict not in ("scaled",):
            rr = Render(tr, limit=200)
            for lf in unscaled_leaves(tr, s):
                if lf[0] == "field" and s.is_self(lf):
                    continue
                uns.append(rr(lf))
        rows.append(dict(site="%X" % site, function="%X" % (s.fn.root if s and s.ok else 0),
                         owners=ps[0][2] if len(ps[0]) > 2 else "",
                         verdict=verdict, read=rd.get("verdict", ""),
                         census=cl.get("static_class", ""),
                         value=" | ".join(lines[2:3]).replace("  value: ", ""),
                         steps=" || ".join(x.strip() for x in lines[3:] if x.strip().startswith("path")),
                         leaves=" ; ".join(uns)))
        print("\n".join(lines))
    if out_csv:
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print("\n%d sites: %s" % (len(rows), ", ".join("%s %d" % kv for kv in tally.most_common())))


PROBLEM_VERDICTS = ("unscaled", "partly", "blend", "complex", "set", "factor", "copy", "?")


def check(tr, broken=None):
    """The suite's check: every census site coverage counts covered (or the
    port's) traces converted, a wrap or gated, or has a reading in reads.csv
    or a census exclusion. 0 when nothing is left over."""
    if broken == "rows":
        # the world rows taken away: their steps must come back unconverted
        keep = [r for r in tr.ranges if not r[2].startswith("world_anims")]
        tr.ranges, tr.range_lo = keep, [r[0] for r in keep]
    sites = sorted(s for s, r in tr.cov.items() if r["status"] in ("covered", "port"))
    problems, tally = [], collections.Counter()
    for s in sites:
        try:
            _lines, v, _st = card(tr, int(s, 16), deep=False)
        except RecursionError:
            v = "?"
        base = v.split("(")[0].split("+")[0]
        tally[base] += 1
        if base in PROBLEM_VERDICTS and s not in tr.reads and \
                tr.cls.get(s, {}).get("decision") != "exclude":
            problems.append("%s %-16s %s (%s)" % (s, v, tr.cov[s]["shape"],
                                                 tr.cov[s]["family"] or "-"))
    print("%d covered or port sites: %s" % (len(sites), ", ".join(
        "%s %d" % kv for kv in tally.most_common())))
    for p in problems[:60]:
        print("PROBLEM   " + p)
    if len(problems) > 60:
        print("... %d more" % (len(problems) - 60))
    print("%d unconverted with no reading%s" % (len(problems),
                                                 " (rows taken away)" if broken else ""))
    return 1 if problems else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="every covered site converted or read (the suite's check)")
    ap.add_argument("--break", dest="broken", choices=["rows"],
                    help="with --check: take the world rows away (must fail)")
    ap.add_argument("sites", nargs="*")
    ap.add_argument("--field", nargs=2, metavar=("FN", "DISP"))
    ap.add_argument("--uses", nargs=2, metavar=("FN", "DISP"),
                    help="stores in FN's classes that add a step from +DISP")
    ap.add_argument("--open", metavar="FILE")
    ap.add_argument("--out", metavar="CSV")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--shallow", action="store_true", help="no sources")
    args = ap.parse_args()
    sys.setrecursionlimit(20000)
    tr = Tracer(rebuild=args.rebuild)
    if args.check:
        sys.exit(check(tr, args.broken))
    if args.field:
        fn = tr.func(int(args.field[0], 16))
        disp = int(args.field[1], 16)
        print("writers of +%X for %s:" % (disp, tr.fn_label(fn.root)))
        print("\n".join("  " + x for x in field_writers(tr, fn.root, disp, limit=60)))
    if args.uses:
        fn = tr.func(int(args.uses[0], 16))
        disp = int(args.uses[1], 16)
        print("steps from +%X in %s's classes:" % (disp, tr.fn_label(fn.root)))
        print("\n".join("  " + x for x in field_uses(tr, fn.root, disp)))
    if args.open:
        batch(tr, args.open, args.out)
    for a in args.sites:
        lines, _v, _s = card(tr, int(a, 16), deep=not args.shallow)
        print("\n".join(lines))


if __name__ == "__main__":
    main()
