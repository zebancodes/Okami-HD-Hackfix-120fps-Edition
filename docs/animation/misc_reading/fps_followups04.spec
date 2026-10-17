# Per-tick enemy decision chains (2026-10-07, second session): em65, em88, em60.
group actor
# em65 update 2C0A60 (vtable 682FA8 slot 8): after its paced +1714 pause the idle decision chain runs every tick; 84 trials, each failing between stock ticks.
notyetb 2C0CDD notyet:2C0D22 | em65 trial: chance 0.01 a tick, success store word ptr [rdi + 0x122a], r12w; held ticks take the failure 2C0D22.
notyetb 2C0D38 notyet:2C0D4C | em65 trial: chance 0.01 a tick, success calls action setter 2C9FD0; held ticks take the failure 2C0D4C.
notyetb 2C0D51 notyet:2C0DC3 | em65 trial: chance 0.01 a tick, success requests state 1501; held ticks take the failure 2C0DC3.
notyetb 2C0DD0 notyet:2C0DE4 | em65 trial: chance 0.005 a tick, success calls action setter 2CA190; held ticks take the failure 2C0DE4.
notyetb 2C0DE9 notyet:2C0DFD | em65 trial: chance 0.005 a tick, success calls action setter 2CA100; held ticks take the failure 2C0DFD.
notyetb 2C0E02 notyet:2C0E74 | em65 trial: chance 0.01 a tick, success requests state 1001; held ticks take the failure 2C0E74.
notyetb 2C0E81 notyet:2C0E95 | em65 trial: chance 0.018 a tick, success calls action setter 2C9D90; held ticks take the failure 2C0E95.
notyetb 2C0E9A notyet:2C0EF1 | em65 trial: chance 0.015 a tick, success requests state C01; held ticks take the failure 2C0EF1.
notyetb 2C0EF6 notyet:2C0F4D | em65 trial: chance 0.015 a tick, success requests state B01; held ticks take the failure 2C0F4D.
notyetb 2C0F52 notyet:2C0F67 | em65 trial: chance 0.015 a tick, success calls action setter 2C9E70; held ticks take the failure 2C0F67.
notyetb 2C0F6C notyet:2C0FA4 | em65 trial: chance 0.015 a tick, success calls action setter 2C9B20; held ticks take the failure 2C0FA4.
notyetb 2C0FA9 notyet:2C0FBD | em65 trial: chance 0.005 a tick, success calls action setter 2C99B0; held ticks take the failure 2C0FBD.
notyetb 2C0FCA notyet:2C0FD3 | em65 trial: chance 0.02 a tick, success calls action setter 2C9A70; held ticks take the failure 2C0FD3.
notyetb 2C0FE8 notyet:2C0FFD | em65 trial: chance 0.015 a tick, success calls action setter 2C9FD0; held ticks take the failure 2C0FFD.
notyetb 2C1012 notyet:2C1026 | em65 trial: chance 0.01 a tick, success calls action setter 2CA190; held ticks take the failure 2C1026.
notyetb 2C103B notyet:2C104F | em65 trial: chance 0.01 a tick, success calls action setter 2CA100; held ticks take the failure 2C104F.
notyetb 2C1064 notyet:2C1078 | em65 trial: chance 0.02 a tick, success calls action setter 2C9B20; held ticks take the failure 2C1078.
notyetb 2C10AC notyet:2C10C0 | em65 trial: chance 0.02 a tick, success calls action setter 2C9B20; held ticks take the failure 2C10C0.
notyetb 2C10F4 notyet:2C10FD | em65 trial: chance 0.02 a tick, success requests state 1001; held ticks take the failure 2C10FD.
notyetb 2C1116 notyet:2C112A | em65 trial: chance 0.15 a tick, success calls action setter 2C9B20; held ticks take the failure 2C112A.
notyetb 2C1148 notyet:2C1152 | em65 trial: chance 0.025 a tick, success requests state 1001; held ticks take the failure 2C1152.
notyetb 2C1167 notyet:2C1171 | em65 trial: chance 0.015 a tick, success requests state C01; held ticks take the failure 2C1171.
notyetb 2C1186 notyet:2C1190 | em65 trial: chance 0.015 a tick, success requests state B01; held ticks take the failure 2C1190.
notyetb 2C11A5 notyet:2C11FB | em65 trial: chance 0.01 a tick, success requests state 901; held ticks take the failure 2C11FB.
notyetb 2C120C notyet:2C1220 | em65 trial: chance 0.02 a tick, success calls action setter 2C9B20; held ticks take the failure 2C1220.
notyetb 2C123D notyet:2C1251 | em65 trial: chance 0.045 a tick, success calls action setter 2C9FD0; held ticks take the failure 2C1251.
notyetb 2C1266 notyet:2C127B | em65 trial: chance 0.025 a tick, success calls action setter 2CA190; held ticks take the failure 2C127B.
notyetb 2C1290 notyet:2C12A5 | em65 trial: chance 0.015 a tick, success calls action setter 2CA100; held ticks take the failure 2C12A5.
notyetb 2C12BA notyet:2C12C3 | em65 trial: chance 0.01 a tick, success requests state 901; held ticks take the failure 2C12C3.
notyetb 2C12E0 notyet:2C12F4 | em65 trial: chance 0.105 a tick, success calls action setter 2C9E70; held ticks take the failure 2C12F4.
notyetb 2C1309 notyet:2C1312 | em65 trial: chance 0.01 a tick, success calls action setter 2C9A70; held ticks take the failure 2C1312.
notyetb 2C1327 notyet:2C197B | em65 trial: chance 0.01 a tick, success requests state 901; held ticks take the failure 2C197B.
notyetb 2C133D notyet:2C1346 | em65 trial: chance 0.02 a tick, success requests state 1501; held ticks take the failure 2C1346.
notyetb 2C1353 notyet:2C135C | em65 trial: chance 0.03 a tick, success requests state 1001; held ticks take the failure 2C135C.
notyetb 2C1361 notyet:2C1376 | em65 trial: chance 0.015 a tick, success calls action setter 2C9D90; held ticks take the failure 2C1376.
notyetb 2C137B notyet:2C138F | em65 trial: chance 0.01 a tick, success calls action setter 2C9FD0; held ticks take the failure 2C138F.
notyetb 2C1394 notyet:2C13A8 | em65 trial: chance 0.01 a tick, success calls action setter 2CA190; held ticks take the failure 2C13A8.
notyetb 2C13AD notyet:2C13C1 | em65 trial: chance 0.01 a tick, success calls action setter 2CA100; held ticks take the failure 2C13C1.
notyetb 2C13C6 notyet:2C13CF | em65 trial: chance 0.01 a tick, success requests state C01; held ticks take the failure 2C13CF.
notyetb 2C13D4 notyet:2C13DD | em65 trial: chance 0.01 a tick, success requests state B01; held ticks take the failure 2C13DD.
notyetb 2C13E2 notyet:2C13F6 | em65 trial: chance 0.02 a tick, success calls action setter 2C99B0; held ticks take the failure 2C13F6.
notyetb 2C13FB notyet:2C191D | em65 trial: chance 0.01 a tick, success calls action setter 2C9B20; held ticks take the failure 2C191D.
notyetb 2C1424 notyet:2C1438 | em65 trial: chance 0.01 a tick, success calls action setter 2C9FD0; held ticks take the failure 2C1438.
notyetb 2C143D notyet:2C1452 | em65 trial: chance 0.015 a tick, success calls action setter 2C9D90; held ticks take the failure 2C1452.
notyetb 2C145F notyet:2C1473 | em65 trial: chance 0.009 a tick, success calls action setter 2CA190; held ticks take the failure 2C1473.
notyetb 2C1478 notyet:2C148C | em65 trial: chance 0.009 a tick, success calls action setter 2CA100; held ticks take the failure 2C148C.
notyetb 2C1499 notyet:2C14A2 | em65 trial: chance 0.02 a tick, success calls action setter 2C9A70; held ticks take the failure 2C14A2.
notyetb 2C14A7 notyet:2C14B1 | em65 trial: chance 0.015 a tick, success requests state C01; held ticks take the failure 2C14B1.
notyetb 2C14B6 notyet:2C14C0 | em65 trial: chance 0.015 a tick, success requests state B01; held ticks take the failure 2C14C0.
notyetb 2C14C5 notyet:2C14D9 | em65 trial: chance 0.02 a tick, success calls action setter 2C99B0; held ticks take the failure 2C14D9.
notyetb 2C14DE notyet:2C14F2 | em65 trial: chance 0.01 a tick, success calls action setter 2C9B20; held ticks take the failure 2C14F2.
notyetb 2C14F7 notyet:2C150B | em65 trial: chance 0.02 a tick, success calls action setter 2C9E70; held ticks take the failure 2C150B.
notyetb 2C1519 notyet:2C1539 | em65 trial: chance 0.04 a tick, success store dword ptr [rdi + 0x1714], ecx; held ticks take the failure 2C1539.
notyetb 2C154A notyet:2C155E | em65 trial: chance 0.02 a tick, success calls action setter 2C9B20; held ticks take the failure 2C155E.
notyetb 2C156F notyet:2C1578 | em65 trial: chance 0.01 a tick, success store word ptr [rdi + 0x122a], r12w; held ticks take the failure 2C1578.
notyetb 2C1589 notyet:2C1593 | em65 trial: chance 0.015 a tick, success calls action setter 2C9A70; held ticks take the failure 2C1593.
notyetb 2C15A8 notyet:2C15BD | em65 trial: chance 0.04 a tick, success calls action setter 2CA190; held ticks take the failure 2C15BD.
notyetb 2C15D2 notyet:2C15E7 | em65 trial: chance 0.04 a tick, success calls action setter 2CA100; held ticks take the failure 2C15E7.
notyetb 2C1605 notyet:2C1619 | em65 trial: chance 0.01 a tick, success calls action setter 2C9FD0; held ticks take the failure 2C1619.
notyetb 2C1626 notyet:2C162F | em65 trial: chance 0.03 a tick, success requests state 1001; held ticks take the failure 2C162F.
notyetb 2C1634 notyet:2C1648 | em65 trial: chance 0.01 a tick, success calls action setter 2CA190; held ticks take the failure 2C1648.
notyetb 2C164D notyet:2C1661 | em65 trial: chance 0.01 a tick, success calls action setter 2CA100; held ticks take the failure 2C1661.
notyetb 2C1666 notyet:2C166F | em65 trial: chance 0.01 a tick, success requests state C01; held ticks take the failure 2C166F.
notyetb 2C1674 notyet:2C167D | em65 trial: chance 0.01 a tick, success requests state B01; held ticks take the failure 2C167D.
notyetb 2C168A notyet:2C191D | em65 trial: chance 0.02 a tick, success calls action setter 2C99B0; held ticks take the failure 2C191D.
notyetb 2C16B2 notyet:2C16C6 | em65 trial: chance 0.035 a tick, success calls action setter 2C9B20; held ticks take the failure 2C16C6.
notyetb 2C16D4 notyet:2C16DE | em65 trial: chance 0.02 a tick, success store word ptr [rdi + 0x122a], r12w; held ticks take the failure 2C16DE.
notyetb 2C16E3 notyet:2C16F8 | em65 trial: chance 0.015 a tick, success calls action setter 2C99B0; held ticks take the failure 2C16F8.
notyetb 2C1705 notyet:2C1719 | em65 trial: chance 0.03 a tick, success calls action setter 2C9E70; held ticks take the failure 2C1719.
notyetb 2C1726 notyet:2C173A | em65 trial: chance 0.007 a tick, success calls action setter 2CA190; held ticks take the failure 2C173A.
notyetb 2C173F notyet:2C1753 | em65 trial: chance 0.007 a tick, success calls action setter 2CA100; held ticks take the failure 2C1753.
notyetb 2C176C notyet:2C1780 | em65 trial: chance 0.05 a tick, success calls action setter 2C9B20; held ticks take the failure 2C1780.
notyetb 2C1791 notyet:2C179A | em65 trial: chance 0.05 a tick, success store word ptr [rdi + 0x122a], r12w; held ticks take the failure 2C179A.
notyetb 2C17AB notyet:2C17BF | em65 trial: chance 0.01 a tick, success calls action setter 2C9A70; held ticks take the failure 2C17BF.
notyetb 2C17D0 notyet:2C17E4 | em65 trial: chance 0.05 a tick, success calls action setter 2CA190; held ticks take the failure 2C17E4.
notyetb 2C17F5 notyet:2C1809 | em65 trial: chance 0.05 a tick, success calls action setter 2CA100; held ticks take the failure 2C1809.
notyetb 2C181A notyet:2C1824 | em65 trial: chance 0.02 a tick, success requests state 901; held ticks take the failure 2C1824.
notyetb 2C15FC notyet:2C197B | em65 trial: chance 0.015 a tick (flags reach 2C183C through a jmp), success calls action setter 2C9A70; held ticks take the failure 2C197B.
callgate 2C1847 (0x2C9A70,"void") | em65 trial 2C1839 (chance 0.01 a tick, the type-267 chain's last) shares its jbe 2C183C with 2C15FC's jmp, so no window fits the compare: between stock ticks its success path skips the action setter 2C9A70 instead (rax unread; the join 2C197B follows). Every other path into 2C1842 is a gated trial.
notyetb 2C1851 notyet:2C1865 | em65 trial: chance 0.01 a tick, success calls action setter 2CA190; held ticks take the failure 2C1865.
notyetb 2C186A notyet:2C187E | em65 trial: chance 0.01 a tick, success calls action setter 2CA100; held ticks take the failure 2C187E.
notyetb 2C188B notyet:2C189F | em65 trial: chance 0.02 a tick, success calls action setter 2C9FD0; held ticks take the failure 2C189F.
notyetb 2C18AC notyet:2C191D | em65 trial: chance 0.05 a tick, success store word ptr [rdi + 0x122a], r12w; held ticks take the failure 2C191D.
notyetb 2C192A notyet:2C197B | em65 trial: chance 0.003 a tick, success requests state 1201; held ticks take the failure 2C197B.
# em88 update 5DF660 (vtable 6BC950 slot 8): once its paced +3878 cooldown is spent the decision chain runs every tick; 33 trials, each failing between stock ticks.
notyetb 5DFCB2 notyet:5E0697 | em88 trial: chance 0.2 a tick, success requests state 1001; held ticks take the failure 5E0697.
notyetb 5DFD99 notyet:5DFDA2 | em88 trial: chance 0.005 a tick, success requests state 501; held ticks take the failure 5DFDA2.
notyetb 5DFDA7 notyet:5DFDF8 | em88 trial: chance 0.005 a tick, success requests state 601; held ticks take the failure 5DFDF8.
notyetb 5DFE05 notyet:5DFE0E | em88 trial: chance 0.001 a tick, success store dword ptr [rbx + 0x3860], 0x438c0000; held ticks take the failure 5DFE0E.
notyetb 5DFE1B notyet:5DFE6C | em88 trial: chance 0.015 a tick, success requests state 1401; held ticks take the failure 5DFE6C.
notyetb 5DFE79 notyet:5DFECA | em88 trial: chance 0.025 a tick, success requests state 1201; held ticks take the failure 5DFECA.
notyetb 5DFECF notyet:5DFF37 | em88 trial: chance 0.015 a tick, success requests state D01; held ticks take the failure 5DFF37.
notyetb 5DFF44 notyet:5DFFA7 | em88 trial: chance 0.02 a tick, success requests state E01; held ticks take the failure 5DFFA7.
notyetb 5DFFAC notyet:5E0010 | em88 trial: chance 0.01 a tick, success requests state F01; held ticks take the failure 5E0010.
notyetb 5E0015 notyet:5E001F | em88 trial: chance 0.01 a tick, success requests state 1001; held ticks take the failure 5E001F.
notyetb 5E0024 notyet:5E0088 | em88 trial: chance 0.01 a tick, success requests state 1101; held ticks take the failure 5E0088.
notyetb 5E0095 notyet:5E0697 | em88 trial: chance 0.008 a tick, success requests state B01; held ticks take the failure 5E0697.
notyetb 5E00F7 notyet:5E0167 | em88 trial: chance 0.04 a tick, success requests state 501; held ticks take the failure 5E0167.
notyetb 5E016C notyet:5E01DA | em88 trial: chance 0.01 a tick, success store dword ptr [rbx + 0x3860], 0x438c0000; held ticks take the failure 5E01DA.
notyetb 5E01E7 notyet:5E0238 | em88 trial: chance 0.03 a tick, success requests state 1701; held ticks take the failure 5E0238.
notyetb 5E023D notyet:5E0697 | em88 trial: chance 0.04 a tick, success requests state 701; held ticks take the failure 5E0697.
notyetb 5E02D2 notyet:5E0314 | em88 trial: chance 0.015 a tick, success requests state 1201; held ticks take the failure 5E0314.
notyetb 5E0332 notyet:5E0382 | em88 trial: chance 0.007 a tick, success requests state 1301; held ticks take the failure 5E0382.
notyetb 5E0387 notyet:5E039B | em88 trial: chance 0.001 a tick, success calls action setter 5EAB80; held ticks take the failure 5E039B.
notyetb 5E03A0 notyet:5E0403 | em88 trial: chance 0.001 a tick, success requests state 901; held ticks take the failure 5E0403.
notyetb 5E0415 notyet:5E041E | em88 trial: chance 0.02 a tick, success requests state 501; held ticks take the failure 5E041E.
notyetb 5E0423 notyet:5E042C | em88 trial: chance 0.02 a tick, success requests state 601; held ticks take the failure 5E042C.
notyetb 5E0431 notyet:5E043A | em88 trial: chance 0.001 a tick, success store dword ptr [rbx + 0x3860], 0x438c0000; held ticks take the failure 5E043A.
notyetb 5E0447 notyet:5E0450 | em88 trial: chance 0.008 a tick, success requests state 1401; held ticks take the failure 5E0450.
notyetb 5E045D notyet:5E0466 | em88 trial: chance 0.005 a tick, success requests state B01; held ticks take the failure 5E0466.
notyetb 5E0473 notyet:5E047C | em88 trial: chance 0.003 a tick, success requests state D01; held ticks take the failure 5E047C.
notyetb 5E0481 notyet:5E048B | em88 trial: chance 0.01 a tick, success requests state 1201; held ticks take the failure 5E048B.
notyetb 5E04A5 notyet:5E04FC | em88 trial: chance 0.04 a tick, success requests state B01; held ticks take the failure 5E04FC.
notyetb 5E0501 notyet:5E0559 | em88 trial: chance 0.01 a tick, success requests state 1401; held ticks take the failure 5E0559.
notyetb 5E055E notyet:5E05D2 | em88 trial: chance 0.01 a tick, success store dword ptr [rbx + 0x3860], 0x438c0000; held ticks take the failure 5E05D2.
notyetb 5E05DF notyet:5E062F | em88 trial: chance 0.005 a tick, success requests state 1201; held ticks take the failure 5E062F.
notyetb 5E0490 notyet:5E0697 | em88 trial: chance 0.003 a tick (flags reach 5E0638 through a jmp), success requests state 1301; held ticks take the failure 5E0697.
notyet 5E0641 notyet:5E0697 | em88 trial 5E0634 (chance 0.01 a tick) shares its jbe 5E0638 with 5E0490's jmp, so no window fits the compare: between stock ticks its success path's first eligibility test (+E34 == 1, `cmp al, 1; jne`) reads "not equal" and goes to the join 5E0697 instead of requesting state 1301. 5E0490 is gated, so only this trial reaches 5E063A on those ticks.
# em60 update 2A8D20 (vtable 682650 slot 8): the near and far decision chains run every tick and end in the paced idle countdown +15D8; 68 trials, each failing between stock ticks.
notyetb 2A905B notyet:2A906B | em60 trial: chance 0.006 a tick, success store dword ptr [rbx + 0x1660], 0x1e; held ticks take the failure 2A906B.
notyetb 2A9079 notyet:2A9089 | em60 trial: chance 0.006 a tick, success store dword ptr [rbx + 0x1664], 0x1e; held ticks take the failure 2A9089.
notyetb 2A9457 notyet:2A9486 | em60 trial: chance 0.007 a tick, success requests state 1601; held ticks take the failure 2A9486.
notyetb 2A9494 notyet:2A94A6 | em60 trial: chance 0.002 a tick, success calls action setter 2B6030; held ticks take the failure 2A94A6.
notyetb 2A94B3 notyet:2A9669 | em60 trial: chance 0.001 a tick, success requests state A01; held ticks take the failure 2A9669.
notyetb 2A9677 notyet:2A96C7 | em60 trial: chance 0.01 a tick, success requests state B01; held ticks take the failure 2A96C7.
notyetb 2A96D5 notyet:2A9735 | em60 trial: chance 0.005 a tick, success requests state 1901; held ticks take the failure 2A9735.
notyetb 2A973A notyet:2A979A | em60 trial: chance 0.006 a tick, success requests state 1E01; held ticks take the failure 2A979A.
notyetb 2A97A7 notyet:2A97E7 | em60 trial: chance 0.009 a tick, success requests state E01; held ticks take the failure 2A97E7.
notyetb 2A97EC notyet:2A983D | em60 trial: chance 0.001 a tick, success requests state D01; held ticks take the failure 2A983D.
notyetb 2A9842 notyet:2A987E | em60 trial: chance 0.009 a tick, success calls action setter 2B57A0; held ticks take the failure 2A987E.
notyetb 2A9883 notyet:2A98C0 | em60 trial: chance 0.006 a tick, success calls action setter 2B5890; held ticks take the failure 2A98C0.
notyetb 2A98C5 notyet:2A98D1 | em60 trial: chance 0.001 a tick, success requests state 1301; held ticks take the failure 2A98D1.
notyetb 2A98E9 notyet:2A993A | em60 trial: chance 0.006 a tick, success calls action setter 2B5D80; held ticks take the failure 2A993A.
notyetb 2A9955 notyet:2A997A | em60 trial: chance 0.006 a tick, success calls action setter 2B5D80; held ticks take the failure 2A997A.
notyetb 2A9995 notyet:2A99AC | em60 trial: chance 0.001 a tick, success calls action setter 2B56E0; held ticks take the failure 2A99AC.
notyetb 2A99C9 notyet:2A9A09 | em60 trial: chance 0.018 a tick, success requests state E01; held ticks take the failure 2A9A09.
notyetb 2A9A1E notyet:2A9A28 | em60 trial: chance 0.002 a tick, success requests state 1301; held ticks take the failure 2A9A28.
notyetb 2A9A59 notyet:2A9A9A | em60 trial: chance 0.006 a tick, success requests state E01; held ticks take the failure 2A9A9A.
notyetb 2A9AB7 notyet:2A9AC0 | em60 trial: chance 0.015 a tick, success requests state 1301; held ticks take the failure 2A9AC0.
notyetb 2A9AD5 notyet:2A9AED | em60 trial: chance 0.01 a tick, success calls action setter 2B56E0; held ticks take the failure 2A9AED.
notyetb 2A9B02 notyet:2A9B42 | em60 trial: chance 0.015 a tick, success requests state E01; held ticks take the failure 2A9B42.
notyetb 2A9B84 notyet:2A9B97 | em60 trial: chance 0.012 a tick, success requests state 1301; held ticks take the failure 2A9B97.
notyetb 2A9BD9 notyet:2A9BE2 | em60 trial: chance 0.008 a tick, success requests state 1301; held ticks take the failure 2A9BE2.
notyetb 2A9BF7 notyet:2A9C38 | em60 trial: chance 0.005 a tick, success requests state D01; held ticks take the failure 2A9C38.
notyetb 2A9C4D notyet:2A9C6A | em60 trial: chance 0.005 a tick, success calls action setter 2B5D80; held ticks take the failure 2A9C6A.
notyetb 2A9C87 notyet:2A9CAA | em60 trial: chance 0.004 a tick, success calls action setter 2B5D80; held ticks take the failure 2A9CAA.
notyetb 2A9CBF notyet:2A9CEA | em60 trial: chance 0.005 a tick, success calls action setter 2B5D80; held ticks take the failure 2A9CEA.
notyetb 2A9D07 notyet:2A9D47 | em60 trial: chance 0.02 a tick, success requests state E01; held ticks take the failure 2A9D47.
notyetb 2A9D5C notyet:2A9D74 | em60 trial: chance 0.006 a tick, success calls action setter 2B56E0; held ticks take the failure 2A9D74.
notyetb 2A9DA9 notyet:2A9DEA | em60 trial: chance 0.006 a tick, success requests state E01; held ticks take the failure 2A9DEA.
notyetb 2A9E24 notyet:2A9E38 | em60 trial: chance 0.006 a tick, success calls action setter 2B5D80; held ticks take the failure 2A9E38.
notyetb 2A9E6C notyet:2A9E76 | em60 trial: chance 0.006 a tick, success calls action setter 2B5D80; held ticks take the failure 2A9E76.
notyetb 2A9E87 notyet:2A9ED9 | em60 trial: chance 0.008 a tick, success requests state B01; held ticks take the failure 2A9ED9.
notyetb 2A9EF3 notyet:2A9EFD | em60 trial: chance 0.006 a tick, success calls action setter 2B57A0; held ticks take the failure 2A9EFD.
notyetb 2A9F23 notyet:2A9F2C | em60 trial: chance 0.003 a tick, success calls action setter 2B5D80; held ticks take the failure 2A9F2C.
notyetb 2A9F4A notyet:2A9F53 | em60 trial: chance 0.003 a tick, success calls action setter 2B5D80; held ticks take the failure 2A9F53.
notyetb 2A9F71 notyet:2A9F7A | em60 trial: chance 0.003 a tick, success calls action setter 2B5D80; held ticks take the failure 2A9F7A.
notyetb 2A9F98 notyet:2A9FD8 | em60 trial: chance 0.015 a tick, success requests state E01; held ticks take the failure 2A9FD8.
notyetb 2A9FF6 notyet:2AA00E | em60 trial: chance 0.01 a tick, success calls action setter 2B56E0; held ticks take the failure 2AA00E.
notyetb 2AA04C notyet:2AA08C | em60 trial: chance 0.003 a tick, success requests state E01; held ticks take the failure 2AA08C.
notyetb 2AA0CD notyet:2AA0F8 | em60 trial: chance 0.003 a tick, success calls action setter 2B5D80; held ticks take the failure 2AA0F8.
notyetb 2AA139 notyet:2AA163 | em60 trial: chance 0.003 a tick, success calls action setter 2B5D80; held ticks take the failure 2AA163.
notyetb 2AA1A1 notyet:2AA1B8 | em60 trial: chance 0.003 a tick, success calls action setter 2B5600; held ticks take the failure 2AA1B8.
notyetb 2AA1F1 notyet:2AA208 | em60 trial: chance 0.003 a tick, success calls action setter 2B5600; held ticks take the failure 2AA208.
notyetb 2AA338 notyet:2AA37F | em60 trial: chance 0.012 a tick, success requests state B01; held ticks take the failure 2AA37F.
notyetb 2AA38D notyet:2AA3F0 | em60 trial: chance 0.015 a tick, success requests state 1601; held ticks take the failure 2AA3F0.
notyetb 2AA3F5 notyet:2AA3FF | em60 trial: chance 0.006 a tick, success requests state D01; held ticks take the failure 2AA3FF.
notyetb 2AA40C notyet:2AA423 | em60 trial: chance 0.014 a tick, success calls action setter 2B56E0; held ticks take the failure 2AA423.
notyetb 2AA430 notyet:2AA473 | em60 trial: chance 0.008 a tick, success calls action setter 2B5D80; held ticks take the failure 2AA473.
notyetb 2AA478 notyet:2AA48B | em60 trial: chance 0.008 a tick, success calls action setter 2B5D80; held ticks take the failure 2AA48B.
notyetb 2AA490 notyet:2AA499 | em60 trial: chance 0.012 a tick, success calls action setter 2B57A0; held ticks take the failure 2AA499.
notyetb 2AA49E notyet:2AA4A8 | em60 trial: chance 0.006 a tick, success calls action setter 2B5890; held ticks take the failure 2AA4A8.
notyetb 2AA4B5 notyet:2AA4CC | em60 trial: chance 0.002 a tick, success calls action setter 2B5600; held ticks take the failure 2AA4CC.
notyetb 2AA4D9 notyet:2AA4DE | em60 trial: chance 0.001 a tick, success requests state 1301; held ticks take the failure 2AA4DE.
notyetb 2AA4EF notyet:2AA507 | em60 trial: chance 0.015 a tick, success calls action setter 2B5600; held ticks take the failure 2AA507.
notyetb 2AA518 notyet:2AA51D | em60 trial: chance 0.002 a tick, success requests state 1301; held ticks take the failure 2AA51D.
notyetb 2AA53A notyet:2AA5AF | em60 trial: chance 0.029 a tick, success requests state 1301; held ticks take the failure 2AA5AF.
notyetb 2AA5C8 notyet:2AA5DF | em60 trial: chance 0.003 a tick, success calls action setter 2B5600; held ticks take the failure 2AA5DF.
notyetb 2AA5F0 notyet:2AA607 | em60 trial: chance 0.012 a tick, success calls action setter 2B56E0; held ticks take the failure 2AA607.
notyetb 2AA620 notyet:2AA656 | em60 trial: chance 0.004 a tick, success calls action setter 2B5D80; held ticks take the failure 2AA656.
notyetb 2AA673 notyet:2AA6A6 | em60 trial: chance 0.005 a tick, success calls action setter 2B5D80; held ticks take the failure 2AA6A6.
notyetb 2AA6B7 notyet:2AA720 | em60 trial: chance 0.004 a tick, success calls action setter 2B5D80; held ticks take the failure 2AA720.
notyetb 2AA739 notyet:2AA79A | em60 trial: chance 0.01 a tick, success requests state 1B01; held ticks take the failure 2AA79A.
notyetb 2AA7AF notyet:2AA815 | em60 trial: chance 0.004 a tick, success requests state B01; held ticks take the failure 2AA815.
notyetb 2AA833 notyet:2AA84A | em60 trial: chance 0.005 a tick, success calls action setter 2B5600; held ticks take the failure 2AA84A.
notyetb 2AA888 notyet:2AA89F | em60 trial: chance 0.005 a tick, success calls action setter 2B5600; held ticks take the failure 2AA89F.
notyetb 2AA8DC notyet:2AA8F3 | em60 trial: chance 0.005 a tick, success calls action setter 2B5600; held ticks take the failure 2AA8F3.
notyetb 2A93DE notyet:2A9426 | em60 trial: chance 0.5 a tick while the player is 30+ above in area 107 (B6B240), success requests state 1701 (after its eligibility tests and the 0.8 pick 2A940F inside it); held ticks take the failure 2A9426.
