# 2026-10-10: the villager sub-object's pushes (4ABE10 from 30D250, 4AB570).
# Each copies its push +E10 into the root motion +EC0 every tick, which
# 20E960 moves the villager by once its +11E8 bit 14 hands it the
# sub-object's motion (3046D0). The motion advance writes +EC0 at the current
# rate's share; these pushes wrote stock units, so the villager went N times
# as far a tick. +E10 becomes this tick's share (lin on its start), and its
# changes land once a stock period, in stock's order around the copy.
group human
lin 4ABECB | villager sub-object 4ABE10 (from 30D250), the hop: +E10 = (0, 0, -1) at each reload, copied to the root motion +EC0 every tick: -s, this tick's share
count 4ABF08 | 4ABE10: +E18 += 0.1 (phase_steps' 0.1 x s) before the copy, stored on the first tick of each stock period: the push changes by 0.1 x s once a period, before that period's copies, as stock's changes once a tick before its copy
count 4ABF12 | 4ABE10: the push's clamp at 0 (+E18 = 0 once +E18 + 0.1 x s passes 0), on the first tick of each stock period with the store above: tested on the other ticks against the same +E18, it ended each ramp a stock tick early
countlast 4ABF27 | 4ABE10: +E3C, where the reload (10..25) and the countdown meet, stored on the last tick of each stock period: the reload test sees 0 for one whole period, as stock's does for one tick, and the hop recurs every R + 1 stock ticks
lin 4AB63B | villager sub-object 4AB570: +E10 = (0, 0, -4) as the state starts, copied to the root motion +EC0 every tick for 15 ticks: -4 x s, this tick's share
ulast 4AB67E scale:4AB694 | 4AB570: +E10 *= 0.8 (ScaleXYZ) after the tick's copy: on the last tick of each stock period, after that tick's copy, as stock's order puts it
