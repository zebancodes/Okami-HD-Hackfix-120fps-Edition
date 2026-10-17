#!/usr/bin/env python3
"""Code that runs once per phase of a state: a state handler's set-up block.

The state handlers keep a phase byte beside the state (+E36 in the actors',
the people's and the weapons' layout): `switch (phase) { case 0: set up;
phase++; case 1: ... }`. What the set-up block does happens once each time
the state starts, whatever the frame rate. A turn toward the target there is
an aim, not a per-tick step, and scaling its limit by s, as the steer group
scales a per-tick turn's, took 3/4 of the aim away at 120 (2026-10-10: wp47
39BB10's turn of up to 30 degrees toward its target as it is thrown).

    once(fn, site) -> a note saying why, or None

`site`, an instruction of the gen_turn_callers.Func `fn`, runs once per phase
when, for one byte [R + d] and one value v:

  gate     it cannot be reached from the function's entry once the branch
           edges taken only while the byte is v are removed. Such an edge is
           a je/jne whose flags come, in straight-line code, from `cmp byte
           [R + d], imm`, or from `test r, r` / `cmp r, imm` / `sub r, imm`
           / `dec r` on r = the byte as `movzx r, byte [R + d]` loaded it,
           less what the chain subtracted before (a switch's `sub ecx, 1;
           je`);
  advance  every path from it to a return writes the byte with something
           other than v (`inc`, `add` of a nonzero immediate, a store of
           another immediate, or a wider store of an immediate whose byte at
           d is not v), and nothing after that on the path writes v back or
           an unknown value.

R is compared by value (gen_turn_callers.Slicer, so `mov rbx, rcx` keeps
the object): the load's base and the write's must render the same. An
indirect jump (a switch's `jmp rax`) is taken to reach every instruction
gen_turn_callers.Func gave it as a predecessor.

    .venv/Scripts/python tools/once_blocks.py SITE [SITE ...]
"""
import collections
import os
import sys

from capstone import x86_const as X

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_turn_callers as gtc  # noqa: E402

BACK = 12  # straight-line instructions searched back for a flag setter or a load


def _field(i, op):
    """(base register, displacement) of a memory operand with a base and no
    index, or None"""
    if op.type != X.X86_OP_MEM:
        return None
    m = op.mem
    if m.index != 0 or m.base in (0, X.X86_REG_RIP, X.X86_REG_RSP):
        return None
    return gtc.reg_key(i, m.base), m.disp


def _writes_flags(i):
    return X.X86_REG_EFLAGS in i.regs_access()[1]


def _straight_back(fn, a):
    """the instructions before `a` in straight-line code, nearest first"""
    out = []
    k = fn.order.index(a)
    while k > 0 and len(out) < BACK:
        prev = fn.order[k - 1]
        if fn.preds.get(fn.order[k], []) != [prev]:
            break
        out.append(fn.ins[prev])
        k -= 1
    return out


def _origin(fn, a, reg):
    """(load, R, d, k) when `reg` at `a` (before it runs) is the byte at
    [R + d] as the movzx at `load` loaded it, less k; else None"""
    k = 0
    for i in _straight_back(fn, a):
        if reg not in gtc.writes(i):
            continue
        ops = i.operands
        m = i.mnemonic
        if m == "movzx" and ops[1].type == X.X86_OP_MEM and ops[1].size == 1:
            f = _field(i, ops[1])
            return (i.address, f[0], f[1], k) if f else None
        if m in ("sub", "add") and ops[1].type == X.X86_OP_IMM:
            k += ops[1].imm if m == "sub" else -ops[1].imm
        elif m in ("dec", "inc"):
            k += 1 if m == "dec" else -1
        else:
            return None
    return None


def _equality(fn, s):
    """(load, R, d, v) when ZF after the flag setter `s` means [R + d] == v,
    as read at `load`"""
    ops = s.operands
    m = s.mnemonic
    if m == "cmp" and ops[0].type == X.X86_OP_MEM and ops[0].size == 1 and \
            ops[1].type == X.X86_OP_IMM:
        f = _field(s, ops[0])
        return (s.address, f[0], f[1], ops[1].imm & 0xFF) if f else None
    if not ops or ops[0].type != X.X86_OP_REG:
        return None
    reg = gtc.reg_key(s, ops[0].reg)
    if m == "test":
        if len(ops) != 2 or ops[1].type != X.X86_OP_REG or gtc.reg_key(s, ops[1].reg) != reg:
            return None
        add = 0
    elif m in ("cmp", "sub") and ops[1].type == X.X86_OP_IMM:
        add = ops[1].imm
    elif m == "dec":
        add = 1
    else:
        return None
    o = _origin(fn, s.address, reg)
    if o is None:
        return None
    v = o[3] + add
    return (o[0], o[1], o[2], v) if 0 <= v <= 0xFF else None


def _base(sl, at, reg):
    """the value of a base register at `at`, rendered: the object it points at"""
    return gtc.render(sl.value(at, reg))


def gates(fn, sl):
    """{(the base's value, d, v): [(je/jne, the successor taken only while
    [base + d] == v)]}"""
    out = collections.defaultdict(list)
    for a in fn.order:
        j = fn.ins[a]
        if j.mnemonic not in ("je", "jne") or j.operands[0].type != X.X86_OP_IMM:
            continue
        setter = None
        for i in _straight_back(fn, a):
            if _writes_flags(i):
                setter = i
                break
        eq = _equality(fn, setter) if setter is not None else None
        if eq is None:
            continue
        load, base, d, v = eq
        taken, fall = j.operands[0].imm, a + j.size
        if taken != fall:
            out[(_base(sl, load, base), d, v)].append((a, taken if j.mnemonic == "je" else fall))
    return out


def _succs(fn, i, ind):
    if i.address in ind:
        return ind[i.address]
    return fn.succs(i)


def _indirect(fn):
    """{indirect jump: the instructions Func gave it as a predecessor}"""
    out = collections.defaultdict(list)
    for a in fn.order:
        for p in fn.preds.get(a, ()):
            if p in fn.indirect:
                out[p].append(a)
    return out


def _write(sl, i, base, d, v):
    """how the instruction leaves [base + d], base a rendered value:
    "advance", "back" (v or an unknown value), or None (not written)"""
    if not i.operands or i.operands[0].type != X.X86_OP_MEM:
        return None
    f = _field(i, i.operands[0])
    if f is None or not f[1] <= d < f[1] + i.operands[0].size or \
            _base(sl, i.address, f[0]) != base:
        return None
    lo, size = f[1], i.operands[0].size
    m = i.mnemonic
    if m == "cmp" or m == "test":
        return None
    if m == "inc" and size == 1:
        return "advance"
    if m == "add" and size == 1 and i.operands[1].type == X.X86_OP_IMM:
        return "advance" if i.operands[1].imm & 0xFF else None
    if m == "mov" and i.operands[1].type == X.X86_OP_IMM:
        byte = (i.operands[1].imm >> (8 * (d - lo))) & 0xFF
        return "advance" if byte != v else "back"
    return "back"


def once(fn, site, sl):
    """a note when `site` runs once per phase (see the module's docstring),
    else None; sl is the function's gen_turn_callers.Slicer"""
    if site not in fn.ins:
        return None
    ind = _indirect(fn)
    for (base, d, v), edges in sorted(gates(fn, sl).items()):
        blocked = set(edges)
        seen, work = set(), [fn.root]
        while work:
            a = work.pop()
            if a in seen or a not in fn.ins:
                continue
            seen.add(a)
            for s in _succs(fn, fn.ins[a], ind):
                if (a, s) not in blocked:
                    work.append(s)
        if site in seen:
            continue
        # every path on to a return advances the byte, and keeps it advanced
        i0 = fn.ins[site]
        done, work, ok, wrote = set(), [(site + i0.size, False)], True, set()
        while work and ok:
            a, adv = work.pop()
            if (a, adv) in done:
                continue
            done.add((a, adv))
            if a not in fn.ins:  # a tail jump out of the function
                ok = adv
                continue
            i = fn.ins[a]
            w = _write(sl, i, base, d, v)
            if w == "advance":
                adv = True
                wrote.add(a)
            elif w == "back":
                adv = False
            if i.mnemonic in ("ret", "retf"):
                ok = adv
                continue
            for s in _succs(fn, i, ind):
                work.append((s, adv))
        if ok and wrote:
            return "once per phase: reached only while [%s + 0x%X] == %d (%s), which %s then " \
                   "advances" % (base, d, v, ", ".join("%X" % e[0] for e in sorted(edges)),
                                 ", ".join("%X" % w for w in sorted(wrote)))
    return None


def main():
    img, secs, _f, _sha = gtc.load_image()
    import bisect
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    roots, starts, _e = gtc.pdata_roots(img, secs)
    for arg in sys.argv[1:]:
        at = int(arg, 16)
        k = bisect.bisect_right(starts, at) - 1
        root, frags = roots[starts[k]]
        fn = gtc.Func(img, root, frags, md)
        sl = gtc.Slicer(img, secs, fn)
        print("%X (in %X): %s" % (at, root, once(fn, at, sl) or "not once per phase"))


if __name__ == "__main__":
    main()
