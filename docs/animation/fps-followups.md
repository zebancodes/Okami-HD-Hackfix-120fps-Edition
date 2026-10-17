# FPS follow-up audit, 2026-10-07

Five passes against Steam build 6990973, main.dll SHA1
`703d292ab2cb50cc9e237e44722dec51d956b79c`. This extends the self-update
census. The forward-mover queue is fully classified; the other new queues
remain open.

1. **Walk animation: fixed offline.** `3B27D9` loads `+E48` into `xmm0`,
   divides it by 1.1 and stores `+F54`, with a 0.5 floor. The existing
   jog/run/dash animation table loaded `xmm1` and omitted walk. The table now
   records each load's original bytes and derives its register from that
   audited load. Its existing `FixAnimRate` and movement A/B controls recover
   stock-unit speed before the divide. The floor and stored movement speed
   are unchanged. `verify_player_anim_rates.py` checks the real DLL installs,
   eight switch states and 224 directed cases around each floor and divisor.
   Both `--break walk` and `--break reg` reproduce the bug and fail.

2. **Random rolls: inventory and 36 confirmed trials fixed offline.**
   There are 948 direct calls to integer RNG `1BD480`, 510 to signed float
   RNG `1BD590`, and another 824 to the unsigned float wrapper `1BD580`.
   The latter is especially relevant to `rand < probability` checks. The
   third pass also identifies 272 calls to 32-bit RNG wrapper `1BD6D0`
   (a tail jump to `1BC5B0`) and 14 to ranged-float helper `1BD620`.
   The inventory follows `rax` for both integer generators and `xmm0` for
   the float generators. This remains an inventory of these five entry points,
   not a proof that every random source or indirect call has been found.
   `random_rolls.csv` records all 2,568 sites and 738 register-derived branch
   candidates. A bounded straight-line slice follows the returned register
   until a branch, call, return or loss of the value. It does not prove
   frequency and does not follow values stored and reloaded through memory.
   The 1,830 `other_use` rows also require semantic review.

   In `em16`'s update `264280`, type `216` has a distance/heading-dependent
   chain of six 0.003 trials and two 0.001 trials on each tick. The compares
   `264945` through `264A8D` now take their unsuccessful paths between stock
   ticks. All eight are paced together, so falling through one roll cannot
   fire another unpaced roll. The update continues to run every tick. The
   `notyetb` proof now accepts `comiss`/`ucomiss` as well as integer compares,
   checks its one flag-consuming branch, and proves flags dead on both paths.
   RNG calls still run; the selected branches are what the gates pace.
   `verify_chance_rolls.py` runs the entire chain with controlled draws:
   every winning trial, all failures, equality at the cutoffs and all winning
   draws, across every residue at N=1/2/4 (77 cases). Removing one gate fails.

   Reviewed exclusions illustrate why candidates need reading: `2F1093`
   and `2F10B1` choose variants once in an object reset; `299892` and
   `29A608` draw only on integer animation-frame crossings. The rolls behind
   motion-completion calls require checking whether the motion loops or
   remains finished before deciding they are events or per-tick waits.
   The third pass adds nine trials in the other `264280` paths: two near
   trials requesting state `501`, four far type-216 trials requesting `1401`,
   `D01` or one of two `301` jump vectors, a low-health-target trial requesting
   `1701`, and two other-type trials requesting `1401`. Timer-expiration picks
   after the already-scaled `+1CF8` countdown retain their existing cadence.

   The same pass adds nine trials in `em85` update `5C6450` and ten in `em89`
   update `5EC0F0`, seven in phase 0 and three in phase 1. These decision paths
   retry each tick without an upstream entry gate. Each complete chain now
   takes its unsuccessful paths between stock ticks, preserving stock
   probabilities, trial priority and eligibility checks. Their remaining
   update paths still run every tick.

   Independent caller tracing also corrects two inherited counter rows:
   `5CD6DE` and `5CD7AE` increment `em85`'s shared `+3490` once per selected
   attack attempt, not once per tick. Helpers `5CD690` and `5CD760` each have
   one caller, behind the newly paced 0.1 selection trials. Their fourth
   accepted attempt sets `+348C=100` and clears `+3490`; both increments now
   retain stock behavior. The existing elapsed cooldown decrement `5C6DC0`
   remains paced. The helpers' internal health-dependent rolls also remain
   per-attempt checks.

   `verify_chance_decisions.py` runs the seven added chains in 343 directed
   cases, checking selected states, payload helpers, jump vectors, callback
   clears, flags and RNG short-circuit order. It executes `26B0A0`'s real
   eligibility checks and the two real attempt helpers. Another 105 helper
   calls test same-helper and alternating-helper attempts on every frame
   phase, the fourth-attempt reset and active cooldown rejection. Removing
   one comparison gate in each enemy family causes eight failures; injecting
   the old event-counter gates causes 60. These are instruction-level tests;
   external vector operations and selected attack payloads are emulated.

   Reviewed exclusions also cover animal action starts in `1D5DD0` and
   `1E11B0`, a `+1170` timeout reload and the one-time setup roll `233B99`.
   `1E11CF` consumes a rate draw every tick but applies it only on action
   starts. `5EC238` remains explicitly unresolved: its 0.98 trial selects
   between phase resets and a continuous timer path, so pacing that compare
   alone would change more than an action's frequency. The roll ledger
   records this distinction instead of treating it as a confirmed chance fix.

3. **Forward mover `2DA410`: all 129 direct sites reviewed.** Initially 40
   had a patch on the call. The first pass added five `callscale` rows:
   `an00` action `1D72B0`'s constant hop (`1D743E`), random movement
   (`1D74C8`) and two moves using stock-unit `+E48` (`1D75AD`, `1D77B7`);
   and `ut2c` state 6's 15-unit step (`57CBA1`) throughout an already-paced
   `+E3C` countdown. The animal's two velocity decays are already converted
   at `1D75BA` and `1D77C4` in `decay_factors.h`. Stored speeds stay in their
   existing units. `2A441B`/`2A4441` and `2A7FFB`/`2A8021` are covered by
   their upstream literal loads; `39FD4D` applies a one-off setup offset.
   The second pass traced all remaining 79 sites through their argument
   initialization and action dispatch. It adds 64 distance conversions:
   46 animal calls, three enemy calls and 15 weapon calls. Their literal,
   random or retained distances still have stock units even when the action
   timers or speed decays are already converted. The new rows scale the
   distance at the call, preserving stored speeds and thresholds.

   Seven compose a converted decay with a newly scaled movement:
   `28D7AA`, `291277` (`+E18`), and `38724E`, `3885FB`, `3888C9`, `38B7C0`,
   `38CC28` (`+E28`). Their speeds originate from stock constants or picks,
   and each active tick stores the decayed speed before applying it. The
   converted decay establishes retention over time; the new call conversion
   establishes the distance per tick. The main flight branches also needed
   individual review: some already multiply by scaled slow-motion dt while
   others still pass the stock speed directly.

   Final classification: **109 calls patched directly, 12 scaled upstream,
   four one-off placements and four player calls already in current-tick
   units**. The latter are `3C22F8`, `3C288A`, `3C56D8` and `3C5E95`. Their
   inherited or dt-derived `+E48`, including the existing scaled caps at
   `3C5428`/`3C5439` and `3C591B`/`3C592C`, must reach the mover unchanged.
   The upstream case `5E399D` is covered by the derived `step 5E3982` row,
   not a handwritten manifest entry. A global hook on `2DA410` would apply
   the conversion twice or shrink setup placements.

   `verify_forward_movers.py` composes the seven load/decay/store/call blocks
   with the real forward helper, using native DLL decay slots, across all
   residues at N=1/2/4. Only its two vector/matrix imports are emulated. It
   also executes three one-off and four current-unit calls unchanged. This
   tests retained units and applied distance, not exact trajectory identity
   between continuous damping and stock discrete integration. Removing a
   selected conversion or injecting a second scale into the helper must fail.

4. **Other speed fields: 963 scalar stores inventoried; 18 reviewed.**
   `motion_field_sets.csv` inventories `mov`/`movss` stores to `+E10`, `+E18`,
   `+E48`, `+1080`, `+10E8` and `+EC8`, recording immediate values and the
   nearest straight-line register producer. Of these, 271 are immediate
   stores, including zeros and non-motion uses of the same offsets. This is
   a scalar-store inventory, not a complete vector or cross-function source
   analysis. In particular, enemy `+1080` is normally a rate multiplier in
   stock units; its integrations often already have a scaled speed read.
   No blanket scaling of these fields is selected.

   The mover audit traced six `+E18` stores: `25A3E1`, `28D6E7`, `28D7A2`,
   `2911A4`, `29126F` and `39B801`. These deliberately retain stock-unit
   speed, including the two post-decay stores tested with the real mover.
   Their distance applications now have individual call conversions. The
   third pass reviews another 12 stores. Six in `em8f` action `2D90E0`
   initialize or retain the stock-unit `+E10/+E18` velocity. The position
   adds `2D9192`/`2D92E2` are already scaled, and four `countlast` multipliers
   preserve the alternating -0.4 decay once per stock tick. Storage should
   not be scaled again. In `24EB80`, `24EC89` initializes `+E10=8` as a
   vector origin, and `24EF42` retains that origin after the already-converted
   sweep step `24EF3E`; these are spatial offsets, not movement speeds.
   Four more matching offsets in `12EFE0` belong to a local constant table:
   `rbp` is explicitly derived from `rsp` in its prologue. This confirms that
   the inventory also contains stack data with numerically matching offsets.
   The other 945 stores remain queued; these reviews do not classify other
   uses of the same offsets.

5. **Counters limited by another field: 53 starter candidates reviewed.**
   `field_limit_counters.csv` collects integer candidates whose p-code facts
   contain `ordered=field`. This is a starting list, not a new complete timer
   census. It does not find counters absent from the earlier self-update
   census, limits reached through another function or comparisons with an
   expression. The starter list contains 21 already-fixed counters, ten
   event counts, one count following a scaled angle wrap and 21 stock
   bookkeeping or sample-index operations. No additional timer fix was
   selected from this list. Existing reviews are carried into the durable
   follow-up ledger with their evidence; previously unreviewed entries were
   checked through their function and caller paths.

   Examples matter here: `3A3DD0` and `3A5326` traverse brush samples recorded
   once per current tick, while `2512B4`, `26D868` and `2D6170` count attacks.
   The weapon `+1C60` rows search/allocate slots inside one invocation;
   `50F7A5` advances a tutorial stage only at the seven event-driven calls
   in `512530`, `5129B0`, `512D00` and `513010`. The real field-limited particle
   lifetimes, grow-in counters, dash and resource meters already have exact
   increment/store gates or verified upstream call gates. A broader search
   for counters absent from the earlier census is still needed.

6. **Early landing and cherry bomb: still pending.** The nine early-landing
   look-aheads remain unchanged. A third-pass read confirms the inherited
   addresses against the original instructions: `206209` (`206000`),
   `2753D5` (`275280`), `277D3B` (`2779A0`), `28CBEA` (`28CB20`),
   `29FF74` (`29FDD0`), `2A0523` (`2A0400`), `384F33` (`384E30`),
   `386757` (`3866C0`) and `389AFC` (`389A30`). They add position Y to a
   register loaded from `+E54`, compare the anticipated height with `+E50`
   and trigger a ground snap or landing state. `28CBEA` reaches its comparison
   through a shared jump, after an earlier velocity-dependent phase test;
   any conversion must affect the anticipated-height calculation only.
   Movement provenance and directed landing-boundary tests are still needed
   before selecting those conversions. Cherry-bomb identification and behavior
   still need the in-game evidence described in the existing playtest notes.
   This pass has no in-game validation.

Regenerate the five inventories with `tools/survey_fps_followups.py`.
`followup_reviews.csv` is the durable source for reviewed decisions; the
generator rejects duplicates and stale review addresses. Coverage columns
report exact instruction overlap and whole-function entry gates, never
nearby patches. See `misc_reading/fps_followups01.spec`,
`misc_reading/fps_followups02.spec`,
`misc_reading/fps_followups03.spec` and
`world_anims.csv` for the selected rows and their generated proofs.

The new normal verifiers and their fault injections are part of
`tools/run_suite.sh`. The existing world verifier also checks every new
window and call against the original at N=1/2/4.

First-pass validation: the clang build and all 44 offline suite expectations
passed with seed 62 and 64 states in the normal world verifier. The suite report is
`.suite-fps-followups-20261006-seed62/summary.txt`; it records the tested DLL's
SHA1. The patch audit found no mismatched original bytes, overlapping patch
ranges or switch destinations entering a detour. In-game validation remains
pending.

Second-pass validation, completed 2026-10-07: the clang build and all 47
offline suite expectations passed with seed 63. The report is
`.suite-fps-followups-20261006-seed63/summary.txt`; the tested DLL SHA1 is
`685532c70de9afc73aedb6ed507f277f74774c45`. The normal world verifier ran
482,112 window cases and 22,704 call cases with zero problems. The composed
forward-mover check passed 294 directed cases and 3,675 movement steps;
removing a conversion produced 12 failures, and a second helper scale
produced 168, including 84 at deliberately preserved callers. The patch
audit checked 6,428 sites with no original-byte mismatches, overlapping
ranges or switch destinations inside a detour. In-game validation remains
pending.

Third-pass validation, 2026-10-07: the clang build and all 52 offline suite
expectations passed with seed 64. The report is
`.suite-fps-followups-20261007-seed64/summary.txt`; the tested DLL SHA1 is
`3a2ef9aaa668c7ddc0b698f497b04f639782c324`. The normal world verifier ran
487,104 window cases and 22,704 call cases with zero problems. The new
decision verifier passed 343 chain cases and 105 attempt calls; its four
fault injections failed as required. The patch audit checked 6,454 sites,
903 switch tables and 9,341 destinations, with no original-byte mismatches,
overlapping ranges or switch destinations inside a detour. The subsequent
RNG inventory expansion and regeneration did not change the tested DLL.
In-game validation remains pending; this pass has not deployed the build.

The coverage report now also recognizes deliberate event-counter restorations:
each must have a `stock` review and an exact `event_counters.NOT_PACED`
instruction within the census candidate's original load .. store. This accounts
for 35 earlier restored candidates without loosening checks on unexplained
lost coverage.

Next random-roll investigation, read-only during third-pass validation:

- `em65` update `2C0A60` is vtable `682FA8` slot 8. It has an action-selection
  region `2C0CB6 .. 2C197B` containing 80 calls to `1BD580` and only eight
  other callees: `2C9FD0`, `2CA190`, `2CA100`, `2C9B20`, `2C99B0`, `2C9E70`,
  `2C9D90`, `2C9A70`. Each is an action setter whose direct callers are this
  update; their eligibility and internal random checks are per selected
  attempt. The preceding `+1714` countdown and turn at `2C0C7B .. 2C0CB1`
  lie outside the region, and action dispatch, motion advance and continuous
  timers follow its join. A single stock-tick gate before `2C0CB6`, with a
  skipped path to `2C197B`, is a promising smaller alternative to dozens of
  comparison gates. It still needs a production encoder, register/stack
  liveness proof and composed tests through the continuous update. Skipping
  the region would also skip its RNG calls, unlike the selected branch gates
  above; that stream-consumption difference must be considered explicitly.
- The bounded RNG slice finds 77 branch candidates here and marks three calls
  `other_use`: `2C0D22` supplies multiple distance-dependent comparisons,
  `2C151F` initializes a selected wait and `2C15F7` carries comparison flags
  through a jump to `2C183C`. This is a concrete reason the branch-candidate
  queue alone cannot be treated as the whole random-roll audit.
- `em60` update `2A8D20` is vtable `682650` slot 8. Its larger decision region
  also contains `+1660/+1664/+1668` waits, the field-derived `+166C` wait,
  and a turn toward its target. A single broad gate must not suppress these
  already-converted continuous operations. Helper `2B4770` checks idle-state
  eligibility, including a substate-D phase threshold, rather than waiting
  for motion completion. Its rolls therefore cannot be dismissed as motion
  events merely because action setters use that helper. This update still
  needs its subregions traced and tested before selecting more rows.

These next-pass findings do not select additional patches or close the
remaining random-roll queue: 2,484 of the 2,568 inventoried sites still have
`pending` reviews, and `5EC238` has the separate unresolved `mixed_guard` review.

Fourth pass, 2026-10-07: per-tick decision chains and animation-frame events.

7. **Per-tick decision chains: em65, em88 and em60 (186 rows).** A new
   reading tool, `tools/chance_trials.py`, follows every draw through
   registers, stack spills, branches and switch tables to each compare it
   decides, and plans gates. A compare is gated when its rare side (at most
   25% likely) does something and its common side, with every other gated
   compare on its common side, does nothing until the branch's
   post-dominator or a join. One draw read by two compares on a path is a pick,
   and a tail jump counts as a call. Trials nested in another trial's success, below
   a store of the actor's state bytes (an action's start) or below an integer
   frame crossing are left alone. The planner reproduces the earlier passes'
   hand-made em16 and em89 gates exactly.

   `em65` update `2C0A60` runs 84 trials (0.3% to 15%) every tick once its
   paced `+1714` pause is spent; `em88` update `5DF660` runs 33 (0.1% to 20%)
   once its paced `+3878` cooldown is spent; `em60` update `2A8D20` runs 69
   (0.1% to 50%) in its near and far chains, which end in the paced idle
   countdown `+15D8`.
   Each success requests an attack state or calls an action setter, so at
   120 these enemies chose an action about four times as often. Each compare
   now reads "below" (`notyetb`) between stock ticks. Two compares share a
   branch that a `jmp` from another compare reaches, so no window fits them:
   `2C1839`'s action setter is skipped between stock ticks by a void call
   gate at `2C1847`, and `5E0634`'s success path is sent to the join by a
   `notyet` on its first eligibility test (`5E0641`). The `notyetb` proof now
   follows an unconditional `jmp` between a compare and its branch.

   `tools/verify_chance_chains.py` runs each chain on the original and the
   patched code with random object states, path selectors and draws, every
   call trapped and answered the same way in both runs. At N = 1 the runs
   must match the original exactly. At N = 2 and 4 the reference is the
   patched image with only the chain's own gate rows put back (other rows in
   the region, such as em60's countdown, stay converted): stock ticks match
   it with the same draws, other ticks match it with every gated draw losing.
   It passes 8,400 runs; 147 of the 184 gates in the regions are exercised
   by a winning draw on a held tick. `--break gate` removes the most
   exercised gate of each chain and fails.

   Reviewed and left as they are: the imp family's 1-in-4 voices and picks
   (16 sites, each below the action's sub-state store), em16, em60 and em88
   action picks drawn when an animation ends or at an integer frame crossing
   (every outcome acts at once), em65's material phase jitter `2C05E0`, and
   13 animal rolls drawn when an animation ends, and 15 animal 1-in-2 or
   1-in-4 rolls a tick that stop a walk within 20 of its target (a fraction of
   a stock tick sooner at 120). The motion-end rolls depend on the
   motion data: a looping motion reports its end one tick per loop, where a
   stock-tick gate would drop three of four rolls; a non-looping motion
   reports it every tick after, where the roll would want pacing. Left
   ungated, a non-looping idle pose can end sooner.

8. **Animation-frame events (39 rows).** The shared motion advance steps
   a model's frame (`+F48`) by 1 a stock tick and by 1/N a tick at N times
   the rate; several classes keep frames of their own stepped the same way
   (`+1534`, `+16B8`, `+3854`, `+4FA8`, `+2434`, em2d's per-part `+C`). A
   test such as `(int)frame == 18` therefore holds one tick of a stock pass
   and N ticks at N x. Most event code guards with a crossing
   (`(int)frame != (int)last`), but 43 unguarded equality windows start
   something one-shot: footstep effects (an00), attack sounds and effects
   (the imp family, em02, em2d, em60, em65, em81, em88, em89), em62's
   projectile volleys at frames 25/35/45/55 (five objects each), em69's
   object spawns, em89's child motion start, vt18's camera shake and sound,
   and three objects' sounds (ut12, ut1e, et67). At 120 each started four
   times. Each equality compare now reads "not equal" between stock ticks
   (`notyet`, 39 rows): the window holds N ticks, exactly one of them a stock
   tick. Four are right as they are: a scripted task whose loop `task_waits.h`
   already paces, and three ranges that run the hit test `2DD1A0`, whose
   effect starts only on a hit the target refuses to repeat (`+E76`).
   `tools/frame_events.py` lists the windows; `--check` (in the suite) fails
   on an unguarded one-shot window with neither a row nor a review. The hit
   tests (`2DC7B0`, `2DD1A0`) in such windows are deduplicated by the
   target's `+E76`; the float windows that spawn objects check a "spawned"
   flag (`+10C1`) first.

9. **Counter events (31 rows).** The same N-tick hold applies to an integer
   counter that a pacing family (memory, action or lea timers, integer skips,
   a world_anims count row) steps on stock ticks only: `counter == K`,
   `counter % N == 0` and `(counter & mask) == 0` hold N ticks at N x. Most
   such events already had `notyet` rows; 31 one-shot ones did not, among
   them the player's sounds at `+E3E` = 80/98 and 95/111 and effects every 8
   or 16 counts (pl00 `3AFA90`, `3A4480`, `3BDCB0`, `3C96A0`; the same state's
   `0x6F`/`0x8E` sounds were rowed before), a countdown's beeps at 90/60/30
   and a tick every 30 counts (utf6 `236A50`), objects' periodic sounds
   every 25, 30 or 90 counts (ut3b, ut32, ut4a, cEnemyObj), effects and
   sounds of ese0, gtfe, et69, utf0, uta5 and em89, and motion starts in
   cDogLikeHm and ut2b. Each test now reads "not equal" (or nonzero) between
   stock ticks. `tools/frame_events.py` finds them (kinds `counter`,
   `modulo` and `bits`, on the census's paced counter fields of the same
   function, a function under a whole-function or call gate counting as
   guarded); reviewed as right: one that sets and checks its own done flag
   (`2F5640`), two alternating jitters (`364DF0`, `36CC50`). The hit tests
   are not counted as one-shot.

Fourth-pass validation, 2026-10-07: the clang build and all 55 offline suite
expectations passed with seed 87 (`.suite-20261007-b/summary.txt`, tested DLL
SHA1 `5ba29bd7c039307befe7951df06ef682e9e76150`). The normal world verifier
ran 529,536 window cases and 22,752 call cases with zero problems; each new
window also fails its `--break gate` run alone. The decision-chain verifier
passed 8,400 runs and its fault injection failed as required, and the frame
event check reports 43 unguarded one-shot windows: 39 rowed, 4 reviewed. The
em65 and em60 regions listed under "Next random-roll investigation" are now
gated compare by compare, not with a single region gate. The random-roll
queue has 2,139 of 2,568 draws pending (217 patched, 99 once, 78 event, 21
stock, 14 mixed). In-game validation remains pending.

Counter-event validation, recovered 2026-10-08 from the completed reports:
all 55 offline suite expectations passed with seed 88
(`.suite-20261007-c/summary.txt`, tested DLL SHA1
`b961f5d609f905928cfd0c70edb106b8795cf8a0`) after the first 26 counter and
modulo rows. Its normal world verifier ran 534,336 window cases and 22,752
call cases with zero problems, and the patch audit checked 6,701 sites.
After the five bit-test rows, all 55 expectations passed again with seed 89
(`.suite-20261007-d/summary.txt`, tested DLL SHA1
`236a5c96d16d7251e0b60bcb87341d02e7aa3fa0`). The normal world verifier ran
535,296 window cases and 22,752 call cases with zero problems. The patch
audit checked 6,706 sites, 903 switch tables and 9,341 destinations, with
no original-byte mismatches, overlapping ranges or switch destinations
inside a detour. The frame-event survey reports 91 unguarded one-shot
windows: 86 rowed, five reviewed and zero open. Both suites include the
normal checks and required fault-injection failures.

At recovery, the built DLL matches the seed-89 report, but the game-folder
DLL and the existing release zip still contain the earlier `5ba29bd7`
build. The counter-event build has not been deployed or packaged, and
in-game validation remains pending.

Fifth pass, 2026-10-08: heading movers and vector displacements.

10. **Heading mover `2DA460`: 25 direct sites inventoried.**
    `heading_movers.csv` extends the mover survey to the helper that accepts
    both a distance and a heading. Four newly selected `callscale` rows
    convert signed direction bytes multiplied by stock-valued distances:
    `37F0DF` (`wp00`, `+10F4` times 3.5), `3870B3` (`wp09`, `+111C` times
    6.5), `38A0B8` (`wp0f`, `+10F4` times 3.5) and `39AD9F` (`wp47`,
    `+10E4` times 3.5). They move every tick while already-paced action waits
    run. Only the applied distance changes; the retained direction bytes,
    headings and waits keep their existing meanings.

    With the three earlier rows at `383D1F`, `383EA6` and `39DE7A`, seven
    calls are converted directly. Seventeen other calls already take
    current-tick distances: 14 from `pl00` and three from `ut35`. The player
    paths inherit `+E48` from corrected movement or initialize it with a
    scaled seed, and their acceleration, blends and damping already account
    for the active rate. The `ut35` accelerations already use the second
    time-scale factor against corrected mode-table damping. Scaling these
    calls again would shrink their movement a second time.

    `389AC8` (`wp0e` action `389A30`) remains unresolved. It moves by retained
    `+E18` in heading `+E14` and then applies the already-converted 0.9
    decay. Its local setup, singleton setters, generic spawn and constructor
    paths, including vector construction at `+E10`, do not establish a
    nonzero initializer or the movement fields' units. No distance conversion
    is selected for this call. This leaves the inventory at seven directly
    patched calls, 17 current-unit exclusions and one unresolved call.

    An independent continuous step in the same `wp0e` action is confirmed:
    its unsigned random draw is multiplied by the degrees-to-radians factor
    and 16, added to `+B0`, wrapped and stored at `389AC0` on every update,
    after the initialization block. The literal at `389A98` now scales the
    angular increment. This does not establish the retained `+E18` units or
    select a new distance conversion there. RNG calls remain per tick;
    directed checks establish increment scaling and wrapping, not identical
    stochastic paths at different frame rates.

11. **Vector mover `2DA3F0`: three selected displacement conversions.**
    `em60` helper `2A8630` has one caller, `2AD82E`, in airborne state 6.
    It applies retained stock-unit velocity `+1590` through two vector
    products and the mover. A `dst` row at the speed read `2A863A`, proved
    through `2A8650`, converts the applied displacement while preserving
    the stored velocity and motion factor `+F54`. Gravity at `2AD83B` is
    already converted and keeps its existing cadence. A static reference
    check finds the one direct call and ordinary unwind metadata, with no
    export, function-pointer, vtable or RIP address-taking references.

    `wp0f` action `38A8F0` initializes its outbound vector as `(0,0,10,1)`
    and applies it every tick during the paced first-flight wait. The literal
    load `38A973` now converts the distance 10. Its homing phase rebuilds
    the vector each tick from normalized owner displacement; `38AA0D`
    converts the distance 4 after normalization. Target geometry, retained
    heading and the homogeneous vector component keep their existing units.

    `verify_heading_movers.py` and `verify_vector_movers.py` compose selected
    caller blocks with the real helpers, preserving representative
    current-unit callers. Their normal checks and `--break missing` and
    `--break double` fault injections join the offline suite, together with
    the heading check's `--break spin`, bringing it to 62 expectations.
    These directed checks complement the whole-world
    verifier's installed-byte and register-preservation checks.

    Remaining vector candidates include `em8f` action `2D9460`'s transient
    sinusoidal X/Z stores at `2D97BC`, `2D97EB` and `2D980E`, and `uta4`
    look-alikes at `560A46` and `561996`. They need an appropriate encoder,
    provenance proof and directed checks before a conversion is selected.
    No blanket scale is placed in either shared movement helper.

Fifth-pass validation, 2026-10-08: the clang build and all 62 offline suite
expectations passed with seed 90 (`.suite-20261008-a/summary.txt`, 967 s).
The tested DLL SHA1 is `561cdf2b7e9df2d75aa808e4de156ba14e94bc9d`. The
normal world verifier ran 535,488 window cases and 22,944 call cases with
zero problems. The heading check passed 1,176 directed cases and 9,436
movement/producer steps; its missing, double and spin faults produced 384,
648 and 108 failures respectively. The vector check passed 133 cases and
6,356 movement/gravity steps; its missing and double faults each produced
66 failures, including the current-unit control under the extra helper
scale. The patch audit checked 6,714 sites, 903 switch tables and 9,341
destinations, with no byte mismatches, overlaps or interior switch entries.
The original self-update census remains 12,485 settled, zero near or left;
the separate follow-up queues remain open. In-game validation remains pending.

Sixth pass, 2026-10-09: every caller of the vector mover.

12. **Vector mover `2DA3F0`: all 59 direct calls reviewed.**
    `vector_movers.csv` (from `tools/survey_fps_followups.py`, verdicts in
    `followup_reviews.csv`): 42 `existing` (34 enemy moves converted at
    their speed read or vector constants by find_actor_motion's rows, 8
    weapon moves by `+E10` times the slow-motion dt their `dst ("slowmo")`
    rows scale), 7 `patched` (em60 and wp0f of the fifth pass, and the five
    below), 4 `current_units` (pl00's root-motion step `+EC0`, rewritten
    every tick by the motion advance, and `+E48`) and 6 `unresolved_units`.

    The hovering bobbers: em8f `2D9460`, uta4 `5607A0`, utb6 `56F330` and
    utb7 `570640` keep a degree phase `+E40` that gains 1 a tick, taken
    `% 360` into the hover target and a sway vector applied by 2DA3F0 every
    tick. Their usual branch's phase store was never paced (the census
    filed it as state, "stepped with a sibling reset"); a scan of every
    `% 360` degree phase finds exactly these four. They now have `count`
    rows (2D96AB, 560932, 56F4A2, 570749), and the sway they apply is
    scaled: `lin` on uta4's, utb6's and utb7's constants (560A25, 56F546,
    5707ED), and for em8f, whose usual branch stores `sin()` with no
    constant, the new kind `callvec` (37) on 2D9819: the call's stub hands
    2DA3F0 a copy of the vector with xyz times s and w unchanged, so `+E10`
    and `+E18` keep stock values. uta4's forward surge `5616C0` (`+E18 =
    0.4 x (sin(6 x phase deg) + 1)` a tick, its phase already paced) went N
    times as far; `lin` 561974 and 561986.

    `verify_vector_movers.py` runs each bobber's real phase and sway code
    tick by tick against the original code at N = 1, 2, 4 and every
    residue: the phase steps once a stock period, N ticks apart; the stored
    vector is the original's (em8f) or s times it; the mover receives
    exactly s times the original's vector. The whole-world verifier checks
    the callvec stub itself (registers but rdx and xmm4, a counter-area
    slot holding (s x, s y, s z, w) bit for bit, the caller's vector and
    game memory untouched).

    Unresolved: em86 `5D15E0` and `5D1E28` and em89 `5F2DC1` move by a
    distance-keeping term (em86: `(distance - 220) x 0.09` a tick along the
    heading), an exponential approach that wants a blend root on its
    factor, which two imported vector products split; em86 `5D237F` and
    `5D3970` and em87 `5DAC62` move by speed fields (`+544C`, `+535C`) with
    their own per-tick acceleration, decay and caps, whose units and
    conversions need reading first.

Sixth-pass validation, 2026-10-09: the clang build and all 62 offline suite
expectations passed with seed 91 (`.suite-20261009-a/summary.txt`, 927 s).
The tested DLL SHA1 is `8ba754687871fc4ed099e5e58707d3285dad0cc4`. The
normal world verifier ran 536,256 window cases and 22,992 call cases with
zero problems; each new window fails `--break gate` alone and the callvec
fails `--break scale` alone. The vector check passed 301 directed cases and
7,868 steps; `--break missing` and `--break double` each fail all 144 bobber
cases at N > 1 (210 failures in all). The patch audit checked 6,724 sites
with no byte mismatches, and 903 switch tables with no destination inside a
detour. In-game validation remains pending.

Seventh pass, 2026-10-09 (later): coverage on the update's own path.

13. **Coverage's 8-byte rule, tightened.** `coverage_report.py` counted a
    candidate covered when any patched range of its function lay within 8
    bytes of its load .. store. It now requires an instruction of the range
    on the update's own path (load to store; into the load or out of the
    store in the 8 bytes around). 30 candidates had been covered only
    through another branch's patch: reading them gave 14 gaps (one-direction
    fades and blends, the motion blend's extra step, the emitters' slow-motion
    countdown, et0f's spin and turn, four countdowns with em2b's volley index
    made an event counter, the money display's count-up) and 3 verdicts. The
    same rule also hid steps of an update beside a patched one: every
    unscaled literal, immediate and inc/dec step on such a path was read (10
    more gaps, et71's position += velocity among them). The field- and
    register-sourced ones (319) and the decay_factors.h velocities whose
    integration is unscaled (31 sites) are listed, not read:
    `misc_reading/open_unscaled_field_steps.txt`,
    `misc_reading/open_decay_integration.txt`.
14. **The "sibling reset" counters (248).** Read: 142 sub-state bytes, 106
    screen states, event counts and indexes; only the four bob phases (the
    sixth pass) were clocks.
15. **The bosses' moves.** callvec on em86 5D237F/5D3970, em87 5DAC62 and
    em89 5F2DC1; blend 5D1599 for em86's distance keeping; the dash's push
    (lin 5D22FC) and two 0.986 decays (countlast). `vector_movers.csv`: 59
    calls, 12 patched, 42 existing, 4 current units, 1 unresolved (em86
    5D1E28, a factor up to 1.2).

Seventh-pass validation, 2026-10-09: the clang build and all 62 offline
suite expectations passed with seed 92 on the off-path batch
(`.suite-20261009-b`, DLL SHA1 `5c4ea196`) and seed 93 on everything
(`.suite-20261009-c/summary.txt`, 898 s). The tested DLL SHA1 is
`6cb501d72b492d5e85458157b02c9ef0c93569de`. The normal world verifier ran
539,136 window cases and 23,232 call cases with zero problems; the callvec
check requires the mover to receive a copy holding x, y and z times s with w
unchanged, and the caller's vector and game memory untouched. The vector
check passed 301 directed cases and 7,868 steps. The patch audit checked
6,761 sites with no byte mismatches, and 903 switch tables with no
destination inside a detour. In-game validation remains pending.

Eighth pass, 2026-10-10: step sources.

16. **`tools/trace_steps.py`.** The seventh pass listed 319 covered updates
    whose unscaled step adds a field or a register, found by a 24-instruction
    linear look-back. The tracer slices each store's value back through the
    function's control flow (switch tables, stack slots by frame offset,
    cVec calls that write a slot, out-pointers passed on the stack), splits
    it at the store's own field into steps, and counts a step converted only
    when every path of it passes a conversion: a patch on its own
    instructions (a world window converts only its row's instruction), the
    port's time scale, a mode-selected constant, a kJogParams global,
    2DA510's FixTurnRate, a clamp helper whose limit is converted. A guarded
    add of a period, the bound or twice it is a wrap; a gatefn, a paced task
    wait or gated callers pace a whole function. `--field` lists a field's
    writers in its classes, `--uses` every store that adds it.
17. **The 319 (277 stores):** 251 converted on their own path (the look-back
    took the update's own field for its step), 6 wraps, 2 the jog; 8 gaps.
18. **Every covered site (4,318):** 3,976 converted, 160 census-excluded
    state; the rest read (65 verdicts, `misc_reading/trace_reads01.spec`):
    bounces, sub-state steps, wraps, dormant debris, and about 20 gaps,
    fixed by 29 rows (`misc_reading/trace_steps01.spec`): a turn limit, a
    lift's rise, a motion-factor clock, slow-time speed adds, boss pushes,
    volleys and a decay, a x1.2 speed growth, weapon spins, an acceleration
    and a hit sweep, two integrations beside scaled velocity ramps, the
    camera's tilt, the Files screen's panel slide, a menu's slide and zoom,
    the game-over screen and a wipe's fade.
19. **The 31 decay integrations:** mostly the velocity's own push, not its
    integration; the per-tick player speeds by design; wp1b/wp1c keep
    current-tick velocities; cBallObj's and wp1a's integrations are rows;
    esf1's is a collision probe; two dormant copies. One gap, the camera
    mode 47A3A0 (unrooted 0.85 and unscaled integration): srcroot + pre,
    as the other camera modes.
20. **em86's close-in (5D1810):** blend on its 0.12 (5D1DDD), exact at a
    factor of 0.12; where stock's factor reaches 1 it snaps or overshoots,
    which no per-tick factor reproduces, and the row approaches smoothly.
21. **The port's sites:** `--check` also traces the 39 sites the census
    left to the port. Four falls (cDogLikeHm 484D40, et99, utc9, utcf)
    scale their gravity by the time scale, keeping the velocity in stock
    units, but add all of it to the position every tick: `pre` on each add
    (`misc_reading/trace_steps03.spec`). The rest are bounces, a one-shot
    impulse, a dormant camera and mode-table factors.
22. **`--check` in the suite:** every covered or port site whose step is
    not converted needs a reading or a census exclusion (4,352 pass);
    `--break rows` fails on 1,102.
23. **Left:** 4ABE10's hop (an unpaced random interval and a copied
    root-motion vector) and wp47's per-tick random scatter (RNG backlog).
24. **4ABE10's hop, done:** a villager's (cHuman's state 30D250 drives its
    sub-object; with the villager's +11E8 bit 14 the sub-object's root
    motion +EC0 moves the villager, 3046D0 then 20E960). The hop copies its
    push +E10, in stock units, into +EC0 every tick; at 120 the countdown
    ran 4x and each reload restarted the push, about 9x the distance. Rows
    (`misc_reading/trace_steps04.spec`): lin 4ABECB (the push at a tick's
    share), count 4ABF08 and 4ABF12 (its ramp and clamp once a stock
    period, before the period's copies), countlast 4ABF27 (+E3C's store,
    where reload and countdown meet; `countlast` now takes an integer
    counter's store). Its sibling 4AB570's push: lin 4AB63B and ulast
    4AB67E (the 0.8 to ScaleXYZ on each period's last tick). Both exact
    tick for tick in a model of the code.
25. **wp47's scatter is not per tick:** 39BB10 draws in its start block
    (+E36 == 0), once per throw (reads.csv 39BD5E `once`). The same block's
    one-off turn toward the target (2DDF90, up to 30 degrees) had a steer
    callscale, as had em4d/em4e/em50's leap turn (28D951, up to 90 degrees x
    speed): at 120 they turned a quarter of the way. `tools/once_blocks.py`
    (reached only while a phase byte has one value, which every path then
    changes) makes survey_turn_steps leave both as `once`; no other world
    row sits in such a block (pl00 3B725B's immstore sets a per-tick speed
    once, which is right).
26. **The random-roll queue, done (2026-10-10, night):** every one of
    random_rolls.csv's 2,568 draws has a review (`tools/roll_reads.py`,
    verdicts `misc_reading/roll_reads00..07.spec`): once 1,500, event 626,
    patched 252, stock 136, dead 31, mixed_guard 23. New rows
    (`misc_reading/roll_rows01.spec`, 20): the motion key windows 4B9770
    (src 4B9964/4B9B06: keyed sounds, dust, voices and a shake held 2 ticks
    at 60 and 4 at 120) and pl00's footstep dust (dst 3B2F86/3B349A/3B37EC);
    esp19's lens flare (notyetneg 1A5FCA, lin 1A5F88/1A5A2F); the battle
    list's reinforcement wait 9C4760 (count 23EF8A/23F0E7, notyet
    23EF90/23F0ED); hm8e's flicker (count 333869); per-tick chances in
    491BD0 (notyetb 491DCD) and ut1d (notyet 532C00/532D96 on its draws'
    mask tests, `test m, r`, now accepted); exact cadence
    for an0c/an03/the animals' head look and em65's specials (203248,
    1DC570, 205C24, notyetb 2C6A5B). The verdict specs have the readings.

Ninth pass, 2026-10-11: the open list.

27. **Early landings, done.** The nine look-aheads of item 6 are `pre` rows:
    each object's fall moves y by s x vy a tick (anff 202A30's pre 202B25,
    20EA30 with a step or callscale row on its time factor), so `y + vy`
    looked a stock tick ahead. `y + s x vy` looks a tick ahead; the sum
    feeds only the compare on every path, and 28CBEA's velocity phase test
    runs before it, unchanged (`misc_reading/fps_followups08.spec`).
28. **The unread turns, done.** Five weapon limits were already converted
    by their slow-motion dt's dst rows (survey_turn_steps now counts a world
    window on a limit's slice as `patched`); em02 24DB65 is a one-off aim;
    uta8 564FFE had its row; em0f 25A401 and em2b 2766F5 turn by a
    stock-unit field a tick: callscale.
29. **wp0e, done.** The imps' dropped weapon: the knockback (242060,
    249F83) sets +E18 = -6 along the imp's heading, +E54 = 6; 389A30 moves by
    +E18 a tick and keeps it x 0.9 (decay_factors.h): callscale 389AC8.
    heading_movers.csv: 8 converted, 17 current-unit, none unresolved.
30. **Rolls at an animation's end (the mixed_guard draws), done.** New kinds
    `notyetend` (38: the advance's `test al, al`, or a draw's test just
    below it, reads "not ended"/"not yet" between stock ticks unless the
    object's motion loops, [R + F38] byte 7 bit 0) and `callend` (40: the
    draw's call answers eax = -1 then, where a join leaves no window).
    em60 2B2BA0's draws are events (every outcome acts); an1e 1FCD3F is a
    per-tick chance near its target: notyet on its wait's test.
31. **em89's 0.98, done.** New kind `hold` (39): the compare is decided on
    the stock tick and its flags kept for the period (a per-site slot;
    em89 is a boss).
32. **The chains, done.** esp10 1A20A0 and esp31 1AA210 integrate a spring
    chain once a tick: pushes x s, damping k^s, p += s x v, esp10's
    relaxation 1 - (1 - r)^s (`fps_followups09.spec`, 13 rows).
33. **Stale list entries.** The draw-time tints and esp35's +1D0 are set for
    one draw and restored (reads.csv); wp20's model 0x624 was converted on
    2026-10-02.
34. **The fps byte's waits.** The player's lock-on retarget delay +1144 had
    a count row on top of the port's doubling (twice its stock time at 60
    and 120): the count row is gone and its three stores are byte
    mulstores. The player's half-second sound (`fc % (fps / 2)`): new kind
    `divn` (41), the divisor x N, kept after the div
    (`fps_followups10.spec`). Open: the five quake lengths (no reader of
    B663C8..D8 found in main.dll's code) and the three "count / fps"
    seconds reads (their count is a script object's +40, whose increments
    are not found yet).
35. **Countdowns that ended early, done** (`tools/early_countdowns.py`,
    `fps_followups11.spec`, 131 rows). A paced countdown holds each value
    for N ticks, so a zero test that runs before the decrement, or reads the
    decremented register or its flags after a count row on the store, saw
    0 a stock tick early, by up to 3 ticks at 120; a countdown reloaded
    there ran each cycle a stock tick short (R for R + 1). Only transient
    zeros are gated (the zero side re-arms the field or changes the state on
    every path): 187 countdowns that rest at 0 (a hit lock's unlocked path)
    and 68 register shapes like them are left, as are 8 tests behind a
    motion's end (an event edge: once a loop of a looping motion). `notyet`
    (43 rows) for a count row's countdown, new kind `notyett` (42, 88 rows)
    for the timer families': its mask is theirs, mirrored into the group's
    [8g + 3] each tick while the group is on, so it stands down when they
    are off. notyet also takes a decrement (`sub`, `add`, `dec`) as its flag
    source. Two system counters of integer_skips.h are reviewed and left;
    `--check` is in the suite.
36. **Counters the census never saw, sized.** A scan of every read-modify-
    write of non-stack memory and every load / step / store of one address
    finds about 300 sites outside sites.csv (132 and 174, overlapping);
    many are library or set-up code. Not read yet.

Ninth-pass validation, 2026-10-11: the clang build and all 65 offline suite
expectations passed with seed 99 (`.suite-20261011-a/summary.txt`, 1,048 s).
The tested DLL SHA1 is `060fe5e853f9942c8fd41d951ab1695e2ca46b5e`. The
normal world verifier ran 579,456 window cases and 23,376 call cases with
zero problems; each new window and call fails alone with its conversion
broken (`--break scale`, `root`, `gate` or `intn`). The heading check passed
1,176 directed cases and the vector check 301. The patch audit checked 6,989
sites with no byte mismatches, and 903 switch tables with no destination
inside a detour. In-game validation remains pending.

Tenth pass, 2026-10-11: the three remaining investigations.

37. **Counters outside the census, reviewed.** `tools/find_uncensused.py`
    resolves RIP-relative addresses and follows load / step / same-address
    stores for six instructions without crossing a control transfer. Its
    conservative scan finds 302 candidates outside the census: 211 library
    or setup, 70 event counts, nine already handled, three current-tick by
    design, and nine new clocks. Every verdict has evidence in `REVIEWED`;
    `--check`, now in the suite, rejects missing reviews and clocks without
    rows. New counts: brush idle gap `16E978`; UV phases `22BFE6`, `3368C3`,
    `5A7B36`; material flipbooks `273778`, `2D8D97`; emitter phase `2284C5`;
    stage sound delays `4C5C2D`, `4C5FE1`. Compare gates `22848B`, `4C5C33`,
    `4C5FE7` prevent repeated effects or sounds on held ticks. Brush points,
    button presses and animation loops remain events. The brush gap's
    nonpositive side only sets an idempotent flag, so it receives no gate.
38. **Quake duration, reader found.** `B663D8` is camera `B661E0+1F8`.
    `47603A` reads it, `476076` decrements it and `476081` stores it;
    `4832AC` consumes it for the visible shake. Existing objects gate
    `476030` already paces both quake blocks together. Constant writers are
    correct. Five FPS-derived initializers (`364CBE`, `370026`, `3703FF`,
    `3C1DE8`, `3C5FE6`) instead supplied 30 stock ticks rather than 15:
    twice the duration at both 60 and 120, where the FPS byte remains 60.
    New `stockfps` reads supply 30 while the matching camera gate is active,
    retaining the original byte when that group is off. The shared mode
    table's quake retention remains a separate follow-up: it can make
    amplitude fade too slowly, and also has player/object consumers.
39. **Count / FPS seconds, incrementer found.** The manager returns plain
    0x50-byte pool records, not objects with vtables. Their `+40` resets at
    `23C94F` and increments at `23D789`, already paced by the actor family.
    The three readers use manager slots 2, 3 and 1. `stockfps` rows at
    `4B1FE2`, `4FBD8B`, `538422` supply divisor 30 while actor pacing is
    active, correcting reported seconds and result thresholds that used
    half the elapsed gameplay time at 60/120. Mask zero preserves the
    original byte and flags. `4B1DC1` is an independent task pause.

`fps_followups12.spec` archives all 20 rows: nine counts, three compare
gates, eight `stockfps` reads (new kind 43). The generator ties each FPS
correction to the same group's existing counter or camera gate and proves
the straight-line division or reciprocal/multiply/store arithmetic.
Evidence: [census review](misc_reading/uncensused12.md),
[quake reader](misc_reading/quake_reader12.md), and
[script seconds](misc_reading/script_seconds12.md).

Tenth-pass validation, 2026-10-11: clang/Ninja built the stabilized header,
and all 66 suite expectations passed with seed 100
(`.suite-20261011-c/summary.txt`, 1,063 s). The tested DLL SHA1 is
`d074cd6c352e5bf92c0ad34ba1fdc97ef1e67683`. All 20 new windows separately
passed 64-state checks at N=1/2/4 (3,840 cases), and each failed independently
under `--break gate`. The full world verifier completed 583,296 window
cases and 23,376 call cases with zero problems. The patch audit checked
7,009 sites without byte mismatches or overlapping ranges, and 903 switch
tables without a destination inside a detour. Coverage remains 12,485 of
12,485 settled. In-game validation remains pending, including pause/options
entry and exit during a quake: the writers use gameplay units, but static
analysis has not excluded every writer from every stock-60 menu path.

Eleventh pass, 2026-10-11: quake fade and stock context.

40. **Quake retention, corrected locally.** Five indexed loads
    (`364CB5`, `37001C`, `3703F5`, `3C1E03`, `3C5FE1`) feed only camera
    retention `B663D0`. At 120 the mode table can supply a fourth-root
    factor, although camera gate `476030` applies it at stock cadence,
    making the shake fade too slowly. New `stockpair` kind 44 uses the
    exact shipped pair (`3F64F95D` / `3F4CCCCD`) selected by live shadow
    mode while that gate is active. The shared table's six other consumers
    retain their behavior. A zero mask keeps the original load, and an
    unknown live mode keeps its result. This also works with mode-table
    rewriting off; squaring its current value would not.
41. **Quake duration context, completed.** The five `stockfps` rows now
    use the tick's captured stock FPS: 30 in gameplay, 60 in stock-60
    contexts, matching the camera gate's N and the engine's earlier FPS
    sampling. Retention originally selects mode later, so it uses live
    context instead. Existing quakes keep their stored factor through
    later mode/rate changes. Pause/options stop bits exclude all five
    writers and the reader during ordinary menu operation; save/title/movie
    reachability remains bounded rather than assumed. The correction
    handles either stock context without needing that exclusion.

`fps_followups13.spec` adds five retention rows and replaces the five
gameplay-only duration rows. The generator proves each local indexed load
and sole store, preserves flags and borrowed RAX, and uses immutable pair
bytes. Evidence and search boundaries:
[quake retention and context](misc_reading/quake_retention13.md).

Eleventh-pass validation, 2026-10-11: clang/Ninja built the stabilized header,
and all 69 suite expectations passed with seed 101
(`.suite-20261011-d/summary.txt`, 1,103 s). The tested DLL SHA1 is
`2be402905848df22c3d260f7fa21499dec926051`. Each of the ten affected windows
passed separately at 64 states and N=1/2/4 (1,920 cases), and each failed
alone under `--break gate`. The directed quake check passed 240 initializer
cases and 2,400 camera updates, and caught both altered retention bits and
reversed duration context. The full world verifier completed 584,256 window
cases and 23,376 call cases with zero problems. The patch audit checked
7,014 sites with no byte mismatches or overlaps and 903 switch tables with
no destination inside a detour. Coverage remains 12,485 of 12,485 settled.
In-game fade, duration and pause/resume checks remain pending.

Twelfth pass, 2026-10-12: the first play of 1.0.2.

42. **Smoke puffs piling up in an arena battle.** In play at 60 and 120, the
    cartoon smoke when a battle's enemies appear kept coming and piled up over
    them; at 30 it went away, and it came back on switching to 60 or 120. That
    is the shape of a "not yet" gate on a countdown that rests at 0: between
    stock ticks the test reads "not yet" and the active side runs on N - 1 of
    every N ticks, forever. Item 35's rule took a zero side that stores the
    actor's state bytes (+E34..+E37) as proof that the zero is passing, but
    the test can run again with the field at 0 (a handler outside any switch
    on them, a state that comes back, the same state stored). The rule now
    requires every path of the zero side to re-arm the field with a nonzero
    value: an immediate, or a register set from one on that path (a call
    clears the volatile registers). 101 of item 35's 131 rows fail it and are
    removed (among them the shared enemy handlers 209240..209330 and the effect
    actors et10, et41..et43, et68, et6b, et92); 30 stay. Those 101 tests run
    as in 1.0.1 again (their zero side up to 25 ms early at 120).
    `--check` now also fails on any `notyet`, `notyetneg`, `notyetb` or
    `notyett` row on a countdown that rests at 0; 67 older rows it flags are
    listed as read (63 from before item 35, all in 1.0.1, move a state
    machine on through a dispatch the rule does not follow; four reload from
    a draw or test an equality).
43. **The brush with a controller stays in the middle.** The cursor step is
    16C7E0's `previous + 0.095 x stick x xmm9` (the four `src` rows of 1.0.2
    scale xmm9), with the stick from B6B142 clamped by B6B12C; the pad code
    writes both through a base pointer and no patch touches it. Nothing found
    so far zeroes the step; an in-game check at 30 is next.

Twelfth-pass validation, 2026-10-12: all 69 offline suite expectations passed
with seed 102 (`.suite-20261012-a/summary.txt`, 1,425 s). The tested DLL SHA1
is `3cc19e12d934e0b40a3d98181b0e7bc3928ae19c`. The world verifier ran
565,824 window cases and 23,376 call cases with zero problems; the countdown
check reports no open test and no "not yet" row on a resting countdown. The
patch audit checked 6,918 sites with no byte mismatches and 903 switch
tables with no destination inside a detour. Coverage remains 12,485 of
12,485 settled. The arena smoke and the controller brush need the next play
session.

Thirteenth pass, 2026-10-15: the second play of 1.0.2. The arena smoke is
gone at 120; the controller brush moves at 30 and stays in the middle at 60
and 120, so it is the patch.

44. **The controller brush (item 43), found.** The step was never zero: it
    is dropped later. Once 16C7E0 has moved the cursor, it measures the move
    (7E71C4, 7E71C8 = this tick's position - the last) and drops it when its
    squared length is under 16, or under 64 when it turns back toward the
    previous point: the cursor goes back to its last kept point 799360, so
    small steps never add up (16DC4C..16DCE5; while the mouse moves, both
    limits are 0.1). The stick term is the larger of B6B142 x 1.65 and
    B6B12C, so full tilt is 12 a tick from B6B12C and 20 from B6B142. Scaled
    to a quarter at 120 that is 3 and 5: every move from the first was
    dropped, and from the second below 80% tilt (at 60, below 66% and 40%;
    stock drops them below 33% and 20%). New kind `limsq` (45) loads each
    limit and multiplies it by s twice (16DB50, 16DB59), so a step of s
    times stock's is kept exactly when stock's would be. It is a detour, not
    an `sq` literal, because the loads use xmm12 and xmm13 (a REX prefix, 9
    bytes). Its proof follows every path from the load to the register's
    rewrite (xmm13 lives to the epilogue's restore, over 2,000 instructions)
    and requires each named compare's other side to be a sum of two squares
    made on a straight line before it. The mouse's 0.1 stays: its moves are
    not scaled. The direction the game derives from the move (7E71CC,
    7E71D0) is never read.
45. **The cursor's pull toward a target.** With the stick and the mouse
    still, a cursor within 50 of something the brush can act on is drawn to
    it by min(8, 3000 / d^2) a tick and put on it inside 5 (16FBF3..16FC84);
    the next tick takes cursor + pull as the cursor. It ran every tick, four
    times as fast at 120. Two `lin` rows scale the 3000 and the cap (16FC15,
    16FC21); xmm1 is read only by the cap's minss and the pull's length only
    by its copy into cVec * float, on every path.
46. **The rest of the brush's kind.** `tools/step_limits.py` reads every
    comiss/ucomiss and minss/maxss in a function the patch scales a value
    in: 3,490 in 962 functions. Each side is sliced backward (trace_steps'
    slicer) and written as a polynomial in s over its leaves, with s where
    each row or family puts it. A global the function stored earlier on the
    way reads as the stored value, so 16C7E0's x - prev cancels to the step;
    cVec::squareMag and GetLength sum their lanes' squares, and a `mov dword
    [m], imm32` is read as a float's bits. A test is flagged when one side
    of a pairing has every term at s^k (k != 0) and the other is nonzero and
    free of s. With the limsq rows read unscaled it flags 16DC73 and 16DCA7
    (s^2 x 0.095^2 x stick^2 against 16 and 64). As built it flags 57 tests,
    none a bug:
    - 40 turn clamps: the angle left to turn, limited to +- the most a tick
      turns times s (20E210, 20E290, 5BC850, 5C22D0, and eight classes'
      copies of one helper at 26B920, 2836F0, 2B5250, 2C9300, 5CCD90,
      5DD910, 5EA280, 5F4730). That is the per-frame step of the approach.
    - 10 tests of pl00's +E48, a per-frame speed. Earlier rows put their
      limits in the same units (srcx, or a lin limit such as 3B210A's 0.05).
      Also 3B46B8, the port's test of +E18 (a saved +E48) against 5 x the
      time scale.
    - em2d's step tests (27E7A4 srcx, 27E9CC and 27EA64 against 10 x s from
      lin 27E9C4), and cDogLikeHm's heading snap (4874D0: the step 0.1 x s is
      also the snap's bound).
    - The brush's two, now paired only with the mouse. With the mouse at
      rest, the cursor glides onto the pointer by an unpaced 0.7 blend
      (7E7204) whose steps are not scaled, so at 120 it settles within 1
      instead of 4 and records a point or two more; 0.1 is the mouse's limit
      while it moves.
    `--check` is in the suite: a flagged test or pairing not in REVIEWED,
    or an entry no longer flagged, fails it; `--break limsq` must fail.
    Three one-time reads found nothing to change. A move derived from a
    position's history (x - prev, prev a copy the game takes) tested against
    a constant anywhere in the image: 21 of 9,090 float tests, all a heading
    stored once, the stroke's straightness ratio, gatefn'd functions or
    vector math. A scaled step truncated to an integer: none of 391
    conversions. Such a move stored in a field and tested elsewhere: 28
    fields, the brush's or blends toward a target, none tested against a
    limit.

Thirteenth-pass validation, 2026-10-15: both `limsq` windows passed 144
directed runs (24 states, N=1/2/4) with zero problems, and with s forced to
1 (`--break scale`) every run at N=2 and N=4 failed (96 of 144). With the
limits alone, all 69 suite expectations passed with seed 103
(`.suite-20261015-a/summary.txt`, 1,257 s). With the pull too, all 69
passed with seed 104 (`.suite-20261015-b/summary.txt`, 1,178 s); the tested
DLL SHA1 is `6452f99f44fe8df1e27597bb6d03003a4c2edd92`. With the
step-limits check and its `--break limsq` run added, all 71 passed with
seed 105 (`.suite-20261015-c/summary.txt`, 1,198 s) on the same DLL. In
each, the world verifier ran 566,208 window cases and 23,376 call cases
with zero problems; the
countdown check reports no open test and no "not yet" row on a resting
countdown; the patch audit checked 6,922 sites with no byte mismatches and
903 switch tables with no destination inside a detour. Coverage remains
12,485 of 12,485 settled. The controller brush needs the next play session.
