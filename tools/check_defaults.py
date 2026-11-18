#!/usr/bin/env python3
"""Check that every fix family is on for players.

The release's okami_hackfix.ini has no Fix... lines, so a player gets the
defaults in src/dinput8_proxy.cpp: the Config member's initializer (no ini
at all) and loadConfig's GetPrivateProfileIntA default (an ini without the
line). 1.0.0 to 1.0.3 shipped FixIntegerSkips off in both. Its 39 counters
include the battle clock, which nothing else paces, so at 120 a battle's time
counted four times as fast and the results' time grade and yen bonus came
out low. The family had been built and measured in play, and
coverage_report.py counted its sites as covered, but no player had it.

For every `bool fix...` member of Config:
  * the initializer is true and loadConfig reads it with default 1, unless
    it is in OFF;
  * applyReleaseDefaults does not set it;
  * release/okami_hackfix.ini does not set it to 0.
A flag in OFF must be off in both places and must not name a family that
coverage.csv credits.

    .venv/Scripts/python tools/check_defaults.py [--break integers]

`--break integers` checks a copy of the source with FixIntegerSkips back at
its 1.0.3 defaults, and must fail.
"""
import argparse
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SRC = os.path.join(ROOT, "src", "dinput8_proxy.cpp")
RELEASE_INI = os.path.join(ROOT, "release", "okami_hackfix.ini")
COVERAGE = os.path.join(ROOT, "docs", "animation", "coverage.csv")

# Off by default on purpose: the half-rate slot gates, an early experiment
# that the patch tables replaced. No coverage figure counts them.
OFF = {
    "fixMenus": "half-rate sub-screen slot gate (experiment)",
    "fixHud": "half-rate HUD slot gate (experiment)",
    "fixEffects": "half-rate effect slot gate (experiment)",
}

# The families coverage.csv credits, and the Config flag each one installs
# under; a credited family must map to a flag this check holds on.
FAMILY_FLAG = {
    "world_anims.h": "fixWorldAnims",
    "memory_timers.h": "fixActionTimers",
    "action_timers.h": "fixActionTimers",
    "lea_timers.h": "fixActionTimers",
    "phase_steps.h": "fixPhaseSteps",
    "decay_factors.h": "fixDecay",
    "hoisted_decay.h": "fixHoistDecay",
    "task_waits.h": "fixTaskWaits",
    "integer_skips.h": "fixIntegerSkips",
    "turn_callers.h": "fixTurnRate",
    "menu_transitions.h": "fixMenuTransitions",
    "launch_velocities.h": "fixLaunchVelocity",
    "frame_clocks.h": "fixFrameClocks",
    "mode_constants.h": "fixModeConstants",
    "kAirAccelSites": "fixAirAccel",
    "kSwimAccelSites": "fixAirAccel",
    "kAirGateSites": "fixAirGates",
    "kRunPatchRva": "fixRunSpeed",
    "kStickDriftSites": "fixStickDrift",
}


def body(src, header):
    """The braced block that follows `header` (a regex), without nesting."""
    m = re.search(header, src)
    if not m:
        sys.exit("not found in dinput8_proxy.cpp: %s" % header)
    start = src.index("{", m.end() - 1)
    depth = 0
    for i in range(start, len(src)):
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        if depth == 0:
            return src[start:i + 1]
    sys.exit("unbalanced block after %s" % header)


def check(src, ini, credited):
    problems = []
    config = body(src, r"struct Config\s*\{")
    members = dict(re.findall(r"\bbool\s+(fix\w+)\s*=\s*(true|false)\s*;", config))
    reads = {}
    for flag, key, dflt in re.findall(
            r"g_cfg\.(fix\w+)\s*=\s*GetPrivateProfileIntA\(\s*sec\s*,\s*\"(\w+)\"\s*,\s*([^,]+?)\s*,\s*ini\s*\)",
            body(src, r"static void loadConfig\(\)\s*\{")):
        reads[flag] = (key, dflt)
    release = body(src, r"static void applyReleaseDefaults\(\)\s*\{")
    # [ \t], not \s: an empty value (ProxyDll=) must not run on into the next line
    ini_lines = {k.lower(): v.strip() for k, v in
                 re.findall(r"^[ \t]*(\w+)[ \t]*=[ \t]*([^;\r\n]*)", ini, re.M)}
    if not members:
        problems.append("no `bool fix...` members found in Config")
    for flag in sorted(members):
        init = members[flag]
        key, dflt = reads.get(flag, (None, None))
        want_on = flag not in OFF
        if key is None:
            problems.append("%s: loadConfig does not read it" % flag)
        elif dflt not in ("0", "1"):
            problems.append("%s: loadConfig default is `%s`, not a constant" % (flag, dflt))
        if want_on:
            if init != "true":
                problems.append("%s: Config default is %s, a player without an ini gets it off"
                                % (flag, init))
            if dflt == "0":
                problems.append("%s: loadConfig reads %s with default 0, a player whose ini "
                                "lacks the line gets it off" % (flag, key))
        else:
            if init != "false" or dflt != "0":
                problems.append("%s: listed in OFF (%s) but defaults on" % (flag, OFF[flag]))
        if re.search(r"g_cfg\.%s\s*=" % flag, release):
            problems.append("%s: applyReleaseDefaults sets it" % flag)
        if key and ini_lines.get(key.lower()) == "0":
            problems.append("%s: release/okami_hackfix.ini sets %s=0" % (flag, key))
    for fam, flag in sorted(FAMILY_FLAG.items()):
        if flag not in members:
            problems.append("%s: its flag %s is not a Config member" % (fam, flag))
    for fam in sorted(credited):
        flag = FAMILY_FLAG.get(fam)
        if flag is None:
            problems.append("coverage.csv credits %s, which FAMILY_FLAG does not map to a flag"
                            % fam)
        elif flag in OFF:
            problems.append("coverage.csv credits %s, but its flag %s is off by default"
                            % (fam, flag))
    return members, problems


def credited_families():
    fams = set()
    with open(COVERAGE, newline="") as f:
        for row in csv.DictReader(f):
            if row["status"] == "covered" and row["family"]:
                fams.add(row["family"].split()[0])  # "world_anims.h literal" -> the header
    return fams


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", dest="brk", choices=["integers"], default=None)
    args = ap.parse_args()
    src = open(SRC, encoding="utf-8").read()
    ini = open(RELEASE_INI, encoding="utf-8").read()
    if args.brk == "integers":
        src, n1 = re.subn(r"bool fixIntegerSkips = true;", "bool fixIntegerSkips = false;", src)
        src, n2 = re.subn(r"(\"FixIntegerSkips\",\s*)1(\s*,)", r"\g<1>0\2", src)
        if n1 != 1 or n2 != 1:
            sys.exit("--break integers: the two FixIntegerSkips defaults were not found")
    credited = credited_families()
    members, problems = check(src, ini, credited)
    on = sum(1 for f in members if f not in OFF)
    print("%d fix flags in Config: %d on by default, %d off by design (%s); "
          "%d families credited by coverage.csv, each mapped to a flag that is on"
          % (len(members), on, len(members) - on, ", ".join(sorted(OFF)), len(credited)))
    for p in problems:
        print("  PROBLEM " + p)
    print("%s: %d problem(s)%s" % ("FAIL" if problems else "OK", len(problems),
                                   " (--break %s)" % args.brk if args.brk else ""))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
