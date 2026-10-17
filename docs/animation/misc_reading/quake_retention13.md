# Camera quake retention and stock context, 2026-10-11

This closes the retention and menu-context follow-ups from
`quake_reader12.md`. Addresses are module RVAs. Evidence is static analysis
and offline instruction emulation; no in-game validation is claimed.

## Artifact and search boundary

The installed `main.dll` and the running Ghidra bridge input have SHA1
`703d292ab2cb50cc9e237e44722dec51d956b79c`, image base `180000000`.
Read-only Ghidra decompilation/xrefs and the cached Capstone instruction
stream were used together. No binary replacement or game launch was needed.

The shipped retention pair is indexed by `mode - 1`:

| RVA | Exact bits | Value |
| --- | --- | --- |
| `7A81E8` | `3F64F95D` | 0.8944299817085266 |
| `7A81EC` | `3F4CCCCD` | 0.800000011920929 |

The fast value is the shipped rounded value, not a newly computed square
root. `updateModeConstants()` rewrites only E8 to the fourth root of the
stock factor at 120 while enabled. At 60, stock mode or movement mute, it
restores the exact shipped fast value. With `FixModeConstants=0` the table
is also shipped. Squaring the current table value would therefore depend
on unrelated switches and would not reliably restore stock units.

Ghidra has 15 references to E8: eleven indexed loads and four LEAs
(`36FFFB`, `3703D4`, `3C1DD1`, `3C5FC2`). EC has no independent xref because
index +4 selects it. The eleven consumers are:

| Load | Store | Use |
| --- | --- | --- |
| `364CB5` | `364CC7` | camera retention `B663D0` |
| `37001C` | `37002F` | camera retention `B663D0` |
| `3703F5` | `370408` | camera retention `B663D0` |
| `3C1E03` | `3C1E0F` | camera retention `B663D0` |
| `3C5FE1` | `3C5FEF` | camera retention `B663D0` |
| `3B1798` | `3B17A9` | multiplied into player `+B8` |
| `3C4858` | `3C4869` | multiplied into player `+B8` |
| `3C809D` | `3C80AE` | multiplied into player `+E48` |
| `3C9C5A` | `3C9C6B` | multiplied into player `+B8` |
| `651A14` | `651A25` | multiplied into ut35 `+B8` |
| `651C74` | `651C85` | multiplied into ut35 `+B8` |

The alias review covers all 52 LEAs into `7A8100..7A83FF`, across 46 unwind
ranges and their containing decompiled functions. It includes nine common
`7A8150` bases (`3B0A1C`, `3BFED6`, `3C2113`, `3C2469`, `3C5361`, `3C57B6`,
`4680B1`, `46876D`, `468AB8`). Byte-aligned and unaligned scans of
non-executable sections find no VA pointer into that region. The cached
instruction scan finds no additional direct RIP access, wide access
overlapping the pair, or original-binary write. Private turn pairs exclude
E8. Arbitrary pointers constructed dynamically remain outside this bounded
static search. The correction does not modify this shared table.

## Local retention correction

The camera reader `476030` already runs once per stock tick through the
objects gate. Its `+1F0` retention multiplies amplitude `+1E8` once per
update, and `+1F8` is decremented with it. At 120, storing the rewritten
fourth-root factor there would apply a per-render-tick value at stock
cadence, so the shake fades too slowly.

Five `stockpair` rows in `fps_followups13.spec` use immutable copies of the
exact shipped pair while that gate is active. The selector is the live
shadow mode, matching each original indexed load. With a zero mask, or an
unknown live mode, the original table read is retained. The stub preserves
RAX and incoming flags. Its memory `movss` clears upper XMM lanes just as
the original load does. It changes the local loaded value only.

Each load reaches the camera store in a straight line with no call, branch,
interior entry or intervening XMM0 use. The generator proves the mode read,
`mode - 1` index, table base, exact pair bits, destination and active camera
gate before accepting a row. The first writer retains the image base in
RDX from `364C37`. Its dispatch paths (`364C54/364C5B/364C62/364C69`) join
at `364C6E`, then reach mode read `364C82` and load `364CB5`; none rewrites
RDX. This jump-table dominance is manually established alongside the
generator's register-preservation check.

The loaded factor has no independent live-out consumer:

- After `364CC7` and `37002F`, integer instructions lead to
  `364CE1/370049 -> 4B9C80`, a pointer-only call; the writers return void.
- After `370408`, `370424 -> 20A220` takes pointer RCX and byte DL; its
  downstream `44E710` takes integer/pointer arguments. `37042C -> 4B9C80`
  likewise takes no float argument.
- After `3C1E0F`, `3C1E45 -> 1989F0` takes six integer/pointer arguments.
  Its later XMM0 read `198B27` follows `198B12 -> 169EB0`, whose first
  instruction replaces XMM0 from `[rcx+E24]`.
- After `3C5FEF`, an XMM1 store and integer instructions lead to
  `RET 3C6013`. The void writer's sole direct caller `3AF328` continues
  integer dispatch in void function `3AF020`.

The pool's aligned unused bytes `88..8F` hold a pointer to live shadow mode.
It is initialized before jumps are published and refreshed before masks
each tick. The production shadow allocation outlives these stubs. Failed
installation and disabled states retain mask zero, which bypasses pointer
dereference. No saved quake factor is changed on later context, rate or
switch changes, matching the original stored-field lifetime.

## Duration uses the tick snapshot

The five FPS inputs remain `stockfps` rows, now supplying 30 in a captured
stock-30 context or 60 in a captured stock-60 context while the objects gate
is active. At mask zero they read the original FPS byte. Thus an initializer
uses 15 or 30 stock ticks just as the original `floor(fps/30)*15` formula
would. The three battle-seconds rows continue to use 30.

The original engine samples mode for FPS at `4B6481..4B6491`, before the
frame counter increment `4B651E` and the per-tick hook. Duration therefore
uses that tick's captured context, also used to compute the camera gate's
N. Retention instead indexed live mode at its later instruction. Memory-card
paths (`1BFD93`, `1BFFB6`, the task path through `605BBC`) can change mode
after sampling and before actors run, so the two selectors must stay
distinct. The objects metadata now retains the captured mode alongside N,
and refreshes it even if N stays 2 across a rate/context transition.

## Ordinary pause/options paths

Both menu entry paths call `1B2020` before selecting mode 1. This installs
stop bits in `B6B2A0`: bit 14 at `1B2188`, bit 24 at `1B20C8`, and bit 12 at
`1B21E8`.

- Object update `207760` tests bit 14 at `207850..20785B` and, when set,
  tail-jumps through vtable slot 21 at `207868`, bypassing reaction slot 29.
  All 19 reaction-vtable references to the three object writers use this
  update. Their slot-21 handlers return or update facing/transforms without
  dispatching a reaction writer.
  Normal reaction dispatch is `2078FC -> 207F60 -> 208049` (slot 24,
  `363FE0`), then `364007` (slot 29) for reaction state `E35=2`. There are
  no direct callers of these three writers.
- Player update `3A9630` tests bit 24 at `3A9A61`; the stopped path through
  `3A9B66 -> 3A8E20 -> 3ACD43` bypasses `3AF020` and both player writers.
  Normal dispatch is `3AA57F -> 3AF020`; its calls `3AF5B3` and `3AF328`
  are the only direct callers of `3C1A80` and `3C5EA0`, respectively, with
  no retained function pointers to either writer.
- Camera dispatcher `475C70` tests bit 12 at `475C76..475C84` and returns
  before `476030`. Calls in the outer frame dispatcher do not establish that
  the quake reader runs during a pause.
- Actor dispatch `4BA71C` precedes pause/options work at `4BA74A/4BA79E`.
  Pause sets mode 1 at `415C0E`, then restores mode 2 at `414825` before
  releasing stop flags at `4145EA`. Options sets mode 1 at `14A190` and mode
  2 at `14A1F6`, before stop-flag restoration through `14A2C8 -> 14A730`;
  `14A2EA` also restores the saved mode.

The 19 slot-29 storage addresses are `689E50`, `68A700`, `68B0F0`,
`6938F0`, `693E70`, `694420`, `694DA8`, `695438`, `696108`, `696658`,
`696B48`, `697150`, `6979D0`, `698128`, `698990`, `6A3EB0`, `6AA908`
(writer `364B00`), `69B0F8` (`36FEA0`) and `6A7BB0` (`370280`). Their
slot-8 update is `207760` and slot-24 reaction dispatch is `363FE0`.
The stop-flag pop `1B1FB0` restores the saved A0/A4 qword at `1B1FBB`.

These paths exclude all five writers and the reader during ordinary
pause/options operation. Save/title/movie contexts have not all been
excluded. The context-aware correction preserves their stock input units
without depending on that exclusion. The stock nested path that may call
the camera update twice in a frame is retained.

## Offline checks

`tools/verify_quakes.py` executes the actual five initializer instruction
segments against the original binary with shipped stock inputs: 240 cases
cover 30/60/120, both captured contexts, both live modes, mode-table rewriting
on/off and the objects family on/off. It also runs 2,400 actual camera updates
against stock-tick execution, changing context during an existing quake and
comparing amplitude, saved retention and count bytes after every tick.
Both deliberately broken variants are detected: altered private retention
bits and a reversed duration context. All three runs are in the suite.

The generator accepted all five retention proofs and rejected 30 directed
mutations: wrong group, incomplete endpoint, interior entry, changed pair
bits, changed store address and changed mode address for each writer.
The normal window verifier independently varies real, captured and live
mode, both table states, and unknown live modes. At N=1 it supplies an
unusable live-mode pointer to verify that mask zero avoids dereference.

Full build, suite, deployment and package results are recorded with this
pass in the public follow-up and technical notes. Visual shake feel and
pause/resume behavior still require playtesting.
