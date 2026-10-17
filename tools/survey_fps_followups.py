#!/usr/bin/env python3
"""Inventory FPS gaps outside the self-update census; never select patches.

Writes random_rolls.csv (including unsigned/ranged float and 32-bit integer wrappers),
forward_movers.csv, heading_movers.csv, vector_movers.csv (2DA3F0: the vector's origin
in rdx), motion_field_sets.csv and field_limit_counters.csv.
Coverage is exact instruction overlap or an entry gate, not proximity.
Random branch detection is a bounded straight-line register slice; other_use
and slice_limit still require review, and a branch is not proof of a clock.

    .venv/Scripts/python tools/survey_fps_followups.py
"""
import bisect
import collections
import contextlib
import csv
import hashlib
import io
import os
import re

import capstone
from capstone import x86 as X

import gen_world_anims as gwa
import read_candidates as rc
import xrefs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs", "animation")
RANDOM = {0x1BD480: "integer", 0x1BD590: "signed_float", 0x1BD580: "unsigned_float",
          0x1BD6D0: "integer32", 0x1BD620: "range_float"}
FIELDS = {0xE10, 0xE18, 0xE48, 0x1080, 0x10E8, 0xEC8}


def canonical(reg):
    if reg in ("al", "ah", "ax", "eax", "rax"):
        return "rax"
    for stem, names in (("rbx", ("bl", "bh", "bx", "ebx")),
                        ("rcx", ("cl", "ch", "cx", "ecx")),
                        ("rdx", ("dl", "dh", "dx", "edx")),
                        ("rsi", ("sil", "si", "esi")),
                        ("rdi", ("dil", "di", "edi")),
                        ("rbp", ("bpl", "bp", "ebp")),
                        ("rsp", ("spl", "sp", "esp"))):
        if reg == stem or reg in names:
            return stem
    return re.sub(r"^(r\d+)[dwb]$", r"\1", reg)


def random_use(seq, index, target, end, decode):
    tainted = {"rax" if RANDOM[target].startswith("integer") else "xmm0"}
    context, predicate = [], None
    for raw in seq[index + 1:index + 33]:
        ins = decode(raw)
        if ins.address >= end:
            break
        reads, writes = ins.regs_access()
        reads = {canonical(ins.reg_name(r)) for r in reads}
        writes = {canonical(ins.reg_name(r)) for r in writes}
        uses = bool(tainted & reads)
        if ins.mnemonic in ("xor", "sub", "xorps", "pxor") and len(ins.operands) == 2 \
                and all(op.type == X.X86_OP_REG for op in ins.operands) \
                and ins.operands[0].reg == ins.operands[1].reg:
            uses = False  # a zero idiom discards the random value
        context.append("%06X %s %s" % (ins.address, ins.mnemonic, ins.op_str))
        if ins.mnemonic == "call" or ins.mnemonic in ("ret", "jmp", "int3"):
            return "other_use", "", "", "; ".join(context)
        if ins.mnemonic.startswith("j"):
            if predicate is not None:
                return "branch_candidate", "%06X" % predicate, "%06X" % ins.address, "; ".join(context)
            return "other_use", "", "", "; ".join(context)
        if ins.mnemonic in ("cmp", "test", "comiss", "ucomiss", "comisd", "ucomisd"):
            predicate = ins.address if uses else None
        elif "rflags" in writes:
            # AND's flags can themselves feed the random branch.
            predicate = ins.address if uses and ins.mnemonic == "and" else None
        tainted -= writes
        if uses:
            tainted |= writes - {"rflags"}
        if not tainted and predicate is None:
            return "other_use", "", "", "; ".join(context)
    return "slice_limit", "", "", "; ".join(context)


def write_csv(name, rows, columns):
    reviews_path = os.path.join(DOCS, "followup_reviews.csv")
    reviews = list(csv.DictReader(open(reviews_path, encoding="utf-8")))
    by_site = {r["site"]: r for r in reviews if r["inventory"] == name}
    if len(by_site) != sum(r["inventory"] == name for r in reviews):
        raise RuntimeError("duplicate reviews for " + name)
    stale = set(by_site) - {r["site"] for r in rows}
    if stale:
        raise RuntimeError("stale reviews for %s: %s" % (name, sorted(stale)))
    for row in rows:
        review = by_site.get(row["site"])
        row["evidence"] = review["evidence"] if review else ""
        if review:
            row["review"] = review["verdict"]
    with open(os.path.join(DOCS, name), "w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=(*columns, "evidence"))
        wr.writeheader()
        wr.writerows(rows)


def main():
    _pe, base, img, _text = xrefs.load_bin("main.dll")
    sha = hashlib.sha1(open(os.path.join(xrefs.GAME, "main.dll"), "rb").read()).hexdigest()
    if sha != gwa.AUDITED_MAIN_SHA1:
        raise RuntimeError("main.dll differs from the audited build; nothing written")
    src = open(rc.DECOMP, encoding="utf-8").read()
    starts = [int(m.group(1), 16) for m in rc.FUNC_HDR.finditer(src)]
    def function(at):
        index = bisect.bisect_right(starts, at) - 1
        if index < 0:
            raise RuntimeError("no function for %X" % at)
        return starts[index], starts[index + 1] if index + 1 < len(starts) else len(img)
    with contextlib.redirect_stdout(io.StringIO()):
        ranges = rc.patched_ranges()
    gates = {rva: "%s %s" % (group, kind)
             for group, kind, rva, *_ in gwa.MANIFEST if kind in ("gatefn", "gate0")}
    def coverage(at, entry):
        exact = [label for lo, hi, label in ranges if lo <= at < hi]
        return " | ".join(exact), gates.get(entry, "")
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True
    # Decode at census boundaries, rather than a new linear sweep that may lose sync.
    raw = xrefs.cached_insns("main.dll")
    seq = [(a - base, m, o, size) for a, m, o, size in raw]
    def decode(raw):
        at, _m, _o, size = raw
        return next(md.disasm(img[at:at + size], at))
    field_pattern = re.compile(r" \+ 0x(?:e10|e18|e48|1080|10e8|ec8)\]")
    random_rows, mover_rows, heading_rows, vector_rows, field_rows = [], [], [], [], []
    for i, raw_ins in enumerate(seq):
        at, mnemonic, op_str, _size = raw_ins
        if not (mnemonic in ("call", "jmp") and op_str.startswith("0x") or
                mnemonic in ("mov", "movss") and field_pattern.search(op_str)):
            continue
        ins = decode(raw_ins)
        entry, end = function(ins.address)
        ops = ins.operands
        if ins.mnemonic in ("call", "jmp") and ops and ops[0].type == X.X86_OP_IMM:
            # A direct branch decoded at an RVA already has an RVA target.
            target = ops[0].imm
            if target in RANDOM:
                status, pred, branch, context = random_use(seq, i, target, end, decode)
                exact, gate = coverage(int(pred, 16) if pred else ins.address, entry)
                random_rows.append(dict(site="%06X" % ins.address, function="%06X" % entry,
                    generator="%06X" % target, kind=RANDOM[target], opcode=ins.mnemonic,
                    status=status, predicate=pred, branch=branch, exact_patch=exact,
                    entry_gate=gate, review="pending", context=context))
            elif target in (0x2DA410, 0x2DA460):
                origin = []
                for prev_raw in reversed(seq[max(0, i - 18):i]):
                    prev = decode(prev_raw)
                    if prev.address < entry or prev.mnemonic in ("call", "ret", "jmp"):
                        break
                    origin.append("%06X %s %s" % (prev.address, prev.mnemonic, prev.op_str))
                    _reads, writes = prev.regs_access()
                    if X.X86_REG_XMM1 in writes:
                        break
                exact, gate = coverage(ins.address, entry)
                (mover_rows if target == 0x2DA410 else heading_rows).append(dict(
                    site="%06X" % ins.address, function="%06X" % entry,
                    opcode=ins.mnemonic, exact_patch=exact, entry_gate=gate,
                    review="pending", argument_context="; ".join(reversed(origin))))
            elif target == 0x2DA3F0:
                # the vector's pointer: rdx's writer, through one register copy
                origin, want = [], {X.X86_REG_RDX}
                for prev_raw in reversed(seq[max(0, i - 24):i]):
                    prev = decode(prev_raw)
                    if prev.address < entry or prev.mnemonic in ("ret", "jmp"):
                        break
                    _reads, writes = prev.regs_access()
                    if want & set(writes):
                        origin.append("%06X %s %s" % (prev.address, prev.mnemonic, prev.op_str))
                        src = prev.operands[1] if len(prev.operands) == 2 else None
                        if prev.mnemonic == "mov" and src is not None and                                 src.type == X.X86_OP_REG:
                            want = {src.reg}
                            continue
                        break
                exact, gate = coverage(ins.address, entry)
                vector_rows.append(dict(site="%06X" % ins.address, function="%06X" % entry,
                    opcode=ins.mnemonic, exact_patch=exact, entry_gate=gate,
                    review="pending", argument_context="; ".join(reversed(origin))))
        if ins.mnemonic in ("mov", "movss") and len(ops) == 2 and ops[0].type == X.X86_OP_MEM \
                and ops[0].mem.disp in FIELDS and ops[0].size == 4 \
                and ops[0].mem.base not in (0, X.X86_REG_RIP):
            source, source_at = "unresolved", ""
            if ops[1].type == X.X86_OP_IMM:
                source = "immediate %08X" % (ops[1].imm & 0xFFFFFFFF)
                source_at = "%06X" % ins.address
            elif ops[1].type == X.X86_OP_REG:
                reg = canonical(ins.reg_name(ops[1].reg))
                for prev_raw in reversed(seq[max(0, i - 24):i]):
                    prev = decode(prev_raw)
                    if prev.address < entry or prev.mnemonic in ("call", "ret", "jmp") \
                            or prev.mnemonic.startswith("j"):
                        break
                    _reads, writes = prev.regs_access()
                    if reg in {canonical(prev.reg_name(r)) for r in writes}:
                        source = "%s %s" % (prev.mnemonic, prev.op_str)
                        source_at = "%06X" % prev.address
                        break
            exact, gate = coverage(ins.address, entry)
            field_rows.append(dict(site="%06X" % ins.address, function="%06X" % entry,
                field="+%X" % ops[0].mem.disp, instruction="%s %s" % (ins.mnemonic, ins.op_str),
                source=source, source_at=source_at, exact_patch=exact, entry_gate=gate,
                review="pending"))
    limits = []
    sites = {r["site"]: r for r in csv.DictReader(open(os.path.join(DOCS, "sites.csv")))}
    for row in csv.DictReader(open(os.path.join(DOCS, "static_classification.csv"))):
        if "ordered=field" in row["facts"] and sites[row["site"]]["size"] in ("1", "2", "4") \
                and sites[row["site"]]["shape"] in ("counter", "int-expr"):
            at = int(row["site"], 16)
            entry, _end = function(at)
            exact, gate = coverage(at, entry)
            limits.append(dict(site=row["site"], function=row["function"],
                field=sites[row["site"]]["field"], facts=row["facts"], exact_patch=exact,
                entry_gate=gate, review="pending"))
    write_csv("random_rolls.csv", random_rows, ("site", "function", "generator", "kind", "opcode",
        "status", "predicate", "branch", "exact_patch", "entry_gate", "review", "context"))
    write_csv("forward_movers.csv", mover_rows, ("site", "function", "opcode", "exact_patch",
        "entry_gate", "review", "argument_context"))
    write_csv("heading_movers.csv", heading_rows, ("site", "function", "opcode", "exact_patch",
        "entry_gate", "review", "argument_context"))
    write_csv("vector_movers.csv", vector_rows, ("site", "function", "opcode", "exact_patch",
        "entry_gate", "review", "argument_context"))
    write_csv("motion_field_sets.csv", field_rows, ("site", "function", "field", "instruction",
        "source", "source_at", "exact_patch", "entry_gate", "review"))
    write_csv("field_limit_counters.csv", limits, ("site", "function", "field", "facts",
        "exact_patch", "entry_gate", "review"))
    print("main.dll SHA1 " + sha)
    print("random calls/tails: %s; branch candidates: %d" %
          (dict(collections.Counter(r["kind"] for r in random_rows)),
           sum(r["status"] == "branch_candidate" for r in random_rows)))
    print("2DA410 calls/tails: %d, exact patches: %d, entry gates: %d" %
          (len(mover_rows), sum(bool(r["exact_patch"]) for r in mover_rows),
           sum(bool(r["entry_gate"]) for r in mover_rows)))
    print("2DA460 calls/tails: %d, exact patches: %d, entry gates: %d" %
          (len(heading_rows), sum(bool(r["exact_patch"]) for r in heading_rows),
           sum(bool(r["entry_gate"]) for r in heading_rows)))
    print("2DA3F0 calls/tails: %d, exact patches: %d, reviewed: %s" %
          (len(vector_rows), sum(bool(r["exact_patch"]) for r in vector_rows),
           dict(collections.Counter(r["review"] for r in vector_rows))))
    print("motion field stores: %d; counters compared with another field: %d" %
          (len(field_rows), len(limits)))


if __name__ == "__main__":
    main()
