# Script elapsed seconds and two stage sound delays

Static reading, 2026-10-11. All addresses below are main.dll RVAs, with image
base `180000000`. The installed binary and the local Ghidra input `main.dll`
both have SHA1 `703d292ab2cb50cc9e237e44722dec51d956b79c`. The `.text`,
`.rdata`, and `.data` sections in `tools/.disasm_cache/read_candidates.pkl`
match the mapped sections of that binary. The disassembly, cached call graph,
and the retained decompilation `main_decompiled.c` supply the evidence below.
This is a static cadence proof, not an in-game observation.

## The object is a plain pool record

`3F2E00` returns `[mgr + 358 + 8*index]`. The three seconds readers use
indices **2**, **3**, and **1**, respectively; they are not all index 3.

* `3F4EB0` calls `23D920` at `3F4F70`, retains its result in RSI, and stores
  that result at `[mgr + 358 + 8*index]` at `3F5036`.
* `23D920` chooses an unused record at `9C2230 + index*50` (address built
  at `23D97D..23D98F`). It allocates and zeroes a separate 88-byte data block
  (`23D9B2`, `23D9C6`) and puts its pointer in the record's first qword at
  `23DA00`. The record's `+8` is the linked-list next pointer. The occupied
  flag is `+24` bit 31; `23DAA7..23DAAC` merges the caller's flags there.
* The static array is 6E records of 50 bytes, initialized by `12C8F0`
  through the vector constructor iterator. Its element constructor
  `23C200` only returns RCX; its destructor `23C210` returns. Neither
  installs a vtable. The first qword is ordinary data, not a vtable.
* `3F50F0` searches the linked list headed by `9C2190` using fields of
  `[node]`, then stores the selected **node** at `3F515B`. Thus both
  manager-element writers refer to the same record type.

The semantic name "battle-list record" follows from `23C420` creating
enemies, tracking the battle states and result, and `23D900` tallying kills
through the record. No recovered source class name or vtable is needed to
identify `node+40`.

## Writers and cadence of node+40

`23C420` zeroes `R12D` at `23C708`. Its battle-start path assigns state 3 at
`23C947` and writes that zero to `[R14+40]` at `23C94F`. `23E0C0` also
clears the entire pool with `memset(9C2230, 0, 2260)` at `23E0CF`, during
manager initialization. The allocator itself does not reset `+40`; the
battle-start path does.

The live increment is **23D789**, `inc dword ptr [rbx+40]`, in `23D700`.
Its guards are the global pause/inactive tests at `23D706..23D754`, then
record `+24` bit 19 set and bit 16 clear at `23D775..23D787`. It calls
`23C420` before the increment. Within the battle-list implementation
`23B950..23EC00`, the only explicit dword writes to this record's `+40`
are the reset and this increment; the separate `23BB90` float `+40` accesses
belong to the manager passed after the list traversal, not a node.

`23B9F0` walks the active list (`[manager]`, next at `node+8`) and calls
`23D700` at `23BA43`, once for each node per update. Its callers are:

* `4BA6AC` in the regular dispatcher `4BA500`;
* `493FA8` and `4942B4` in the two scene spins.

The existing `actor/count` manifest row at **23D789** already holds that
increment between stock ticks, retaining the original pause and inactive
guards. Its counter is therefore in **stock 30-Hz units during gameplay**
while that family is enabled, not current high-FPS units. Keep this row;
changing it to current-tick units would change every other consumer of the
battle elapsed count.

The `task_waits.h` entry at **4B1DC1** is a ten-tick pause before the script
polls battle completion. It does not call or pace `23D700`. The polling
yields at `4B1E30` similarly wait for a record updated by the dispatcher.
The analogous ten-tick entry at `5381E4` is also separate from the count.
Neither makes the counter an iteration count of the waiting script.

## The three divisions

| Script | Manager element read | Count load | FPS-byte load | Unsigned division | Result test |
|---|---|---|---|---|---|
| `4B1D80` | `4B1E56`, index 2 | `4B1E65`, EBP = `[RAX+40]` | `4B1FE2` | `4B1FF4`, `div ecx` | seconds <= 12 at `4B1FFB` |
| `4FBCB0` | `4FBD86`, index 3 | `4FBD94`, EAX = `[RAX+40]` | `4FBD8B` | `4FBD97`, `div ecx` | seconds < 25 at `4FBEDE` |
| `5381A0` | `53829A`, index 1 | `5382A9`, ESI = `[RAX+40]` | `538422` | `538432`, `div ecx` | seconds <= 30 at `538436` |

All three FPS loads are `movzx ecx, byte ptr [B6AC44]`. Their paths to the
division neither branch nor overwrite ECX. The quotient is displayed or
saved through UI object `79BEF8+2CC` and selects the completion result; this
is elapsed-time reporting and grading, not a countdown of script yields.

Required rows, in the **actor** group to match the existing count row:

```
stockfps 4B1FE2 0x4B1FF4
stockfps 4FBD8B 0x4FBD97
stockfps 538422 0x538432
```

`stockfps` retains the original byte load, then substitutes 30 only while
the actor group's mask is nonzero; mask zero retains the original load and
incoming flags. With actor pacing active the arithmetic is `stock_count/30`.
At stock rate or with the family disabled it remains `raw_count/fps_byte`.
It must use the actor mask, not the independent flag group's mask, and
must not change the shared FPS byte. The port's byte reads 60 at both 60
and 120 in the current patch, so the previous paced-count calculation
reported half the true active battle time in those modes.

The divisor has no independent FPS use after these divisions. After
`4B1FF4`, success overwrites ECX at `4B203E` and failure overwrites RCX at
`4B2051`. After `538432`, success overwrites ECX at `538467` and failure
overwrites RCX at `5384F4`. `4FBD97` immediately overwrites RCX at
`4FBD99`. Thus changing this loaded value also preserves unrelated FPS
consumers on the scripts' outgoing paths.

This identifies the incrementer and establishes the conversion statically;
an incrementer probe is not needed to decide the fix. In-game confirmation
should compare a timed battle's reported seconds and completion threshold at
120 against F9, allowing the normal integer-second truncation.

## Census: callbacks 4C5900 and 4C5E80

These are per-tick stage callbacks, not task-wait loops or counts of stage
transitions. Their registration and dispatch are fully indirect:

* `4C5D24` loads callback `4C5900` into RDX; `4C6044` loads `4C5E80`.
* Each calls `48C8C0`, which supplies `7E57C0` as RCX to `136400`.
  `136400` stores RDX at `[RCX+38]`.
* Dispatcher call `4BA5D1` reaches `48BE20`; its active state calls
  `48C120`, which calls `48C280` at `48C14C`. The alternate branch at
  `48BE99` tail-jumps directly to `48C280`.
* `48C2B4` calls `135940`. This loads `[state+38]` and tail-jumps at
  `135951`, with stage `[state+18]` in ECX and stage frame `[state+1C]`
  in XMM1. There is no stock-tick gate or task wait on this chain.

`4C5900` arms byte `B6D6D8` and zeroes counter `B6D6DC` at `4C5B48` after
the stage-6 readiness event. On **every subsequent callback**, including
other stages, it executes:

```
4C5C23  mov eax, [B6D6DC]
4C5C29  mov edx, eax
4C5C2B  inc eax
4C5C2D  mov [B6D6DC], eax
4C5C33  cmp edx, 15
4C5C36  jne 4C5C4B
4C5C46  call 44A160       ; sound action 12
```

`4C5E80` has the same pattern: arm byte `B6D6E0`, reset `B6D6E4` at
`4C5F31`, increment/store at `4C5FDF/4C5FE1`, compare **old count** at
`4C5FE7`, skip to `4C5FFF`, sound call at `4C5FFA`.

Each is an elapsed delay after an event, so it needs a count row. Holding
the store alone would leave old count 15 visible on every intervening
tick and repeat the sound; gate the compare itself with the same group's
mask. This also preserves the original post-increment timing (old 15),
without gating any unrelated family on a held path:

```
count 4C5C2D
notyet 4C5C33 0x4C5C4B
count 4C5FE1
notyet 4C5FE7 0x4C5FFF
```

The reset and arm writes remain once per event. The callback registration,
readiness polling, stage changes, and sound start remain per tick; only
the elapsed count and its sound equality need pacing.

## Census: brush idle gap 16E978

In brush update `16C7E0`, `896BEC` is initialized to 30 at `16D3FE` when
entering drawing and reloaded to 30 at `16EA79` on the path that constructs
the next recorded point (`16EB09` onward). While the drawing input remains
active and the point buffer has room (`7E71E4 < 600`), `16E970..16E978`
loads, decrements, and stores this elapsed idle gap once per update.
At `16E985..16E999`, a value <= 0 only ORs bit 8 into the last point's
flags. Repeating that OR is idempotent; it is not a point append or an
input event.

The `player/count` row at `16E978` therefore paces elapsed idle time.
It does not pace the actual point count: `16F622` increments EBX and
`16F624` stores `7E71E4` after a new point. Input reads, pointer movement,
the reload, and point construction also remain current-tick operations.
The reload is reached only after the unchanged-position/no-new-input path
has been rejected (`16E99E..16EA79`).

The test uses the computed decrement in EAX, so on a held tick with a
stored gap of 1 it can set the last point's flag up to 25 ms before the
stock store at 120. The nonpositive side remains an idempotent flag write
between uses; it does not rearm a transient zero or repeat an event.
No notyet row is justified there under the resting-countdown rule.
