#!/usr/bin/env python3
"""Fail when a counter that counts events is paced to stock ticks.

The timer tables (memory_timers.h, action_timers.h, lea_timers.h) and the world
table's integer rows (count, count2, countlast, notyet*) run a counter on
stock ticks only. A counter that changes once per loop of a motion or once per
button press loses the events that land between stock ticks, so the loop plays
about N times as often, or the press is lost (tools/event_counters.py).

Problems:
  * a paced site that an event edge dominates, in its own function or up to
    event_counters.CALLERS calls up (the dig's hole, 459D90, grows only from
    the press handler's call), and that is not reviewed in
    event_counters.STILL_PACED;
  * a site event_counters.NOT_PACED lists that a table still paces.

    .venv/Scripts/python tools/survey_event_counters.py
"""
import sys

import event_counters as ec


def main():
    sites = ec.timer_sites()
    gated = ec.event_gated(sites, callers=ec.CALLERS, strict=True)
    problems = []
    for rva, (why, test) in sorted(gated.items()):
        if rva not in ec.STILL_PACED:
            problems.append("%06X (%s) is paced but counts events: %s at %06X"
                            % (rva, sites[rva], why, test))
    for rva in sorted(ec.NOT_PACED):
        if rva in sites:
            problems.append("%06X (%s) is paced but event_counters.NOT_PACED lists it: %s"
                            % (rva, sites[rva], ec.NOT_PACED[rva]))
    stale = [rva for rva in ec.STILL_PACED if rva not in gated]
    print("%d paced integer sites, %d behind an event edge (%d reviewed and left paced)"
          % (len(sites), len(gated), sum(1 for r in gated if r in ec.STILL_PACED)))
    print("%d left out as event counters (event_counters.NOT_PACED)" % len(ec.NOT_PACED))
    for rva in stale:
        print("note: STILL_PACED %06X is no longer behind an event edge" % rva)
    for p in problems:
        print("PROBLEM " + p)
    print("%d problem(s)" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
