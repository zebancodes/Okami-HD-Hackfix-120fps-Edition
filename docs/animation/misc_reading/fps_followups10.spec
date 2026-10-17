# 2026-10-11: the player's half-second sound. pl00 3B2CF0 plays a sound when the frame counter
# B6AC20 (every tick) divides by fps / 2: 15 ticks at 30 and 30 at 60, half a second, but the
# fps byte reads 60 at 120 as at 60, so every 30 ticks, a quarter second. The quotient is
# unread; the divisor register is kept by the stub (div does not write it).
group flag
divn 3B35F5 0x3B35EA | pl00 3B2CF0: a sound (44E3C0, 0x1C) when fc % (fps / 2) == 0: the divisor times the flag group's N (2 at 120), half a second at every rate
divn 3B394E 0x3B3943 | pl00 3B2CF0: the other half-second sound (0x1C), as 3B35F5
