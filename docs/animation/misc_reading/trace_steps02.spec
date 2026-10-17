# 2026-10-10: em86's close-in and the decay list's camera mode.
group actor
blend 5D1DDD | em86 5D1810, after its switch every tick: forward by (distance to Amaterasu - 200) x 0.12 x t x speed x +F54 (2DA3F0, 5D1E28), t the turn factor 1..10 from the distance to the anchor +5430; an approach toward 200 whose factor reaches 1 and past it (stock overshoots there): 1 - (1 - 0.12)^s, exact at t x speed x +F54 = 1, as 5D1599 for 5D1080's 220
group objects
srcroot 47AE31 | camera 47A3A0: the stick velocity +3C0 (input x the port's time scale, idle x the mode-table pair) is damped x0.85 a tick after its use; as the other camera modes' 0.85 (468365, 4686D8, 468F57)
pre 47AE44 | camera 47A3A0: +3BC += the velocity +3C0 a tick before the 0.85; as the other camera modes' pre rows (46832D, 468698, 468F27)
