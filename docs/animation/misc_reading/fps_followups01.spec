# First follow-up pass, 2026-10-06: per-tick chance chain and forward movers.
group actor
notyetb 264945 notyet:26498D | em16 update 264280, type 216: while in its distance/heading decision path, trial 1 has probability 0.003 each tick and may enter state 1401. All eight trials in this chain now take the unsuccessful path between stock ticks; the update and motion continue every tick.
notyetb 264992 notyet:2649B8 | em16 type 216 decision chain, trial 2 (0.003): failure goes to the next roll; success requests state D01. Paced together with the other seven trials.
notyetb 2649BD notyet:2649E3 | em16 type 216 decision chain, trial 3 (0.003): failure goes to the next roll; success requests state 1601. Paced together with the other seven trials.
notyetb 2649E8 notyet:264A0E | em16 type 216 decision chain, trial 4 (0.003): failure goes to the next roll; success requests state 901. Paced together with the other seven trials.
notyetb 264A13 notyet:264A39 | em16 type 216 decision chain, trial 5 (0.003): failure goes to the next roll; success requests state A01. Paced together with the other seven trials.
notyetb 264A3E notyet:264A64 | em16 type 216 decision chain, trial 6 (0.003): failure goes to the next roll; success requests state B01. Paced together with the other seven trials.
notyetb 264A71 notyet:264A88 | em16 type 216 decision chain, trial 7 (0.001): failure goes to the last roll; success sets a jump vector and requests state 301. Paced together with the other seven trials.
notyetb 264A8D notyet:264B4C | em16 type 216 decision chain, trial 8 (0.001): failure leaves the decision path without changing state; success sets the alternate jump vector and requests state 301. Every trial fails between stock ticks.
group objects
callscale 1D743E | an00 slot-26 action 1D72B0, substate 2/1: moves forward by the constant -2 every tick during the hop. No time scale feeds the argument, and the caller is not gated: scale only this displacement by s.
callscale 1D74C8 | an00 slot-26 action, substate 2/3: moves by a freshly drawn negative random displacement (rand x 0.3 x 15) every tick while its motion plays. Scale the applied step, keep the stored animation rate and random draw unchanged.
callscale 1D75AD | an00 slot-26 action, substate 2/5: when +E3E <= 0 moves by stock-unit +E48 before its separate decay and reload. Scale the call argument; keep the stored velocity and its thresholds in stock units.
callscale 1D77B7 | an00 slot-26 action, substate 1/1: the other +E3E <= 0 movement by stock-unit +E48, before its decay and reload. Scale the call argument, as 1D75AD.
callscale 57CBA1 | ut2c state 6 in 57CA00: moves forward by the constant 15 every tick while its +E3C countdown (already paced by action_timers.h) runs. The call receives no time scale: s of 15 restores the distance over the stock-length window.
