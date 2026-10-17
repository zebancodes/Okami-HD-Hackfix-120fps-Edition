# 2026-10-10: updates coverage counted covered while a step of theirs is
# converted nowhere on its own path, found by tools/trace_steps.py over every
# covered census site (the 319 field/register steps of 10-09 and the rest).
group player
lin 3C180C | pl00 3C13F0: past +E3C 10 (paced), heading +B4 turns toward the locked target by 2DDF90 at most 8 degrees a tick; the sibling state 3C7880 scales the same limit (3C7A20)
pre 3CAFBA | pl00 3CAE60 sub-state 1: while 8909C0's lift reports a height above her, pos.y += its rise speed (169780: 1.5, or 2E3210's per-type table) a tick; xmm0 holds only that step
lin 3A25DE | wp5f 3A2530: the forward speed +E48 (moved by 2DA410, callscale 3A25D1, stock units) gains 4 a tick; its lifetime fade (phase_steps 3A25EE) and remaining distance (lin 3A25C1) are paced
lin 38CC76 | wp12 38CB60: joint 1's +B4 copies +107C, which turns 20 degrees a tick while the paced +E3E counts down
lin 38D140 | wp12 38CF10: the same spin, -40 degrees a tick while the paced +E3C counts down
lin 39BA74 | wp47 39B950: the hit point's distance +E28 (11 at the start) falls 14 a tick while the paced +E3C counts 18 down; each tick's 2DC7B0 hit test sits at that distance
group actor
pre 2C1AC2 | em65 2C0A60 (vt 8): +16BC += the motion factor +F54 a tick, an elapsed-time clock read as (int) against 25-tick windows (2C4FB8, 2C6276); its sibling +16B8 has the step row 2C1ABA
src 282757 | em2d 281AE0, sub-objects in states 1..3 under slow time (B6B2BC bit 21): +C gains the speed +1080 three times a tick; the first add has the step row 282744, this is the second
src 282765 | em2d 281AE0: the third add of the same speed
lin 5F2B39 | em89 5F2A60: the speed field +5060 approaches 3 x +505C by 0.0065 a tick; the four nearer bands have lin rows (5F2AAD..5F2B19), this is beyond 500
lin 5F2B59 | em89 5F2A60: the same push beyond 1000
lin 5F2B70 | em89 5F2A60: the same push between 100 and 500
lin 5F2C1F | em89 5F2A60: the other mode (dl = 0): the push 0.0055 for every band
srcroot 28D9CF | em4d 28D810 (em4d em4e em50): the forward speed +E18 (moved by 2DA410, callscale 28D9FD) grows x1.2 a tick to its cap of 7
count 5F0A01 | em89 5F08E0 (from 5ED890): +E37 counts every tick (every 4th frame under slow time, frame_gates.h's test) while +4FA8 < 0x4B; each multiple of 6 fires a volley
notyet 5F0A1D 0x5F0CAE | em89 5F08E0: the volley test (+E37 a multiple of 6, jne past it): between stock ticks the held count must not fire again
count 5F1871 | em89 5F1750 (from 5ED890): the same volley count while +4FA8 < 0x3B
notyet 5F188D 0x5F1AD9 | em89 5F1750: its volley test
group objects
pre 46849E | camera 468420 (from 47C9D0, 47DAB0): pitch +3B0 += the stick velocity +3B4 a tick, whose input is the port's x time scale and whose 0.85 decay is decay_factors.h's root; the other camera modes' pre rows (46832D, 468698, 468F27)
dst 41F615 | cSubScrFilesInfoMess 41F5B0: the panel's +24 moves by (a.y - b.y) / 15 a tick while the countdown +D4 (count 41F62B) runs 15 stock ticks
dst 420359 | cSubScrFilesInfoMess 4202F0: the same slide back (its countdown has count 42036F)
src 4F0ED0 | ut23 4F0CD0: the spin +1140 += +1164 a tick, +1164 ramping by 0.00058 (phase_steps 4F0E59, src 4F0EA6) to a cap of 1 degree a tick
src 4F10AB | ut23 4F0CD0: the reverse spin, +1140 -= +1164
src 56FBDF | utb6 56F760: the distance +E10 (60 down to 30) falls by +E18 a tick, +E18 gaining 0.6 a tick (phase_steps 56FBE3)
src 1C594E | cMcAction 1C5870: the slide +B8 moves by +BC a tick toward 0, +BC decaying x0.95 (decay_factors.h's root)
src 1C5023 | cMcAction 1C4FA0: after the paced delay +C8 (integer_skips.h), the scale +C4 grows by the double 0.1 a tick to 1 beside its pulse phase +CC (phase_steps 1C5059)
lin 3FCF6E | cCockGameOver 3FCF50: +68 -= 17 a tick while the countdown +7C (menu count) runs, beside +6C's lin 3FCF9A and +70/+74's phase steps
srcroot 5CBC58 | em85 5CBAD0 (dl != 0): the speed field +343C *= 0.995 a tick before its 0.0065 push (lin 5CBC60); the other mode's 0.99 is decay_factors.h's (5CBD05). The store is shared behind a jmp, which the decay finder's window does not follow
count 3D782B | 3D77B0 (a screen wipe drawn each tick): its alpha byte +6 gains 16 a tick to 255 beside the wipe's progress +5BE8 (phase_steps 3D7814)
