# 2026-10-11: the follow-up list's first items (fps-followups.md, ninth pass).
# Landing look-aheads: each object's fall moves y by s x vy a tick (vy, +E54, in stock units:
# anff 202A30's pre 202B25 for the animals; 20EA30 with xmm2 = speed x s, the step rows on
# +1080, for the enemies; 20EA30's callscale rows for the weapons), but `y + vy <= ground`
# looked a stock tick ahead: at 120 they snapped to +E50 up to 3 ticks early, a whole stock
# tick's fall in one 8 ms tick. pre: y + s x vy, the next tick's position, as an0c's and
# wp0b's (1EE7D4, 1ED0D0, 387E5D). The sum feeds only the compare on every path.
group actor
pre 206209 | an00..an18 (and the other animals sharing slot 40's 206000, the jump/hop action): the landing look-ahead y + vy <= ground (+E50) after the motion advance; vy is stock-unit (anff 202A30 moves y by s x vy, pre 202B25): y + s x vy
pre 2753D5 | em2b 275280 (slot 17 of 680790, update 273FF0, whose fall 20EA30 takes speed x s, step 27425C): the landing look-ahead, y = +E50 and the next phase on contact
pre 277D3B | em2b 2779A0 (slot 16 of 680790): the landing look-ahead after its paced turn and step
pre 28CBEA | em4d/em4e/em50 28CB20 (slot 16 of 681578/681718/681918, update 288D90, fall step 288FB0): xmm1 = vy after the phase test 28CBD7 (vy <= xmm6: phase 2, unchanged); the sum jumps to 28CC54's compare with +E50: only the anticipated height is scaled
pre 29FF74 | 29FDD0 (slot 17 of 681E58/682040/6822A0/682440, update 29EE50, fall step 29F009): the landing look-ahead, then y = +E50 and phase 4
pre 2A0523 | 2A0400 (slot 17 of the same four classes): the landing look-ahead, then y = +E50 and phase 4
group player
pre 384F33 | wp04 384E30 (from 3844F0 and its 384A80; fall 20EA30, callscale 3845DA): the landing look-ahead after vy = 5 at its set-up 384EBD
pre 386757 | wp07 3866C0 (from 386320; fall callscale 386409): the landing look-ahead, then a sound and a shake
pre 389AFC | wp0e 389A30 (the imps' dropped weapon, from 389730; fall callscale 3897F7): the landing look-ahead, vy = 6 at the drop (242060, 249F83)
# The unread turns (survey_turn_steps.MANUAL): two per-tick turns of the enemies' wrapper
# 23A2E0 whose limit is a stock-unit field. (The five weapon calls were already converted by
# their slow-motion dt's dst rows; 24DB65 is a one-off aim; 564FFE had its row.)
group actor
callscale 25A401 | em0f 25A310 (from 25A2D0): every tick of phase 1 (and the set-up tick) turns toward Amaterasu by at most +E14 x 3 degrees x speed; +E14 = 1 + rand, set once per action (25A3D1): a stock-unit limit a tick
callscale 2766F5 | em2b 276400 (from 275020): while frame +F48 is in (15, 37) with +E37 clear it turns toward Amaterasu by at most +E14 degrees x speed a tick; +E14 ramps from 3 by 0.3 x speed a tick (2766FA's step row) to 12: a stock-unit limit
# wp0e's move: the imps' weapon (type 0x60E, spawned by 24A0D2 and held through the owner's
# +1298) is dropped by the knockback 242060 / 249F83: heading +E14 = the imp's, +E18 = -6 (back
# along it), +E54 = 6, state 0x101. 389A30 then moves it by +E18 every tick through 2DA460 and
# keeps +E18 x 0.9 (decay_factors.h 389AD5, 0.9^s): +E18 is in stock units, and at 120 the drop
# slid about 3.8 times as far.
group player
callscale 389AC8 | wp0e 389A30: the move by +E18 along +E14 (2DA460's xmm1) a tick, +E18 = -6 at the drop and x 0.9 a stock tick after: s of it a tick, the speed itself kept
# The end-of-animation rolls (random_rolls.csv mixed_guard): a draw on the motion advance's
# "ended" answer. A non-looping motion reports its end on every tick after it (4B9C80 keeps
# the frame at length - 0.0001), so a roll there that mostly does nothing was retried four
# times as often at 120: the animals' 1 in 4 or 1 in 8 that ends a held pose, em60's type
# 0x223 waits. A looping motion reports it once a loop, right at any rate. notyetend: between
# stock ticks the answer reads "not ended" unless the object's motion loops.
group actor
callend 1DB882 (0x1BD6D0,0x1DB895) | an01 1DB670 (from 1D8870's slot 21): the motion's end (4B9B70), then 1 in 4 (rand & 3 == 0) requests 0x101 at the join 1DB88B: the draw itself (the end's je and the draw's test are short, the join leaves no window); held and not looping it answers eax = -1, `test al, 3` reads nonzero and the block returns (rax unread: 1D89F4 and the slot-21 dispatchers 20273E/203E97 overwrite it)
notyetend 1E2E8D notyet:1E2FCE | an06/an08 1E2DB0 (from 1E04A0's slot 21): the end (4B9B70), then 1 in 4 requests a state: the draw 1E2E95
notyetend 1E5E7C notyet:1E5FAB | 1E5D50: the end of the motion it plays (4BA080, 4B9C80), then 1 in 4: the draw 1E5E84
notyetend 1EC6CD notyet:1EC83E | 1EC5B0: the end (4B9B70) of its first motion, then 1 in 4: the draw 1EC6D5
callend 1EC82B (0x1BD6D0,0x1EC83E) | 1EC5B0 (from 1E98FE): the end (4B9B70) of its second motion, then 1 in 4 requests 0x101 at the join 1EC834: the draw itself, as 1DB882 (rax unread after: the slot-21 dispatchers overwrite it)
notyetend 1EFD67 notyet:1EFD72 | 1EFCC0: the end (4B9C80), then 1 in 8 restarts the phase (+E36 = 0): the draw 1EFD62's test
notyetend 1F9CFA notyet:1F9A71 | 1F9970: the end (4B9B70), then 1 in 4: the draw 1F9D02
notyetend 1F9E00 notyet:1F9A76 | 1F9970: the end (4B9B70) of its other motion, then 1 in 4: the draw 1F9E08
notyetend 1FD4B7 notyet:1FD422 | 1FD040: the end (4B9C80), then 1 in 4: the draw 1FD4BF
notyetend 200750 notyet:200837 | 2006D0: the end (4B9B70), then 1 in 4: the draw 200758
notyetend 200D17 notyet:200D22 | 200C70: the end (4B9C80), then 1 in 8 restarts the phase (+E36 = 0): the draw 200D12's test
notyetend 200E46 notyet:200E51 | 200D30: the end (4B9C80), then 1 in 8 sets phase 2: the draw 200E41's test
notyetend 2B3AD7 notyet:2B3B78 | em60 2B3960 (from 2AB930's slot 16): the end (239420), then for type 0x223 an 0.8 / 0.3 pick that does nothing 86% of the time (state 0x1001 or 0xF01 otherwise; the others always act): the draws 2B3B0E, 2B3B44
notyetend 2B3DDD notyet:2B3ED5 | em60 2B3C90 (from 2AB930's slot 16): the end (239420), then for type 0x223 0.6 E01, else an 0.8 / 0.3 pick that does nothing 34% of the time (the others always act): the draws 2B3E32..2B3EA4
# an1e 1FCC10's draw 1FCD3F was filed with them, but the motion's end only skips a turn there
# (jne to the join 1FCCEE): it is a 1 in 2 a tick, once within 20 of its target (+1160) with
# the paced wait +E3E spent, that changes the state. Between stock ticks the test reads "not
# yet" (the return), so it is tried once a stock tick.
notyet 1FCD35 notyet:1FCD65 | an1e 1FCC10 (from 1FA7F0): within 20 of +1160, the wait +E3E's test (> 0: return); its draw 1FCD3F (rand & 1 == 0 sets state 1 with a random sub-state) follows: between stock ticks the wait reads "not yet", so the draw is tried once a stock tick (the draw's own test has a call in its window)
# em89 5EC0F0: once Amaterasu has stayed above y = 100 for 450 stock ticks (+5050, counted),
# each tick draws 0.98: reset the phase timers +5030/+5028 and maybe start state 0x901 (98%),
# else the normal path (2%): +5034's countdown by s x speed, the paced trials, and with the
# countdown done the state request 0xB01 or 5F52C0. At 120 the 2% came on four times as
# many ticks: the countdown kept its rate on average but its end's request came about 1.2 s
# sooner. A notyetb would have cut the countdown to a quarter. hold: decided on the stock
# tick and kept for its period, so the period runs the path stock's tick did.
group actor
hold 5EC245 | em89 5EC0F0 (slot 8 of 6BCB38, a boss: one at a time): the 0.98 draw 5EC238's compare once +5050 > 450: decided once a stock tick and held through the period, so the reset path or the normal one runs for the whole period, as for stock's tick
