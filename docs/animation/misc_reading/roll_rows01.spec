# 2026-10-10: rows from reading random_rolls.csv's pending draws (tools/roll_reads.py).
# Countdowns whose store has a count row but whose zero test (the reload of a random target
# and wait) had no gate: on the held ticks after the count stored 0 the reload drew up to 3/4 of
# a stock tick early. As 2030D7/203196 did for 2030B0/203160, the test reads "not yet" between
# stock ticks, so the draws and the reload come on the stock tick.
group actor
notyet 203248 notyet:2032B7 | an0c 203230 (from 1EEF50): the +1170 wander countdown's store has a count row (203242) but its zero test reads the old value (edx): between stock ticks the test reads "not yet", so the new target and wait are drawn on the stock tick, as stock's
notyet 1DC570 notyet:1DC5E5 | an03 1DC560 (from 1DC600/1DC780): +E3C's zero test (the reload of the random target +E10..+E18 and the wait 90..345) beside the count on its decrement (1DC5E8): between stock ticks it reads "not zero", so the reload comes on the stock tick, as stock's
notyet 205C24 notyet:205C73 | 205AE0 (every animal's update via 204D70/205A60): the random head-look timer +1175's zero test beside the count on its decrement (205C75): between stock ticks it reads "not zero", so the next look (yaw/pitch within 40 degrees) and the reload (+1176 + rand % +1177) come on the stock tick, as stock's
notyetb 2C6A5B notyet:2C6FBC | em65 2C66F0 (an action, from slot 16's 2C2F30): in its motion's last 15 frames (and on the tick it ends) it draws once a tick: 97% requests 0xA01, else 1% each 2CA3D0, 0x1501, 0x1401; for type 0x266, type 0x211 with +1730 set or off-screen the 97% side does nothing, so it draws again every tick: 15 draws a loop at 30, 60 at 120. Between stock ticks the window's compare reads "below" (the return), so the window draws on stock ticks only; the end tick's draw (the loop's wrap) stays
# The motion key windows: K <= frame < K + F54 holds for one tick when the frame steps F54 a
# tick (the 30 fps mode); the port's 60 fps mode steps F54 x 0.5 (4B9CA9, kModeSelects), so the
# window held for 2 ticks at 60 and 4 at 120, and everything keyed in it fired that often. Its
# width scaled by s is the step at every rate, so each key fires once, as at 30.
src 4B9964 | 4B9770's sound/effect key track (from the motion advance 4B9C80, before its step): a key K fires on K <= frame < K + F54 (the sounds 44E3C0/44E620/44E710/44EA00, the footstep dust 2DB8C0); with the frame stepping F54 x s (4B9CA9's mode select) the window held 1/s ticks; F54 x s keeps it to one tick, as at 30
src 4B9B06 | 4B9770's flag key track: +F32 (cleared each tick at 4B9AE0) gets a key's bits on K <= frame < K + F54; its five readers (20F2D0 from 2163FE, a shake's start; 2475DA, 247A67, 24924E, 304ADE, voices with a random variant) act on each tick it is set; F54 x s keeps it to one tick, as at 30
group player
dst 3B2F86 | pl00 3B2CF0's footstep dust: 5 <= frame < 5 + F54 spawns dust of a random variant (2DB8C0, rand & 3) on every tick of the window, 1/s ticks with the frame stepping F54 x s; the width F54 x s keeps it to one tick, as at 30
dst 3B349A | pl00 3B2CF0's second footstep dust window (5 <= frame < 5 + F54), as 3B2F86: one tick, as at 30
dst 3B37EC | pl00 3B2CF0's third footstep dust window (5 <= frame < 5 + F54), as 3B2F86: one tick, as at 30
# esp19 (effect type 0x13), the sun's lens flare: its draw (slot 4, 1A55E0) reads back an
# occlusion pixel each tick and raises the intensity 9A6B24 by 0.2 while the sun shows (or in
# map 0x102); its update (slot 1, 1A5D00) lowers it by 0.25 a tick otherwise and, while it is
# not below 0, spawns the flare's sprites (up to 20, one per element) every tick. Each sprite
# lives until its keyframe step (18FF60, stock ticks only) reaches its count of 1: two stock
# ticks. Spawned on every tick at 120, about four times as many overlapped, and the fades ran
# four times as fast.
group effect
notyetneg 1A5FCA notyet:1A6147 | esp19 1A5D00 (slot 1): the flare's sprites (up to 20, seeded at 1A602A) are spawned every tick its intensity is not below 0, and live two stock ticks; between stock ticks the count's test reads negative, so they are spawned on stock ticks only and as many overlap as at 30
lin 1A5F88 | esp19 1A5D00: the flare's intensity 9A6B24 -= 0.25 a tick while its draw saw no sun (9A6B21 clear): the fade-out
lin 1A5A2F | esp19's draw 1A55E0 (slot 4): the flare's intensity += 0.2 a tick, capped at 1, while the occlusion readback sees the sun (or in map 0x102): the fade-in
# The battle list's reinforcement wait 9C4760 (a global, 10 at the list's set-up 23E200): while
# fewer enemies are up than the list holds, its spawners (23EF20, 23F070, from 23C420 each tick)
# count it down and, at 0, reload 10 and spawn one. It had no row: reinforcements came every
# 10 ticks, 83 ms at 120 instead of 333. As 2030D1/2030D7: the count's store on stock ticks
# only, and its zero test (of the register) "not yet" between them.
group actor
count 23EF8A | 23EF20 (lists with +80 clear): the reinforcement wait 9C4760 -= 1 a tick while fewer enemies are up than the list holds; at 0 it reloads 10 and spawns a random group's next enemy (23EC00)
notyet 23EF90 notyet:23F064 | 23EF20: the wait's zero test reads the decremented register: between stock ticks it reads "not yet", so the reload and the spawn come on the stock tick
count 23F0E7 | 23F070 (lists with +80 set): the same wait 9C4760 -= 1 a tick; at 0 it reloads 10 and spawns the next enemy of the first group short of its count
notyet 23F0ED notyet:23F1DF | 23F070: the wait's zero test, as 23EF90
# hm8e's slot 32 (3337F0, each tick after the human update 305840 clears +11EC): +1310 counts
# down and, at 0, reloads a random 0..15 while the model's materials get animation state 2
# (3DE510) for that tick, 0 otherwise: a flicker with no row, four times as often at 120. With
# the store on stock ticks only, the held ticks after the count stores 0 take the reload path
# too (its draw and store discarded), so state 2 holds one stock period, at most 3/4 of a
# stock tick early, and the next stock tick's reload commits. A not-yet on the zero test would
# cut the flash to one tick, so there is none.
group human
count 333869 | hm8e 3337F0 (slot 32): the flicker's countdown +1310 -= 1 a tick, reloaded with a random 0..15 at 0 while the materials take state 2 for that tick; on stock ticks only, the flicker comes at stock cadence and holds a stock period
# 491BD0 (each tick from 48EBB0, mode +157 = 0 of the minigame object 48EC20 under 490190, while
# B6B308 is set): with fewer than six type-0x5C7 objects up, it picks a random entry of its
# table's row (rand & 15) and spawns that entry's object with the entry's chance (rand x 254.9
# below its byte): a chance a tick, so they came four times as fast at 120. As the em60
# trials: between stock ticks the chance's compare reads "below", so it is tried once a stock
# tick.
group objects
notyetb 491DCD notyet:491EFA | 491BD0: the spawn's chance (the entry's byte against rand x 254.9) a tick: between stock ticks it reads "below" (the return), so a spawn is tried once a stock tick, as stock's
# ut1d 532BC0 (its update): two chances a tick while a paced wait is idle: an effect at 1 in 64
# when +E40 is 0 (then +E40 = 60), and the material pulse at 1 in 16 when +E3E is 0 (then 30
# ticks of sin). Each chance is a draw tested against a mask in memory (`test m, r`): between
# stock ticks it reads "not yet" (no effect, no pulse), so each is tried once a stock tick, as
# stock's. A not-yet on the waits' zero tests would send the held ticks into their decrements,
# which are action_timers.h's (532BEF, 532D57): with that family off and this one on, a 0 would
# wrap to 65535.
group objects
notyet 532C00 notyet:532C55 | ut1d 532BC0: the effect's chance (rand & 63 == 0) while +E40 is 0: between stock ticks it reads "not yet", so it is tried once a stock tick
notyet 532D96 notyet:532DAA | ut1d 532BC0: the material pulse's chance (rand & 15 == 0) while +E3E is 0: between stock ticks it reads "not yet", so it is tried once a stock tick
