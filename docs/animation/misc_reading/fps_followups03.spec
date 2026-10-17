# Third follow-up pass, 2026-10-07: repeated enemy decision trials.
group actor
notyetb 264B04 notyet:264B09 | em16 update 264280, near decision path: trial 1 (0.012) may request state 501. Fail between stock ticks; the next trial is paced as well.
notyetb 264B16 notyet:264B4C | em16 near decision path: trial 2 (0.05) may request state 501. Failure joins the continuous countdown at 264B4C.
notyetb 264D3D notyet:264D46 | em16 far type-216 decision path: trial 1 (0.012) may request state 1401. Pace all four trials in this chain.
notyetb 264D53 notyet:264D79 | em16 far type-216 decision path: trial 2 (0.003) may request state D01.
notyetb 264D86 notyet:264D9D | em16 far type-216 decision path: trial 3 (0.008) may request state 301 with jump vector (0,3,6.5,1).
notyetb 264DA2 notyet:264F95 | em16 far type-216 decision path: trial 4 (0.008) may request state 301 with jump vector (0,4,5,1). Failure joins the continuous countdown at 264F95.
notyetb 264F29 notyet:264F95 | em16 other-type decision path: a low-health target permits a 0.5 per-tick trial requesting state 1701. This is distinct from the elapsed +1CEC wait that can also enter 1701.
notyetb 264F40 notyet:264F45 | em16 other-type decision path: trial 1 (0.01) may request state 1401. The second trial is paced together with it.
notyetb 264F52 notyet:264F95 | em16 other-type decision path: trial 2 (0.05) may request state 1401 if rsi is nonzero. Preserve eligibility checks and the continuous countdown after failure.
notyetb 5C66DC notyet:5C673E | em85 update 5C6450: repeated trial 1 (0.007), distance and idle-state checks then state A01. All nine trials fail between stock ticks.
notyetb 5C674B notyet:5C67AD | em85 decision chain: trial 2 (0.012), distance and idle-state checks then state B01.
notyetb 5C67BA notyet:5C67CD | em85 decision chain: trial 3 (0.04), distance check then vector attack helper 5CD430.
notyetb 5C67D2 notyet:5C67E6 | em85 decision chain: trial 4 (0.1) selects helper 5CD690 once. Its +3490 increment counts attempts, not time, and must remain stock.
notyetb 5C67EB notyet:5C67FF | em85 decision chain: trial 5 (0.1) selects helper 5CD760 once. Its +3490 increment also counts attempts and remains stock.
notyetb 5C680C notyet:5C6866 | em85 decision chain: trial 6 (0.008), idle-state checks then state C01.
notyetb 5C686B notyet:5C687C | em85 decision chain: trial 7 (0.1) selects helper 5CD1F0 once.
notyetb 5C6881 notyet:5C68BF | em85 decision chain: trial 8 (0.1) selects vector attack helper 5CD430 once.
notyetb 5C68CC notyet:5C68E0 | em85 decision chain: trial 9 (0.5), distance check then helper 5CD610. Failure joins the remaining update at 5C68E0.
notyetb 5EC3E3 notyet:5EC3F7 | em89 update 5EC0F0, phase-0 decision chain: trial 1 (0.009) selects helper 5F4F50. All seven trials fail between stock ticks.
notyetb 5EC404 notyet:5EC477 | em89 phase-0 chain: trial 2 (0.003), idle-state checks then state 901.
notyetb 5EC484 notyet:5EC498 | em89 phase-0 chain: trial 3 (0.004) selects helper 5F4ED0.
notyetb 5EC49D notyet:5EC510 | em89 phase-0 chain: trial 4 (0.005), idle-state checks then state 1001.
notyetb 5EC515 notyet:5EC588 | em89 phase-0 chain: trial 5 (0.005), idle-state checks then state F01.
notyetb 5EC595 notyet:5EC5FD | em89 phase-0 chain: trial 6 (0.0055), idle-state checks then state 1101.
notyetb 5EC602 notyet:5EC65F | em89 phase-0 chain: trial 7 (0.005), idle-state checks then state 1201. Failure joins phase bookkeeping at 5EC65F.
notyetb 5EC6B4 notyet:5EC72B | em89 phase-1 decision chain: trial 1 (0.005), idle-state checks then state C01. All three trials fail between stock ticks.
notyetb 5EC730 notyet:5EC78F | em89 phase-1 chain: trial 2 (0.005), idle-state checks then state D01.
notyetb 5EC794 notyet:5EC7A3 | em89 phase-1 chain: trial 3 (0.005) selects helper 5F4C90. Failure joins the remaining update at 5EC7A3.
