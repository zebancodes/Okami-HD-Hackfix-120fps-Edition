# Heading and vector movers, 2026-10-08: per-tick stock-unit distances.
# wp0e 389AC8 remains unresolved: no nonzero speed initializer established.
group player
callscale 37F0DF 2DA460:xmm1 | wp00 37F060: retained signed brush direction +10F4 times 3.5; heading +10F0 and paced +E3C wait stay unchanged.
callscale 3870B3 2DA460:xmm1 | wp09 387010: retained signed brush direction +111C times 6.5; heading +1118 and paced +E3C wait stay unchanged.
callscale 38A0B8 2DA460:xmm1 | wp0f 389FF0: retained signed brush direction +10F4 times 3.5; heading +10F0 and paced +E3C wait stay unchanged.
callscale 39AD9F 2DA460:xmm1 | wp47 39AD20: retained signed brush direction +10E4 times 3.5; heading +10E0 and paced +E3C wait stay unchanged.
lin 38A973 672ED8:10 | wp0f 38A8F0 outbound: +E10=(0,0,10,1), consumed each tick by 38AA4A during the paced wait. Homing overwrites the transient vector.
lin 38AA0D 6799B4:4 | wp0f 38A8F0 homing: normalized owner displacement times 4, then += position each tick; preserve target geometry.
lin 389A98 675A8C:16 | wp0e 389A30: random times 16 degrees is added to +B0 and wrapped every tick after the setup block. Scale the increment only; RNG and +E14 heading unchanged.
group actor
dst 2A863A scale:2A8650 | em60 helper 2A8630: only caller 2AD82E passes retained +1590 velocity in airborne state 6. Scale +1080 at its read for the vector product; gravity 2AD83B is already converted.
