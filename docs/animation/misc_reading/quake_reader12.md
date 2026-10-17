# Camera quake length: reader and cadence, 2026-10-11

Resolved by following the camera's enclosing base, rather than the position
vector inside it. All addresses below are module RVAs unless prefixed with a
full virtual address. This is static analysis, not an in-game observation.

## Artifact and evidence boundary

The installed `main.dll` and the input of the running Ghidra HTTP bridge have
SHA1 `703d292ab2cb50cc9e237e44722dec51d956b79c`. The bridge reports image base
`180000000`, 27,738 functions, x86 little-endian 64-bit Windows. Its input was
verified against the installed image before using its decompilation.

Additional installed artifacts inspected:

| Artifact | SHA1 | Instructions inspected |
| --- | --- | ---: |
| `main.dll` | `703d292ab2cb50cc9e237e44722dec51d956b79c` | 1,691,049 cached instructions |
| `flower_kernel.dll` | `6f091eabb5c5eeaae4d5d5f37019a76e9d616abb` | 152,581 cached instructions |
| `okami.exe` | `d3b66ea3981efec17d025b34de303c6539de1273` | 11,921 instructions disassembled from `.text` |

Ghidra read-only requests used `get_metadata`, `get_xrefs_to?address=...` and
`decompile_function?address=...` at `http://127.0.0.1:8089/`. Instruction bytes
and resolved addresses were checked independently with the repository's
Capstone/PE readers. No program switch, binary mutation or runtime launch was
needed.

The negative searches are bounded:

- Neither secondary module has an imported symbol from `main.dll`, an exact
  little-endian RVA or preferred-VA literal for `B66380` or `B663D8`, or a
  disassembled RIP-relative operand targeting preferred-VA
  `180B65380..180B6737F`. This excludes straightforward direct access, not
  access through a pointer received at runtime.
- Main's direct memory operands overlapping `B663C8..B663D8`, including operand
  widths that could hide a vector read, have one read: the already known
  writer-side compare `57C304`. Ghidra reports 57 direct references to
  `B663D8`, all writes; it cannot identify the enclosing-object alias from
  that byte's direct xrefs alone.
- A straight-line constant/alias scan seeded by all 4,578 nearby LEAs in
  `B65380..B6737F`, plus the initial nearby pointers at `7AA148` and `7AB210`,
  found no additional direct read of the quake fields before a branch/call
  boundary. This is discovery evidence, not an exhaustive interprocedural
  pointer analysis. The dominant enclosing base `B661E0` led to the reader
  described below.
- Copies from the position vector did not explain the duration. The imported
  cVec copy constructor at flower_kernel `17D5 -> 18D60` reads source `+0`,
  `+4`, `+8` and writes a fixed homogeneous lane. Assignment at
  `14B0 -> 1A9D0` also reads only source `+0`, `+4`, `+8`. A vector source
  at `B66380` therefore cannot copy the byte at `B663D8`. No global claim
  about every memcpy or dynamically computed source is needed after finding
  the actual enclosing-object reader.

## The missing alias

The camera object begins at `B661E0`; `B66380` is its eye position at `+1A0`.
The quake fields are camera offsets, not fields reached from that vector:

| Main RVA | Camera offset | Use |
| --- | --- | --- |
| `B663C8` | `+1E8` | amplitude |
| `B663CC` | `+1EC` | phase step |
| `B663D0` | `+1F0` | amplitude retention per update |
| `B663D4` | `+1F4` | phase |
| `B663D8` | `+1F8` | remaining updates, byte |

The camera initialization at `47F60E` forms `B661E0`; `47F617` sets size
`490`, and `47F61D` clears that object. The object includes the quake fields.

The tick dispatcher supplies the same camera address on both paths:

```text
4BA5FA lea rcx, [B661E0]
4BA601 call 475C70
4BA872 lea rcx, [B661E0]
4BA879 call 475C70
```

`475C70` dispatches the camera mode, then calls `476030` at `475DE3` with the
same object and tail-jumps to camera matrix construction `4831B0`.

## Countdown and visual consumer

`476030` is the actual quake update:

```text
47603A movzx edi, byte ptr [rcx + 1F8]
476041 mov rbx, rcx
476044 test dil, dil
476047 je 476088
476049 movss xmm0, dword ptr [rcx + 1F0]
476051 mulss xmm0, dword ptr [rcx + 1E8]
476059 movss dword ptr [rcx + 1E8], xmm0
476061 movss xmm0, dword ptr [rcx + 1EC]
476069 addss xmm0, dword ptr [rcx + 1F4]
476071 call 13F2E0                     ; phase wrap
476076 dec dil
476079 movss dword ptr [rbx + 1F4], xmm0
476081 mov byte ptr [rbx + 1F8], dil
```

It rests at zero. Its second half does the same for the camera's other shake
block at `+1D4..+1E4` (decrement `4760C1`, store `4760CC`). No new not-yet
gate is appropriate.

The visual consumer is `4831B0`: `4831CF` saves camera rcx to rbp; `4832AC`
tests byte `[rbp+1F8]`. While nonzero, `4832B5` reads phase `+1F4`, calls
sinf at `4832BD`, multiplies by amplitude `+1E8` at `4832C2`, and adds the
result to the camera projection component `+174` at `4832CA..4832D2`.
This directly connects the byte to a camera shake rather than a rumble request.

The existing `objects` `gatefn 476030` row in `camera_rates119.spec` already
paces the whole update: amplitude, phase, wrap and both durations together.
The corresponding manifest and `camera_fixed119.spec` classify it that way.
`worldAnimsN` selects the context's original cadence: gameplay shadow mode 2
runs it at 30 Hz (`N=2` at 60, `N=4` at 120); shadow mode 1 uses 60 Hz.
Disabling the objects family leaves the function at its original cadence.

This is a count per invocation, not a claim that every camera mode invokes it
exactly once a game tick. `4760E0` has seven internal call sites, each on an
alternative path (`47630A`, `476321`, `47633B`, `476355`, `47636F`, `476389`,
`4763A3`); a nested mode can call it there and again from outer `475C70`.
Those are also stock call paths and share the existing entry gate.

## Length decision and proposed rows

The constant writers are already in the paced reader's stock-update units.
They need no new rows. The five fps-derived lengths require normalization on
their input while the same objects-family cadence gate is active:

| FPS read | `mov eax, 88888889` | Byte store to `B663D8` | Enclosing function |
| --- | --- | --- | --- |
| `364CBE` | `364C96` | `364CD8` | `364B00` |
| `370026` | `370021` | `370040` | `36FEA0` |
| `3703FF` | `3703FA` | `37041B` | `370280` |
| `3C1DE8` | `3C1E08` | `3C1E3C` | `3C1A80` |
| `3C5FE6` | `3C5FBD` | `3C6008` | `3C5EA0` |

Each reads fps into ecx, multiplies the unsigned magic reciprocal by ecx,
shifts the high product edx right four, copies dl into eax, multiplies that
by 15 into ecx, and stores cl. This is `floor(fps/30)*15`. The value reaches
the quake store on a straight line without a call or branch.

The fps byte is 60 at both 60 and 120 fps. With the current gameplay camera
gate these writers consequently request 30 stock updates, about one second,
instead of the stock-30 request of 15 updates, about half a second. They are
twice as long at 60 and 120, not four times as long at 120.

Recommended implementation: five `objects` `stockfps` rows on the fps reads,
with proof tying the reciprocal/multiply/store sequence to `B663D8` and to
the existing same-group `gatefn 476030`. Supply 30 only while that group's
mask is nonzero. With its gate disabled, preserve the original fps byte and
arithmetic. Do not change the fps byte globally, the constant duration
writers, or the shared reader's cadence.

Static identity and cadence are resolved; the requested runtime reader probe
is unnecessary. In-game validation of the resulting five rows remains to be
done: at 120, compare a scenery/player impact shake with one F9 switch to
stock. It should end at the same time. `WatchBytes=B663D8` is optional
diagnostic context; its status-line sampling can miss a half-second quake.

The five writers are world-object reaction slot 29 or player gameplay action
paths. Their normalization uses gameplay stock-30 units. The nonzero objects
mask also occurs at 120 in stock-60 menu contexts, so it does not itself prove
that a writer executes only in gameplay. Common actor dispatch can run on a
paused path; static analysis has not excluded every writer from every menu
path. No incorrect menu execution has been observed. Runtime coverage must
include entering and leaving pause/options during a quake, compared with F9;
the offline verifier establishes trampoline semantics, not this reachability.

## Separate follow-up: mode-table retention

The same five writers load the quake retention from the mode-indexed pair
`7A81E8/7A81EC` and store it at `B663D0`:

| Factor read | Retention store |
| --- | --- |
| `364CB5` | `364CC7` |
| `37001C` | `37002F` |
| `3703F5` | `370408` |
| `3C1E03` | `3C1E0F` |
| `3C5FE1` | `3C5FEF` |

The installed table pair is approximately `sqrt(0.8), 0.8`.
`mode_constants.h` rewrites its mode-1 entry to stock `0.8` raised to the
elapsed-time scale. That factor is appropriate for consumers updating every
render tick. Camera shake instead applies its saved factor only when the
existing whole-function stock gate runs. This compounds two conversions and
can make the amplitude decay too slowly. It is distinct from the byte's
duration and is not repaired by the five length rows.

Keep this as a separate follow-up. The table is shared by player motion and
ut35 consumers; changing it globally would change their established units.
A local correction requires a proof covering the source table's runtime
rewrites, the camera gate's switch/context states and the retention's other
consumers, plus an appropriate encoder and directed verification. No float
row or shared-table change is proposed in this length pass.

The double-pacing survey detects four of these integer FPS rows beside the
rewritten table (`370026`, `3703FF`, `3C1DE8`, `3C5FE6`). Their explicit
REVIEWED entries identify separate destinations: integer length `B663D8`
and float retention `B663D0`. These entries establish that the new integer
normalization does not scale a rewritten float; they do not resolve the
pre-existing retention follow-up above. The survey's scope and detection
rules remain unchanged.
