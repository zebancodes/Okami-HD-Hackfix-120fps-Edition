# 2026-10-10: trace_steps.py --check over the port's sites: four falls whose
# gravity carries the port's time scale (so +E54 stays in stock units) while
# the position takes the whole velocity every tick.
group actor
pre 484E62 | cDogLikeHm 484D40: +E54 -= ts x 0.3, then y += +E54 a tick; the same fall in 484A20 has pre 484BD6
pre 599608 | et99 599590: +E54 -= ts x 0.3, then y += +E54 a tick, unscaled
pre 5A469B | utc9 5A4650: +E54 -= ts x 0.3, then y += +E54 a tick, unscaled
pre 5A65EC | utcf 5A64F0: +E54 -= ts x 0.3, then y += +E54 a tick, unscaled
