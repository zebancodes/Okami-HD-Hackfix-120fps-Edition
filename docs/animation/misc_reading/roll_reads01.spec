# 2026-10-10: draws in functions nothing references. Each function is its own .pdata entry,
# and no direct call or jump, 8-byte pointer, rip-relative lea/mov, 4-byte RVA outside
# .pdata or export names it; the decompile's neighbours do not fall into it.
dead | 1BC2E0 (beside the generators) is never called: no reference of any kind | 1BC31D 1BC342 1BC390
dead | 1BC3E0 (beside the generators) is never called: no reference of any kind | 1BC43B 1BC457 1BC475
dead | 207AA0 is never called: no reference of any kind | 207AC7 207B01 207B3C
dead | 23E9A0 is never called: no reference of any kind | 23E9C2
dead | 2B5830 (em60's helpers) is never called: no reference of any kind | 2B5860
dead | 2B5910 (em60's helpers) is never called: no reference of any kind | 2B5932
dead | 2B60B0 (em60's helpers) is never called: no reference of any kind | 2B60D2
dead | 2B6100 (em60's helpers) is never called: no reference of any kind | 2B612B
dead | 2B62A0 (em60's helpers) is never called: no reference of any kind | 2B62CB
dead | 366450 is never called: no reference of any kind | 366481 36649E 3664B4
dead | 4A1DA0 is never called: no reference of any kind | 4A1DF3
dead | 55BF30 is never called: no reference of any kind (56BB90 and 56E010 are copies of it) | 55BF57 55BF91 55BFCC
dead | 56BB90 is never called: no reference of any kind | 56BBB7 56BBF1 56BC2C
dead | 56E010 is never called: no reference of any kind | 56E037 56E071 56E0AC
dead | 5EA670 (em89's helpers) is never called: no reference of any kind | 5EA6D1
dead | 5EA9A0 (em89's helpers) is never called: no reference of any kind | 5EA9F3
dead | 5EAA40 (em89's helpers) is never called: no reference of any kind | 5EAA93
