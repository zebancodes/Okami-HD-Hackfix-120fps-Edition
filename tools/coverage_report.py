#!/usr/bin/env python3
"""How far along the patch is: every candidate in docs/animation/sites.csv
against what the tables patch today and what the classification decided.

The plan's goal: every candidate patched or excluded with a
reason. A candidate is a self-updating store the census found; this sorts
each one into

  library     linked middleware (CRI, CRT), excluded wholesale
  covered     a patched range of any family lies in the same function within
              8 bytes of the update's load .. store (the rule
              animation_inventory.py used for `covered_by` in 2026-09), and on
              the update's own path: an instruction of the range lies on a
              path from the load to the store, or (in the 8 bytes before the
              load or after the store) on a path into the load or out of the
              store. A range only on another branch (2026-10-09: em8f's and
              uta4's bob phases counted covered by the other branch's row)
              does not cover; the column `offpath` names it
  excluded    classification.csv decided `exclude` (its static reason says why)
  port        the port already scales it by the time scale (audit only)
  read        read by hand (docs/animation/reads.csv, a verdict per site): a row
              further away fixes it, or it needs nothing (it follows something
              already at stock pace, runs once per event, ...), and why
  near        none of those, but a patched range in the same function within
              64 bytes: a scaled step computed a little before the load, as
              many world rows are. Counted apart: probably covered, unproven
  to-patch    classified to patch (`patch`, `patch-static`), nothing near it
  review      classified `review`: not yet read
  unclassified  not in classification.csv

Patched ranges come from check_patch_sites.all_sites (every family's
tables, parsed exactly); function starts from the decompile's headers.

    .venv/Scripts/python tools/coverage_report.py [--decomp PATH] [--out docs/animation]

Writes OUT/coverage.csv (a row per candidate: status, the covering family and
its distance) and OUT/coverage.md (the counts); prints the counts.
"""
import argparse
import bisect
import collections
import contextlib
import csv
import datetime
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_patch_sites as cps  # noqa: E402
import event_counters as ec  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, ".."))
DOCS = os.path.join(ROOT, "docs", "animation")
DECOMP = os.path.expanduser(r"~\tools\main_decompiled.c")
FUNC_HDR = re.compile(r"^// ==== main\+([0-9A-F]{6})  ", re.M)
TIGHT, NEAR = 8, 64
PLANNED = ("patch", "patch-static")

# subsystem -> the group a player would name
GROUPS = [
    ("enemies", ("em", "cEnemy", "cEm", "cMonster")),
    ("player and weapons", ("pl", "plwp", "plwpsub", "wp")),
    ("animals", ("an", "cAnimal", "cDog", "cFish")),
    ("people", ("hm", "cHuman")),
    ("objects", ("ut", "et", "obj", "gt", "vt", "cItem", "cKiType", "cKihon", "cBall", "cCarry",
                 "cGear", "cDig", "cBamboo", "cObj", "cTubomi", "cKakejiku", "cSave", "cScr", "sg",
                 "db")),
    ("effects", ("es",)),
]


def group_of(subsystem):
    if subsystem == "library":
        return "library"
    if subsystem in ("effect",):
        return "effects"
    if subsystem.startswith("ui"):
        return "ui"
    if subsystem == "model-material":
        return "materials"
    if subsystem.startswith("object:"):
        fams = subsystem[7:].split("/")
        for name, prefixes in GROUPS:
            if any(f in prefixes for f in fams):
                return name
        return "objects"
    return "unattributed"


def function_starts(path):
    if not os.path.exists(path):
        sys.exit("no decompile at %s (tools/ghidra_export.py writes it)" % path)
    src = open(path, encoding="utf-8", errors="replace").read()
    return sorted(int(m.group(1), 16) for m in FUNC_HDR.finditer(src))


class Flow:
    """Instruction-level control flow inside one function, for `on_path`:
    fall-through, direct jumps and branches, and a `jmp reg` to the switch
    table its own `mov r, [base + idx*4 + table]` names (a table the parser
    cannot read leaves that jump without successors, so the candidates behind
    it read as off-path: flagged for reading, never hidden)."""

    def __init__(self, img, insns, starts):
        self.img, self.insns, self.starts = img, insns, starts
        self.index = {a: k for k, (a, _m, _o, _s) in enumerate(insns)}
        self.addrs = [a for a, *_ in insns]
        self.cache = {}

    def bounds(self, at):
        i = bisect.bisect_right(self.starts, at) - 1
        lo = self.starts[i] if i >= 0 else 0
        hi = self.starts[i + 1] if i + 1 < len(self.starts) else lo + 0x10000
        return lo, hi

    def succ(self, k, lo, hi):
        a, mn, op, size = self.insns[k]
        nxt = a + size
        if mn in ("ret", "int3", "ud2", "hlt"):
            return []
        if mn == "jmp":
            if op.startswith("0x"):
                return [int(op, 16) - cps.BASE_IMAGE]
            for j in range(k - 1, max(-1, k - 7), -1):
                g = cps.TBL.match(self.insns[j][2])
                if self.insns[j][1] == "mov" and g:
                    tbl, out = int(g.group(4), 16), []
                    for e in range(4096):
                        t = int.from_bytes(self.img[tbl + 4 * e:tbl + 4 * e + 4], "little")
                        if not lo <= t < hi:
                            break
                        out.append(t)
                    return out
            return []
        if mn.startswith("j") and op.startswith("0x"):
            return [nxt, int(op, 16) - cps.BASE_IMAGE]
        return [nxt]

    def forward(self, at):
        """every instruction start reachable from `at` inside its function"""
        if at in self.cache:
            return self.cache[at]
        lo, hi = self.bounds(at)
        seen, todo = set(), [at]
        while todo:
            x = todo.pop()
            if x in seen or not lo <= x < hi or x not in self.index:
                continue
            seen.add(x)
            todo.extend(self.succ(self.index[x], lo, hi))
        self.cache[at] = seen
        return seen

    def starts_in(self, a, b):
        """instruction starts in [a, b), or the one instruction containing a"""
        i = bisect.bisect_left(self.addrs, a)
        out = []
        while i < len(self.addrs) and self.addrs[i] < b:
            out.append(self.addrs[i])
            i += 1
        if not out and i > 0:
            out.append(self.addrs[i - 1])
        return out

    def on_path(self, a, b, load, store):
        """Some instruction of [a, b) lies on the update's path: after the
        store, reached from it; otherwise into the store, and from the load
        (or, in the bytes before it, into the load). A census load with no
        path to its store (one read of several, from another state) leaves
        only `into the store`."""
        lo, hi = min(load, store), max(load, store)
        from_load, from_store = self.forward(load), self.forward(store)
        load_ok = store in from_load
        for x in self.starts_in(a, b):
            if a > hi:
                if x in from_store:
                    return True
            elif store in self.forward(x) and (
                    not load_ok or x in from_load or (b <= lo and load in self.forward(x))):
                return True
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--decomp", default=DECOMP)
    ap.add_argument("--out", default=DOCS)
    args = ap.parse_args()

    starts = function_starts(args.decomp)

    def owner(rva):
        i = bisect.bisect_right(starts, rva) - 1
        return starts[i] if i >= 0 else None

    img, text_lo, text_hi = cps.load_image()
    with contextlib.redirect_stdout(io.StringIO()):
        sites, _detours, loads = cps.all_sites(img)
    flow = Flow(img, cps.disassemble(img, text_lo, text_hi), starts)
    ranges = sorted([(rva, rva + max(ln, 1), fam) for rva, (fam, ln, _raw) in sites.items()] +
                    # a hoisted decay patches the multiply; the load of k it is proven
                    # from sits by the update itself
                    [(rva, rva + len(raw), "hoisted_decay.h") for rva, raw in loads])
    by_fn = collections.defaultdict(list)
    for a, b, fam in ranges:
        by_fn[owner(a)].append((a, b, fam))

    cands = list(csv.DictReader(open(os.path.join(DOCS, "sites.csv"), encoding="utf-8")))
    cls = {r["site"]: r for r in csv.DictReader(open(os.path.join(DOCS, "classification.csv"),
                                                      encoding="utf-8"))}
    reads_path = os.path.join(DOCS, "reads.csv")
    reads = {r["site"]: r for r in csv.DictReader(open(reads_path, encoding="utf-8"))}         if os.path.exists(reads_path) else {}
    unknown = sorted(set(reads) - {c["site"] for c in cands})
    if unknown:
        sys.exit("reads.csv names %d sites that are not candidates: %s"
                 % (len(unknown), ", ".join(unknown[:8])))
    rows = []
    reviewed_event_restorations = set()
    for c in cands:
        site = int(c["site"], 16)
        load = int(c["load"], 16) if c["load"] else site
        lo, hi = min(site, load), max(site, load)
        fn = int(c["function"], 16) if c["function"] else owner(site)
        best, off = None, None
        for a, b, fam in by_fn.get(fn, ()):
            # distance from the update's instructions to the patched range
            d = 0 if (a <= hi and b > lo) else (lo - b if b <= lo else a - hi)
            if d > NEAR or (best is not None and d >= best[0]):
                continue
            if flow.on_path(a, b, load, site):
                best = (d, fam)
            elif d <= TIGHT and (off is None or d < off[0]):
                off = (d, "%s %X" % (fam, a))
        if best is not None and best[0] <= TIGHT:
            off = None
        k = cls.get(c["site"])
        decision = k["decision"] if k else ""
        if c["subsystem"] == "library":
            status = "library"
        elif best and best[0] <= TIGHT:
            status = "covered"
        elif decision == "exclude":
            status = "excluded"
        elif c["shape"] == "port:timescale":
            status = "port"
        elif c["site"] in reads and reads[c["site"]]["verdict"] != "left":
            status = "read"
        elif best and best[0] <= NEAR:
            status = "near"
        elif decision in PLANNED:
            status = "to-patch"
        elif decision == "review":
            status = "review"
        else:
            status = "unclassified"
        # Deliberately undoing a timer patch is also a reviewed resolution:
        # require both a stock verdict and the exact event-counter instruction
        # inside this candidate's original load .. store, not a nearby patch.
        if status == "read" and reads[c["site"]]["verdict"] == "stock" and \
                any(lo <= event <= hi for event in ec.NOT_PACED):
            reviewed_event_restorations.add(c["site"])
        rows.append({"site": c["site"], "function": "%X" % fn if fn is not None else "",
                     "subsystem": c["subsystem"], "group": group_of(c["subsystem"]),
                     "shape": c["shape"], "status": status,
                     "family": best[1] if best else "", "distance": best[0] if best else "",
                     "offpath": off[1] if off else "",
                     "decision": decision,
                     "reason": ("read: %s, %s" % (reads[c["site"]]["verdict"],
                                                  reads[c["site"]]["note"])
                                if status == "read" else
                                k.get("static_reason", "") if k else "")})

    # A historical patch may be replaced by a documented fix outside the
    # eight-byte coverage radius, such as a gate for the complete physics step,
    # or removed after review proves that the counter counts events, not ticks.
    old = [r for r, c in zip(rows, cands) if c["covered_by"] and r["status"] != "library"]
    # The 2026-09 rule also counted candidates covered through another branch's
    # patch (offpath): those are settled by their own status, not lost.
    lost = [r for r in old if r["status"] != "covered" and not
            (r["status"] == "read" and (reads[r["site"]]["verdict"] == "fixed" or
                                        r["site"] in reviewed_event_restorations)) and not
            (r["offpath"] and r["status"] in ("excluded", "read", "port"))]
    offpath = [r for r in rows if r["offpath"]]
    restored = sum(r["site"] in reviewed_event_restorations for r in old)

    statuses = ["covered", "excluded", "port", "library", "read", "near", "to-patch", "review",
                "unclassified"]
    total = collections.Counter(r["status"] for r in rows)
    groups = collections.defaultdict(collections.Counter)
    for r in rows:
        groups[r["group"]][r["status"]] += 1
    fams = collections.Counter(r["family"] for r in rows if r["status"] == "covered")
    reasons = collections.Counter(r["reason"] for r in rows if r["status"] == "excluded")
    verdicts = collections.Counter(reads[r["site"]]["verdict"] for r in rows
                                   if r["status"] == "read")

    n = len(rows)
    settled = total["covered"] + total["excluded"] + total["port"] + total["library"] +         total["read"]
    left = total["to-patch"] + total["review"] + total["unclassified"]
    lines = []
    say = lines.append
    say("# Coverage: the candidates against the patch")
    say("")
    say("Written by `tools/coverage_report.py` on %s from `sites.csv` (%d candidates), "
        "`classification.csv` and the tables in `src/` (%d patched ranges)."
        % (datetime.date.today().isoformat(), n, len(ranges)))
    say("")
    say("**Settled: %d of %d (%.0f%%)**: covered %d, excluded %d (library %d, classified %d, "
        "port-scaled %d), read by hand %d. **Near a patch, unproven: %d.** **Left: %d** "
        "(classified to patch %d, to review %d, never classified %d)."
        % (settled, n, 100.0 * settled / n, total["covered"],
           total["library"] + total["excluded"] + total["port"], total["library"],
           total["excluded"], total["port"], total["read"], total["near"], left,
           total["to-patch"], total["review"], total["unclassified"]))
    say("")
    say("Without the library: settled %d of %d (%.0f%%), %.0f%% with the near ones."
        % (settled - total["library"], n - total["library"],
           100.0 * (settled - total["library"]) / (n - total["library"]),
           100.0 * (settled - total["library"] + total["near"]) / (n - total["library"])))
    say("")
    say("| group | " + " | ".join(statuses) + " | total |")
    say("|---|" + "---|" * (len(statuses) + 1))
    for g in sorted(groups, key=lambda g: -sum(groups[g].values())):
        cnt = groups[g]
        say("| %s | " % g + " | ".join(str(cnt[s]) if cnt[s] else "--" for s in statuses)
            + " | %d |" % sum(cnt.values()))
    say("| **all** | " + " | ".join(str(total[s]) for s in statuses) + " | %d |" % n)
    say("")
    say("Covered, by family: " + ", ".join("%s %d" % (f, c) for f, c in fams.most_common()) + ".")
    say("")
    say("Excluded, the classification's reasons (top 8): " +
        "; ".join("%s (%d)" % (r or "none given", c) for r, c in reasons.most_common(8)) + ".")
    say("")
    if verdicts:
        say("Read by hand (`reads.csv`), by verdict: " +
            ", ".join("%s %d" % v for v in verdicts.most_common()) + ".")
        say("")
    say("Check: of the %d candidates `animation_inventory.py` found covered in 2026-09, %d "
        "remain covered, have documented replacement fixes or have reviewed event counters "
        "restored to stock behavior%s." % (len(old), len(old) - len(lost),
                                      "" if not lost else " (%d NOT: %s)" % (
                                          len(lost), ", ".join(r["site"] for r in lost[:8]))))
    say("")
    if offpath:
        say("Off the patched path: %d candidates have a patch within 8 bytes only on another "
            "branch (column `offpath`), so they are not counted covered: %s." % (
                len(offpath), ", ".join("%s %d" % kv for kv in
                                        collections.Counter(r["status"] for r in offpath)
                                        .most_common())))
        say("")
    if restored:
        say("The %d event-counter restorations require both a `stock` verdict in `reads.csv` "
            "and a matching `event_counters.NOT_PACED` instruction within the original "
            "candidate's load .. store." % restored)
        say("")
    say("The classification is from 2026-09-18: `review` and `to-patch` shrink only as "
        "candidates are read or patched, and a candidate the patch covers some other way "
        "(a hook, a skipped call, a retargeted table the rule does not see) still counts "
        "as left.")

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "coverage.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    open(os.path.join(args.out, "coverage.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 1 if lost else 0


if __name__ == "__main__":
    sys.exit(main())
