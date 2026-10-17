# 2026-10-11: countdowns that ended early (tools/early_countdowns.py --spec).
# A countdown a family paces holds each value for N ticks at N times the rate. Its zero test,
# when it runs before the decrement on a tick (the action timers' `test ax, ax; je` at the top,
# a `cmp word [F], 0`, or after a count row on the store alone, the old value or the decrement's
# own flags), reads 0 on every tick after the stock tick that stored the 0: its zero side acted
# up to 3 ticks before stock's next tick, and a countdown reloaded there lost that much a cycle
# (a period of R stock ticks for stock's R + 1). Only a transient zero is gated: every path of
# the zero side re-arms the field with a nonzero value (2026-10-12: a store of the actor's
# state bytes counted too until 101 of the first 131 rows, chosen that way, were removed: the
# test can run again with the field resting at 0, and the active path then ran on N - 1 of
# every N ticks; smoke puffs piled up over a battle's enemies). Between stock ticks the test
# reads "not yet", so the zero side comes on the stock tick, as stock's. notyet for a count
# row's countdown (its group); notyett for the timer families' (action, memory, lea timers),
# whose mask it takes, so it never runs while they are off.
# Left: zero tests behind a motion's "ended" answer (event_counters.event_gated: 1F13A3,
# 1FD14D, 208FB5, 36A1A6, 3C45EB, 562598, 651967, 651BC7): they run once a loop of a looping
# motion, and a "not yet" would drop the loop ends that fall between stock ticks; countdowns
# that rest at 0 (their zero side is the idle behaviour every tick); two integer_skips.h
# system counters (early_countdowns.REVIEWED).
group actor
notyet 1DBFCF notyet:1DBFFD | 1DBFB0: register's countdown 1DBFB6/1DBFC8 (world_anims.h count (store)): its zero side (store word ptr [rcx + 0x1184], ax at 1DBFE0) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet
notyet 1DC14A notyet:1DC178 | 1DC130: register's countdown 1DC134/1DC143 (world_anims.h count (store)): its zero side (store word ptr [rcx + 0x1184], ax at 1DC15B) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet
notyet 4847A6 notyet:4847D5 | 484610: [rdi + 120B]/1's countdown 48479F/4847D7 (world_anims.h): its zero side (call 1989F0 at 4847C7) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyet 4A1D44 notyet:4A1D83 | 4A1A80: [rbx + 1079]/1's countdown 4A1D3D/4A1D85 (world_anims.h): its zero side (store byte ptr [rbx + 0x1079], 0x1e at 4A1D75) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyet 276312 notyet:276317 | 2762A0: [rbx + 10C2]/2's countdown 27630B/27631A (world_anims.h): its zero side (store word ptr [rbx + 0x10c2], ax at 276330) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyet 276CF0 notyet:276CF5 | 276CD0: [rbx + 10C2]/2's countdown 276CE6/276CF8 (world_anims.h): its zero side (store word ptr [rbx + 0x10c2], ax at 276D0E) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyet 276F26 notyet:2770F8 | 276DE0: [rsi + E3C]/2's countdown 276F1F/2770FB (world_anims.h): its zero side (call ??GcVec@math@wk@@QEBA?AV012@AEBV012@@Z at 276F9B) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyet 5D3861 notyet:5D3865 | 5D3600: [rbx + 53E4]/4's countdown 5D3853/5D3867 (world_anims.h): its zero side (store dword ptr [rbx + 0x53e4], 0x5a at 5D3874) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyet 20297D notyet:2029BC | 202920: [rbx + 1187]/1's countdown 202976/2029BE (world_anims.h): its zero side (call qword ptr [rax + 0x60] at 202987) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyet 4B335F notyet:4B33BE | 4B3300: [rbx + F1]/1's countdown 4B3358/4B33C0 (world_anims.h): its zero side (call 44E530 at 4B33B0) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
group objects
notyet 4D13EF notyet:4D1448 | 4D1350: [rbx + E36]/1's countdown 4D13E8/4D144A (world_anims.h): its zero side (store byte ptr [rbx + 0xe36], 0x59 at 4D13F3) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyett 62F8B2 (0x62F8E9,0x62F8AB) | 62F700: [rbx + E3C]/2's countdown 62F8A1/62F8AB (lea_timers.h): its zero side (call 44E3C0 at 62F8D8) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyett 632411 (0x632448,0x63240A) | 632230: [rdi + E3C]/2's countdown 632400/63240A (lea_timers.h): its zero side (call 44E3C0 at 632437) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyet 2F9A5D notyet:2F9A9C | 2F9920: [rbx + E3C]/2's countdown 2F9A56/2F9A9F (world_anims.h): its zero side (call 1989F0 at 2F9A80) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyett 215D38 (0x215E7A,0x215D31) | 215C90: [rbx + E3C]/2's countdown 215D27/215D31 (lea_timers.h): its zero side (call 19C850 at 215DE8) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyett 215EC2 (0x216053,0x215EBB) | 215E90: [rbx + E3C]/2's countdown 215EB1/215EBB (lea_timers.h): its zero side (call 19C850 at 215F5E) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyet 224020 notyet:224053 | 223F20: [rbx + E35]/1's countdown 224019/224055 (world_anims.h): its zero side (call 44E3C0 at 224045) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyett 23631B (0x23634D,0x236314) | 235A90: [rbx + E3C]/2's countdown 23630A/236314 (lea_timers.h): its zero side (call 16AA00 at 236327) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyett 23729C (0x236EC0,0x237295) | 236A50: [rsi + E3C]/2's countdown 23728B/237295 (lea_timers.h): its zero side (store word ptr [rsi + 0xe3c], ax at 2372B3) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyet 4E40C5 notyet:4E4158 | 4E3F90: [rbx + 0]/4's countdown 4E4106/4E4106 (world_anims.h): its zero side (store dword ptr [rbx], eax at 4E40D2) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyett 57AAD8 (0x57AB13,0x57AB6C) | 57A880: [rbx + E3E]/2's countdown 57AB5D/57AB6C (action_timers.h): its zero side (call 57CD80 at 57AAFB) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyet 5A339B notyet:5A339F | 5A3340: [rbx + E35]/1's countdown 5A3394/5A33A1 (world_anims.h): its zero side (store byte ptr [rbx + 0xe35], 5 at 5A33AE) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyet 5A4AC2 notyet:5A4AC6 | 5A49A0: [rbx + 10E2]/1's countdown 5A4ABB/5A4AC8 (world_anims.h): its zero side (store byte ptr [rbx + 0x10e2], 6 at 5A4AD5) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyet 5A4B84 notyet:5A4B88 | 5A4B40: [rcx + 10E2]/1's countdown 5A4B7D/5A4B8A (world_anims.h): its zero side (store byte ptr [rcx + 0x10e2], 6 at 5A4BA0) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyet 5A4D3F notyet:5A4D43 | 5A4CE0: [rdi + 10E1]/1's countdown 5A4D38/5A4D45 (world_anims.h): its zero side (store byte ptr [rdi + 0x10e1], 4 at 5A4D52) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyet 5A5A20 notyet:5A5AA9 | 5A5950: [rdi + 1071]/1's countdown 5A5A19/5A5AAB (world_anims.h): its zero side (store byte ptr [rdi + 0x1071], 2 at 5A5A37) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyett 5A704C (0x5A7051,0x5A7054) | 5A6F60: [rbx + E3C]/2's countdown 5A7045/5A7054 (action_timers.h): its zero side (call 1989F0 at 5A7081) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyet 5A947B notyet:5A947F | 5A9090: [rdi + 1116]/1's countdown 5A9474/5A9481 (world_anims.h): its zero side (call 1989F0 at 5A94D2) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyet 5A9BD4 notyet:5A9BD8 | 5A9BC0: [rcx + 10E6]/1's countdown 5A9BCA/5A9BDA (world_anims.h): its zero side (store byte ptr [rcx + 0x10e6], 2 at 5A9BE2) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
notyett 244FF5 (0x245170,0x244FEE) | 244C80: [rsi + E3C]/2's countdown 244FE4/244FEE (lea_timers.h): its zero side (call 1989F0 at 24501C) acted up to 3 ticks before stock's next tick; between stock ticks it reads not yet, and the cycle it reloads keeps its stock length
