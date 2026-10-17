# 2026-10-10: verdicts from tools/trace_steps.py's pass over every covered census
# site (open_unscaled_field_steps.txt's 319 among them): the ones a reading settled
# without a row, and the sites the rows of trace_steps01/02.spec fix.
follows | esp01.. 190DA0: the phase +1A0 wraps by 0x800 once past +-0x400 (cmp 190F0A); its step 190EFC is counted | 190F12
follows | esp01.. 190DA0: the phase +1A2 wraps by 0x800 once past +-0x400; its step 190FC1 is counted | 190FD7
follows | et07 2E25B0: the material's U wraps by -1 after its scaled step | 2E2741
follows | ut1d 532BC0: the material's U wraps by -1 after its lin-scaled step | 532C9D 532D13
follows | esp01.. 18FBD0: the countdown +26D reloads by its period +26C when it reaches 0; its decrement 18FBE0 is counted | 18FC28
follows | 315E60: the motion frame +F48 jumps back 12 frames once it reaches 50, a loop of the clip's last 12 frames | 315F97
follows | movie rumble PWM 4BD900: the phase, counted at 4BDA0A, wraps by 255 when it crosses | 4BDA21
follows | utd7 231200: +1628 counts down once per 60-tick cycle of +E3C (lea_timers.h paces it) while B6B240 is 0x208 | 231322
once | em00/em81 2469A0: state 0's turn by 2DDF90, its limit speed x pi (a snap), runs once before the state moves on; state 2's per-tick turn has callscale 246B93 | 246BEE
once | em03/em80 24E8E0: as 2469A0 (state 2's per-tick turn has callscale 24EAF3) | 24EB4E
once | em27/em29 2723C0: +E36 steps once after the state's setup | 2724A4
once | et2d 2E93A0: +E34 steps once with the motion's start | 2E9D90
once | hm3c 306E30: +E37 steps once each time the paced +E3C expires | 306F17
once | menu 439AD0: +29 steps once when +C reaches 64 | 439B1E
once | cKiType vt25 handlers: +E54 x -0.3, the bounce when the dropped thing lands | 36913F 209868 368897 369B1F
once | cKiType reaction 206A10 (from 363F90, a hit): +112C x -0.4 once per reaction, as 206A58 | 206A70
once | em2d 281AE0 sub-objects: x -0.95 and x 0.95, then x -0.84 and x 0.7, the bounce at ground contact | 2824C1 2824C6 2824F3 2824F8
once | objScroll 35C790 and 35D0E0: the bounce at the floor (x -0.2; +E42 counts the bounces) | 35C935 35D283
once | em4d 28D810: +E24 x 0.1 once, with the state's step (+E36 += 1) | 28D949
once | pl00 3B7320 and 3B9A70: +E48 x 0.1 once at a state change; the other paths' decays are decay_factors.h's | 3B83FD 3BB831
stock | em52 2994C0: +12B4 is set from the distance band every tick, then x4 in mode 3: a fresh value, not an accumulation | 2996A6
fixed | pl00 3B2CF0: the jog's speed update v x (1 - c v) and its blend toward the target read kJogParams (dinput8_proxy.cpp) | 3B31A6 3B3241
fixed | ut9a 229A20: both blends' factors (0.2, 0.05) are blend rows; the trace splits only because each path loads +D2C itself | 229BA2
fixed | em85 5CBAD0: the 0.995 path's factor is srcroot 5CBC58, the 0.99 path's decay_factors.h 5CBD05, both pushes lin rows | 5CBD25
fixed | em89 5F2A60: the push is a lin row on every band and mode (5F2AAD..5F2C1F) | 5F2C58
fixed | pl00 3C13F0: the 8-degree turn limit, lin 3C180C | 3C183C
fixed | pl00 3CAE60: the lift's rise step, pre 3CAFBA | 3CAFBF
fixed | em65 2C0A60: the motion-factor clock +16BC, pre 2C1AC2 | 2C1ACE
fixed | em2d 281AE0: the second and third adds of the speed under slow time, src 282757 and 282765 | 282760 28276E
fixed | camera 468420: pitch += velocity, pre 46849E | 4684AE
fixed | cSubScrFilesInfoMess: the panel's slide step, dst 41F615 and 420359 | 41F626 42036A
fixed | ut23 4F0CD0: the spin's integration, src 4F0ED0 and 4F10AB | 4F0EDF 4F10BB
fixed | utb6 56F760: the distance's fall, src 56FBDF | 56FBEB
fixed | cMcAction 1C5870: the slide, src 1C594E | 1C5962
fixed | cMcAction 1C4FA0: the scale's growth, src 1C5023 | 1C5032
fixed | cCockGameOver 3FCF50: +68's step, lin 3FCF6E | 3FCF7E
fixed | wp5f 3A2530: the speed's gain, lin 3A25DE | 3A25F6
fixed | wp12 38CB60 and 38CF10: the spin, lin 38CC76 and 38D140 | 38CC8F 38D159
fixed | wp47 39B950: the hit point's distance step, lin 39BA74 | 39BA8E
fixed | em4d 28D810: the speed's x1.2 growth, srcroot 28D9CF | 28D9DE
fixed | em89 5F08E0 and 5F1750: the volley count and its test, count and notyet | 5F0A01 5F1871
fixed | 3D77B0: the wipe's alpha, count on its store | 3D782B
fixed | camera 47A3A0: srcroot 47AE31 on the 0.85 and pre 47AE44 on the integration | 47AE5C
left | 4ABE10 (from 30D250): a hop every 10..25 ticks (a random reload of +E3C, counted down unpaced) that moves by the root-motion vector +E10..+E18 copied to +EC0 (+E18 from -1 by phase_steps' 0.1 x s); it wants the countdown paced and the copied vector scaled | 4ABF27
left | wp47 39BB10: with +10E5 set, +B4 gains rand x 30 degrees and +E54 loses rand x 3 a tick: a random draw per tick, with the RNG backlog | 39BD5E
once | espEmitter 1950D0: +19C gains 0.99 once per reload of the emission countdown, while its slow-motion flag (134 bit 25) holds | 195256
stock | Dormant debris 3809D0-3822D0 (no call, jump or code pointer enters it; the live copy is 3822D0/382340): a joint's +C4 falls 0.6 a tick there | 381C79 38224A
stock | Dormant debris 393F50-395850 (no call, jump or code pointer enters it; a copy of the live loop 3822D0/382340): a joint's +C4 falls 0.6 a tick there | 3951F9 3957CA
