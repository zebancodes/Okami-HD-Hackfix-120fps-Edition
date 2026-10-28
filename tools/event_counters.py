#!/usr/bin/env python3
"""Integer counters that count events, not ticks.

The three timer finders (find_memory_timers.py, find_action_timers.py,
find_lea_timers.py) take every inc/dec of the character duration fields
(+E3C, +E3E, +E40, +E42, +E76) for a per-tick countdown and run it on stock
ticks only. Some of those counters change once per *event* instead:

  * once per loop of a motion: the motion advance (4B9C80, 4B9B70) and 239420
    answer "ended" on the tick a looping motion wraps, and the counter says how
    many more loops to play (an idle repeated rand & 3 times, a dig cycle five
    times). Paced, a wrap on one of the N - 1 ticks between stock ticks is not
    counted, so the loop plays about N times as often;
  * once per button press (B6B0D0, B6AD20: pressed this tick, cPad::Key_set):
    pressed between stock ticks, the press is lost;
  * one point per tick of recorded data: the brush stroke records a point every
    tick the cursor moves (16C7E0 -> 803650 -> 889750), and the characters that
    fly along it (pl02 Issun with the Thief's Glove, pl03, pl04) take one point a
    tick. Paced, they need N ticks a point, N times the time it took to draw.

An event test is `call E; test al, al; jcc` with E one of the above, and a
counter is event-gated when the event edge of such a test dominates it in the
function's control-flow graph (jump-table cases are roots; see event_gated()),
or when its function only runs behind one: called directly, address never
taken, and every call behind an event edge, up to CALLERS calls up. The dig's
hole grows in 459D90, which pl00's press handler 3C18B0 calls once per press;
the one-function test missed its two count rows until 1.0.3.

A motion that does not loop answers "ended" on every tick once it has played,
so a counter behind it can also be a per-tick wait after a one-shot motion.
Each event-gated site was read: where the counter's reload is small (rand & 3,
1..6), it is a loop count and is left out of the timer tables (NOT_PACED);
where it is large or computed it stays paced (STILL_PACED).

    .venv/Scripts/python tools/event_counters.py      # list the event-gated sites
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# --- left out of the timer tables: they run at any rate as stock runs them ---
LOOP = "counts loops of a motion (one decrement on each tick it wraps)"
NOT_PACED = {
    # em85: once per selected attack attempt, behind the update's chance trials.
    0x5CD6DE: "em85 helper 5CD690, sole caller 5C67DC behind the 0.1 trial at "
              "5C67D2: +3490 counts attempts; the fourth sets +348C=100 and "
              "clears +3490. Pace the selection branch, preserve each attempt",
    0x5CD7AE: "em85 helper 5CD760, sole caller 5C67F5 behind the 0.1 trial at "
              "5C67EB: the same shared four-attempt cooldown count",
    # memory_timers.h: once per press
    0x3C19EE: "pl00 sub-state 0x29 (3C13F0/3C18B0, the dig; entered from 3B2620 and the "
              "dirt-spawning 3CF730/3CF980): +E40 counts presses of the dig button "
              "(B6B0D0, pressed this tick), one paw stroke each; more than 5 finish it",
    # memory_timers.h: once per loop
    0x1F9B04: LOOP + ": +E3C = (rand & 3) + 2 loops",
    0x2A3CA8: LOOP + ": +E3C = 1 or 2 loops (239420)",
    0x2BA63C: LOOP + ": em61 +E3E = 2 loops (239420)",
    # memory_timers.h: one point a tick of the brush stroke
    0x3A3DD0: "pl02 (3A3CA0, sub-state 1: Issun's flight with the Thief's Glove): +E3C "
              "indexes the brush stroke copied by 169A40, one point per tick drawn",
    0x3A5326: "pl03 (3A51F0, sub-state 1): +E3C indexes the brush stroke copied by "
              "169A40, one point per tick drawn",
    # world_anims.h (rows removed 2026-10-03): the same kinds
    0x3A62A9: "pl04 (3A619F): +414C[part] indexes the brush stroke 169A40 copied for "
              "that part (3A60BE), one point per tick drawn",
    0x2755EF: LOOP + ": em2b +1394 = 3 or 6 loops (239420)",
    0x3BC4C4: "the zero test of 3BC4BA's loop count (a notyet held it for stock ticks)",
    0x384CFC: "wp04 (384BE0): the zero test of +E37's loop count (3 or 0)",
    0x384D06: LOOP + ": wp04 +E37 = 3 or 0",
    0x3A8378: "pl00 (3A80F0): -5 off the hold +115A for each button pressed this tick "
              "(B6B0D0) or B6B13C",
    0x3D13F4: "pl00 (3D1330): -2 off +E3C for each button pressed this tick (B6B0D0) "
              "or B6B13C",
    # world_anims.h (rows removed 2026-10-28): the dig's hole, once per press
    0x459DA1: "459D90, called only by pl00's dig press handler 3C18B0 (3C19BC, behind "
              "the dig button's press B6B0D0): the hole et68's +E3E gains 2 or 6 a "
              "press; its size is +E3E x 0.02 and it is dug at 0.9",
    0x459DBE: "459D90, the same press: the hole's +E3C (its time left, counted down a "
              "stock tick at a time by lea_timers 2F2389/2F2423) gains 40 or 120, "
              "capped at 900",
    # action_timers.h (2026-10-09): once per volley
    0x2770E3: "em2b 276DE0 state 3: +E3E indexes the volley pattern, stepped once per "
              "projectile 0x607 (when the paced +E3C countdown reaches 0, a row at "
              "2770FB); paced, the volley lands between stock ticks and the index stalls",
    0x4004F1: "cCockLoading (4003D0): +39C counts the loading mini-game's well-timed "
              "presses (B6AD20); integer_skips refuses it for that reason",
    # action_timers.h: once per loop, +E3C = rand & 3 (or + 1, + 2) at the motion's start
    0x1D653D: LOOP, 0x1D6C75: LOOP, 0x1D98BD: LOOP, 0x1DA117: LOOP, 0x1DC244: LOOP,
    0x1DDAED: LOOP, 0x1DDC91: LOOP, 0x1DE2D0: LOOP, 0x1DE3D2: LOOP, 0x1E12FD: LOOP,
    0x1E1A67: LOOP, 0x1E464D: LOOP, 0x1E7A02: LOOP, 0x1E7F28: LOOP, 0x1EFC9B: LOOP,
    0x1F1A33: LOOP, 0x1F5880: LOOP, 0x1F7AE3: LOOP, 0x1F822D: LOOP + " (rand & 1)",
    0x1FB539: LOOP + " ((rand & 1) + 5)", 0x1FBADA: LOOP,
    0x1FEE07: LOOP + " ((rand & 3) + 2)", 0x1FEFEE: LOOP + " ((rand & 3) + 2)",
    0x200C4B: LOOP,
    # lea_timers.h: once per loop
    0x218C32: LOOP + ": 3..5 loops",
    0x3BC4BA: LOOP + ": pl00 sub-state 0x11 (3BC300): motion 0x16 five times "
              "(+E3C = 4), between an opening and a closing motion",
    0x3C5B09: LOOP + ": +E3C = 1",
    0x3C64DE: LOOP + ": +E3C = 2",
    0x57F856: LOOP + ": +E3C = (rand & 3) + 1",
}

# --- event-gated but left paced: the reload is large or computed, so it may be a
# per-tick wait after a one-shot motion; a loop count this large is unlikely ---
STILL_PACED = {
    0x1F13AC: "+E3C = (rand & 15) + 5 or rand & 1",
    # (1FCD13 and 1FCD35, an1e 1FCC10, were listed here until 1.0.3: the advance's
    # jne 1FCCD5 only skips a turn and rejoins at 1FCCEE, which the strict edge
    # test no longer takes for the motion's end)
    0x1FD152: "+E3C = a float's integer part, or rand & 1",
    0x4AAB40: "+E3C = rand % param + param (4AAA70's caller decides)",
    0x3CA79F: "+E3C = 1 or 10 (pl00 sub-state 0x56)",
    0x56258E: "+E3C = 15 or rand + 30",
}

BASE = 0x180000000
CALLERS = 2   # calls up the surveys follow from a counter to its event test
EVENT_CALLS ={0x4B9C80: "motion ended", 0x4B9B70: "motion ended", 0x239420: "anim ended"}
PRESS_ARRAYS = {0xB6B0D0, 0xB6B0D8, 0xB6AD20, 0xB6AD28}   # pressed this tick
COND = {"je", "jne", "jg", "jge", "jl", "jle", "ja", "jae", "jb", "jbe", "js", "jns",
        "jp", "jnp", "jo", "jno"}
RIP = re.compile(r"\[rip ([+-]) 0x([0-9a-f]+)\]")


class Image:
    def __init__(self):
        import xrefs
        pe, base, img, text = xrefs.load_bin("main.dll")
        self.pe, self.img, self.text = pe, img, text
        self.insns = [(a - BASE, m, o, s) for a, m, o, s in xrefs.cached_insns("main.dll")]
        self.idx = {a: k for k, a in enumerate(i[0] for i in self.insns)}
        self.imps = {a - BASE: n for a, n in xrefs.import_names(pe).items()}
        self._calls = None

    def calls(self):
        """({target: [site, ...]} for every direct call and jump, {rva, ...} of the
        code addresses taken: loaded by another instruction (a callback) or held by
        a pointer in data (a base relocation: vtables, handler tables). A function
        whose address is taken can be called from anywhere."""
        if self._calls is None:
            lo, hi = self.text[0], self.text[0] + self.text[1]
            tgt, taken = collections.defaultdict(list), set()
            for a, m, o, s in self.insns:
                if m == "call" or m == "jmp" or m in COND:
                    t = self.target(o)
                    if t is not None:
                        tgt[t].append(a)
                        continue
                r = self.rip(a, o, s)
                if r is not None and lo <= r < hi:
                    taken.add(r)
            for blk in getattr(self.pe, "DIRECTORY_ENTRY_BASERELOC", ()):
                for e in blk.entries:
                    if e.type == 10:  # IMAGE_REL_BASED_DIR64
                        v = int.from_bytes(self.img[e.rva:e.rva + 8], "little") - BASE
                        if lo <= v < hi:
                            taken.add(v)
            self._calls = (tgt, taken)
        return self._calls

    def target(self, op):
        try:
            return int(op, 16) - BASE
        except ValueError:
            return None

    def rip(self, a, op, sz):
        mo = RIP.search(op)
        if not mo:
            return None
        d = int(mo.group(2), 16)
        return a + sz + d if mo.group(1) == "+" else a + sz - d


def _function(im, rva):
    """The function's instructions: back to the int3 padding before it, forward to
    the padding after it (jump-table cases included)."""
    k = im.idx.get(rva)
    if k is None:
        return None
    lo = k
    while lo > 0 and im.insns[lo - 1][1] != "int3":
        lo -= 1
    hi = k
    while hi < len(im.insns) and im.insns[hi][1] != "int3":
        hi += 1
    return im.insns[lo:hi]


def _graph(im, body):
    seen = {a for a, *_ in body}
    starts = {body[0][0]}
    for a, mn, op, sz in body:
        if mn in COND or mn in ("jmp", "ret"):
            t = im.target(op) if mn != "ret" else None
            if t in seen:
                starts.add(t)
            if a + sz in seen:
                starts.add(a + sz)
    blk, cur = {}, None
    for a, *_ in body:
        if a in starts or cur is None:
            cur = a
        blk[a] = cur
    succ = collections.defaultdict(list)
    for a, mn, op, sz in body:
        b, nxt = blk[a], a + sz
        if mn in ("ret", "int3"):
            continue
        t = im.target(op) if (mn in COND or mn == "jmp") else None
        if t in seen:
            succ[b].append(blk[t])
        if mn == "jmp":
            continue
        if nxt in seen and (mn in COND or blk[nxt] != b):
            succ[b].append(blk[nxt])
    nodes = sorted(set(blk.values()))
    has_pred = {s for ss in succ.values() for s in ss}
    succ[-1] = [n for n in nodes if n not in has_pred]      # the entry and the cases
    nodes = [-1] + nodes
    pred = collections.defaultdict(list)
    for b, ss in succ.items():
        for s in ss:
            pred[s].append(b)
    dom = {n: set(nodes) for n in nodes}
    dom[-1] = {-1}
    changed = True
    while changed:
        changed = False
        for n in nodes[1:]:
            ps = [dom[p] for p in pred[n]]
            new = (set.intersection(*ps) if ps else set()) | {n}
            if new != dom[n]:
                dom[n], changed = new, True
    return blk, dom, pred


def _event_edges(im, body, blk, pred=None):
    """[(edge block, why, test rva)]. With pred, only an edge whose block the test
    alone enters: a join that the other path reaches as well (the motion advance's
    `jnz` past a call the not-ended path makes, 39CF56) runs on both."""
    out = []
    for k, (a, mn, op, sz) in enumerate(body):
        if mn != "call" or k + 2 >= len(body):
            continue
        why, negate = None, False
        t = im.target(op)
        if t in EVENT_CALLS:
            why = EVENT_CALLS[t]
        else:
            name = im.imps.get(im.rip(a, op, sz), "")
            if "LargeBitValue" in name and ("??B" in name or "??7" in name):
                for b, m2, o2, s2 in body[max(0, k - 14):k]:
                    if im.rip(b, o2, s2) in PRESS_ARRAYS:
                        why, negate = "pressed", "??7" in name
                        break
        if not why:
            continue
        (_a1, m1, o1, _s1), (a2, m2, o2, s2) = body[k + 1], body[k + 2]
        if m1 != "test" or o1 != "al, al" or m2 not in ("je", "jne"):
            continue
        taken, fall = blk.get(im.target(o2)), blk.get(a2 + s2)
        edge = fall if (m2 == "je") != negate else taken
        if edge is not None and pred is not None and pred[edge] != [blk[a2]]:
            continue
        if edge is not None:
            out.append((edge, why, a))
    return out


def _gated(im, rva, cache, callers, strict):
    body = _function(im, rva)
    if not body:
        return None
    key = body[0][0]
    if key not in cache:
        blk, dom, pred = _graph(im, body)
        cache[key] = (blk, dom, _event_edges(im, body, blk, pred if strict else None), body)
    blk, dom, edges, body = cache[key]
    b = blk.get(rva)
    if b is None:
        return None
    for edge, why, test in edges:
        if edge in dom.get(b, ()):
            return why, test
    if callers <= 0:
        return None
    # One call up: the body's entries (its start, and any other instruction a call
    # or jump from outside lands on) must all be called directly, and every one of
    # those calls must itself be behind an event edge.
    tgt, taken = im.calls()
    lo, hi = body[0][0], body[-1][0]
    first = None
    for a, *_ in body:
        sites = [s for s in tgt.get(a, ()) if not lo <= s <= hi]
        if a != lo and not sites:
            continue
        if a in taken or not sites:
            return None
        for s in sites:
            up = _gated(im, s, cache, callers - 1, strict)
            if up is None:
                return None
            first = first or ("%s, caller %06X" % (up[0], s), up[1])
    return first


def event_gated(rvas, im=None, callers=0, strict=False):
    """{rva: (why, test rva)} for the sites an event edge dominates. With callers=n,
    also those in a function that only runs behind one up to n calls up: every
    direct call of it is behind an event edge in its caller, and its address is
    never taken (a press handler's helper, 459D90). With strict, an edge counts
    only when its block has the test as its only predecessor (see _event_edges);
    early_countdowns keeps the old test."""
    im = im or Image()
    cache, out = {}, {}
    for rva in rvas:
        g = _gated(im, rva, cache, callers, strict)
        if g:
            out[rva] = g
    return out


def timer_sites():
    """{rva: source} for every site the three timer tables and the world table's
    integer rows pace."""
    root = os.path.normpath(os.path.join(HERE, ".."))
    out = {}
    pats = (("memory_timers.h", r"\s*\{0x([0-9A-F]+), \d, \{"),
            ("action_timers.h", r"\s*\{0x([0-9A-F]+), +\d+, \{"),
            ("lea_timers.h", r"\s*\{0x([0-9A-F]+), +\d+, +\d+, +\d+, \{"))
    for name, pat in pats:
        for line in open(os.path.join(root, "src", name)):
            m = re.match(pat, line)
            if m:
                out[int(m.group(1), 16)] = name
    import csv
    for r in csv.DictReader(open(os.path.join(root, "docs", "animation", "world_anims.csv"))):
        if r["status"] == "selected" and r["kind"] in (
                "count", "count2", "countlast", "notyet", "notyetneg", "notyetb", "notyett"):
            out[int(r["site"], 16)] = "world_anims.h " + r["kind"]
    return out


if __name__ == "__main__":
    sites = timer_sites()
    for rva, (why, test) in sorted(event_gated(sites, callers=CALLERS, strict=True).items()):
        tag = "STILL_PACED" if rva in STILL_PACED else "NOT_PACED?" if rva in NOT_PACED else "OPEN"
        print("%06X %-22s %-12s test %06X  %s" % (rva, sites[rva], why, test, tag))
