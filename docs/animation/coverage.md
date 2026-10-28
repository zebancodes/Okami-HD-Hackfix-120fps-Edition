# Coverage: the candidates against the patch

Written by `tools/coverage_report.py` on 2026-10-28 from `sites.csv` (12485 candidates), `classification.csv` and the tables in `src/` (6927 patched ranges).

**Settled: 12485 of 12485 (100%)**: covered 4325, excluded 3881 (library 1626, classified 2227, port-scaled 28), read by hand 4279. **Near a patch, unproven: 0.** **Left: 0** (classified to patch 0, to review 0, never classified 0).

Without the library: settled 10859 of 10859 (100%), 100% with the near ones.

| group | covered | excluded | port | library | read | near | to-patch | review | unclassified | total |
|---|---|---|---|---|---|---|---|---|---|---|
| unattributed | 700 | 603 | 12 | -- | 1867 | -- | -- | -- | -- | 3182 |
| enemies | 695 | 518 | -- | -- | 460 | -- | -- | -- | -- | 1673 |
| objects | 1016 | 112 | 1 | -- | 524 | -- | -- | -- | -- | 1653 |
| library | -- | -- | -- | 1626 | -- | -- | -- | -- | -- | 1626 |
| animals | 497 | 622 | 2 | -- | 340 | -- | -- | -- | -- | 1461 |
| player and weapons | 741 | 128 | 13 | -- | 516 | -- | -- | -- | -- | 1398 |
| ui | 189 | 162 | -- | -- | 194 | -- | -- | -- | -- | 545 |
| materials | 285 | -- | -- | -- | 188 | -- | -- | -- | -- | 473 |
| people | 79 | 63 | -- | -- | 112 | -- | -- | -- | -- | 254 |
| effects | 123 | 19 | -- | -- | 78 | -- | -- | -- | -- | 220 |
| **all** | 4325 | 2227 | 28 | 1626 | 4279 | 0 | 0 | 0 | 0 | 12485 |

Covered, by family: world_anims.h 1964, world_anims.h literal 572, memory_timers.h 540, phase_steps.h 401, action_timers.h 244, world_anims.h call 207, decay_factors.h 168, lea_timers.h 108, integer_skips.h 40, turn_callers.h 38, hoisted_decay.h 9, kAirAccelSites 6, task_waits.h 6, kSwimAccelSites 5, menu_transitions.h 5, menu_transitions.h literal 4, kStickDriftSites 3, kAirGateSites 2, mode_constants.h 1, kRunPatchRva 1, frame_clocks.h tick 1.

Excluded, the classification's reasons (top 8): switch (1041); compared with 4 small values (#0,#1,#2,#3) (432); compared with 3 small values (#0,#1,#2) (138); compared with 5 small values (#0,#1,#2,#3,#4) (90); array index (83); reads feed only arithmetic/calls (76); float stepped with no bound seen (48); dereferenced (39).

Read by hand (`reads.csv`), by verdict: once 1496, stock 1279, fixed 903, follows 601.

Check: of the 1478 candidates `animation_inventory.py` found covered in 2026-09, 1478 remain covered, have documented replacement fixes or have reviewed event counters restored to stock behavior.

Off the patched path: 15 candidates have a patch within 8 bytes only on another branch (column `offpath`), so they are not counted covered: excluded 8, read 6, port 1.

The 36 event-counter restorations require both a `stock` verdict in `reads.csv` and a matching `event_counters.NOT_PACED` instruction within the original candidate's load .. store.

The classification is from 2026-09-18: `review` and `to-patch` shrink only as candidates are read or patched, and a candidate the patch covers some other way (a hook, a skipped call, a retargeted table the rule does not see) still counts as left.
