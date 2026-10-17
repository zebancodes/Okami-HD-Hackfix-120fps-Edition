#!/usr/bin/env python3
"""Audit integer updates absent from the original self-update census.

Read the read_candidates cache (its instruction addresses are already RVAs;
absolute operands still use image base 180000000). Find non-stack memory
inc/dec and add/sub-immediate instructions, and load / step / same-address
stores within six following instructions, without crossing a control transfer.
RIP operands are resolved before comparing addresses, including globals.
RSP operands are excluded. RBP is conservatively retained because it often
holds an object pointer here; true frame aliases and data misdecodes receive
explicit setup verdicts rather than being silently excluded.

Every candidate must have an explicit REVIEWED verdict; a per-tick verdict
also needs a selected world row. --check is deliberately closed-world: an unclassified candidate
fails, so a future per-tick update cannot silently escape the audit.
"""
import argparse
import bisect
import collections
import csv
import os
import pickle
import re
import sys

import read_candidates as rc

DOCS = rc.DOCS
REG = re.compile(r"^(?:r(?:[abcd]x|[sb]p|[sd]i|[89]|1[0-5])(?:d|w|b)?|e[abcd]x|e[sb]p|e[sd]i|[abcd][xhl]|[sb]p|[sd]i|[sb]pl|[sd]il)$")
IMM = re.compile(r"^-?(?:0x[0-9a-f]+|[0-9]+)$")
MEM = re.compile(r"\[([^]]+)\]")

# Store / read-modify-write RVA -> (verdict, evidence).
# Verdicts: setup, event, family, current_tick, per_tick.
REVIEWED = {
    0x150B: ('event', 'Audio-service invocation count B75A5C: modulo 7D7938 dispatches 2394/27C0. 14F4 callers 7D5C/132EC poll completion and Sleep(10); 2394 reads performance-counter elapsed time via 1CD54. This is library service cadence, not a world frame timer.'),
    0x214F: ('event', 'Audio-service invocation count B75A5C: modulo 7D7938 dispatches 2394/27C0. 14F4 callers 7D5C/132EC poll completion and Sleep(10); 2394 reads performance-counter elapsed time via 1CD54. This is library service cadence, not a world frame timer.'),
    0x257B: ('setup', 'Leaf 2574 decrements B75A58 and tail-calls mutex unlock 76D24; paired lock-depth bookkeeping in 2394, not elapsed time.'),
    0xA954: ('setup', 'Leaf A918 appends rdx+28 to head/tail at owner+110/+118, then increments owner+120 list length.'),
    0xB928: ('setup', 'B91C increments B760B0 and initializes library storage only on transition to 1 (7AB2C and zeroed globals).'),
    0x12D49: ('setup', '12CE0/leaf12D44 register a node in B760E8/B760F0 list, set node+10 registered flag, and increment aggregate/member counts B760E0/B760F8 under mutex.'),
    0x12D6B: ('setup', '12CE0/leaf12D44 register a node in B760E8/B760F0 list, set node+10 registered flag, and increment aggregate/member counts B760E0/B760F8 under mutex.'),
    0x132D5: ('setup', '131BC unlinks registered list member, clears next/self and node+10 registration flag, and decrements matching B760F8/B760E0 membership counts.'),
    0x132DB: ('setup', '131BC unlinks registered list member, clears next/self and node+10 registration flag, and decrements matching B760F8/B760E0 membership counts.'),
    0x1CC4F: ('setup', 'Leaf1CC48 returns rcx-8 to B764A0 free list and decrements B76268 outstanding allocation count.'),
    0x1CD6F: ('setup', '1CD5C first-use reference count B764A8: transition to 1 initializes timing library/frequency and globals.'),
    0x1F828: ('setup', '1F7DC constructs/registers fader (7BB04), increments B76604 live faders, and initializes shared timestamp on first registration.'),
    0x1F9C8: ('setup', '1F9BC initialization reference count B76600: first-use 7BC08/1CD5C plus fader pool allocation.'),
    0x201B2: ('setup', '20124 finalization loop removes B76638 list heads, destroys each fader at 200CC, and decrements outstanding B76648; reports finalization while faders remain used.'),
    0x24BA1: ('setup', '240F0 prologue sets RBP=entryRSP-E8. RBP+110 is stack local/home storage, decremented inside a finite array traversal at24B5A while rbx advances by2.'),
    0x2B688: ('setup', 'Not executable data: linear decode of inline switch table following295E8 produces nonsensical lods/scas/huge-displacement writes; candidate is table bytes.'),
    0x30468: ('setup', '30460 initialization reference count B769E8: only transition to1 clears list/storage globals.'),
    0x306AE: ('setup', 'Leaf3066E drains list: updates head/prev at owner+0/+8 and node+128/+130/+138 then decrements owner+10 membership count and loops on next head.'),
    0x34A3B: ('setup', '34A04 finalization reference count B76A40: when last reference, destroys list B76A48 before decrement.'),
    0x34A7D: ('setup', '34A70 initialization reference count B76A40: first reference zeroes list B76A48/B76A50/count B76A58.'),
    0x350A4: ('setup', '35098 initialization reference count B76A60: first use creates mutex/work object at B76A70 via76BF0.'),
    0x3C93F: ('setup', 'Leaf3C8E8 splits an identifier into masked bitfields; output [r9] is doubled and ORed with1 (3C934-3C93F). This is bit packing, not a running count.'),
    0x4695C: ('event', 'Leaf4694C generates B76B08 sequence value, increments and skips sentinel -1 by substituting0; an identifier-generation operation, no time threshold.'),
    0x4BB15: ('event', 'B7737C is audio voice serial generator. 4B9A8/4C7C8 pass old value to voice allocation4DA24 then increment; leaf4CC10 returns old value and increments. One change per voice/identifier request.'),
    0x4C8C7: ('event', 'B7737C is audio voice serial generator. 4B9A8/4C7C8 pass old value to voice allocation4DA24 then increment; leaf4CC10 returns old value and increments. One change per voice/identifier request.'),
    0x4CC1A: ('event', 'B7737C is audio voice serial generator. 4B9A8/4C7C8 pass old value to voice allocation4DA24 then increment; leaf4CC10 returns old value and increments. One change per voice/identifier request.'),
    0x4D0D9: ('setup', '4CCC4 prologue sets RBP=entryRSP-57. RBP+5F is stack loop count, decremented per BusSend entry while output pointer advances (4D048-4D0E0).'),
    0x4D0DD: ('setup', '4CCC4 RBP is stack frame base (entryRSP-57); RBP+6F is stack BusSend loop index incremented alongside remaining count at4D0D9.'),
    0x4E2D8: ('setup', '4E2D0 library initialization reference count B77678: first use clears list storage B77680/B77688/B77690.'),
    0x4E7D7: ('setup', 'Leaf4E7B0 fills a newly registered callback/work entry and increments owning record+16 registration/reference count; no cyclic timer consumer.'),
    0x51058: ('setup', '5104C first-use reference count B81720: initializes thread/platform settings only when count becomes1.'),
    0x51260: ('setup', 'Leaf51260 decrements 7D7EC0 allocation/reference count; paired allocation511D8 increments after pool object registration51620.'),
    0x54025: ('setup', 'Leaf54014 swaps owner+2C8 pointer: decrements old pointee+124 and increments new pointee+124 only if pointer changes. Reference ownership transfer.'),
    0x54037: ('setup', 'Leaf54014 swaps owner+2C8 pointer: decrements old pointee+124 and increments new pointee+124 only if pointer changes. Reference ownership transfer.'),
    0x547EC: ('setup', 'Paired short-count accessors at547EC/547F8 decrement/return or increment object+1A; adjacent547E4 returns object size20 and54800 parses record. No static callers or pointer refs for these leaf accessors in inspected cache; no elapsed-time consumer.'),
    0x547F8: ('setup', 'Paired short-count accessors at547EC/547F8 decrement/return or increment object+1A; adjacent547E4 returns object size20 and54800 parses record. No static callers or pointer refs for these leaf accessors in inspected cache; no elapsed-time consumer.'),
    0x56717: ('setup', '560F8 RBP is stack-derived (rsp-68 before frame allocation). RBP+B0 is local ushort command/track index advanced by parsed operand, compared with local limit; cue parsing loops, not persistent timer.'),
    0x567A9: ('setup', '560F8 RBP is stack-derived (rsp-68 before frame allocation). RBP+B0 is local ushort command/track index advanced by parsed operand, compared with local limit; cue parsing loops, not persistent timer.'),
    0x568B4: ('setup', '560F8 stack-derived RBP+D8 is local ushort outer cue/track loop index, increment then compare against local118 loop bound (56899-568BE); decompile param6 low word.'),
    0x5713C: ('setup', 'Leaf5713C advances input cursor [rdx] by2, reads bytes at newcursor-2/-1, and constructs big-endian word. Byte-stream parsing cursor.'),
    0x57838: ('setup', '5717C prologue RBP=entryRSP-E8. RBP+F8 is stack ushort parser index, advanced by decoded big-endian operand and compared with stack limit; finite cue record traversal.'),
    0x578CF: ('setup', '5717C prologue RBP=entryRSP-E8. RBP+F8 is stack ushort parser index, advanced by decoded big-endian operand and compared with stack limit; finite cue record traversal.'),
    0x57CF5: ('setup', '5717C RBP is stack frame base; RBP+100 local ushort outer parser/track index increments and compares to stack loop bound before branch576E6.'),
    0x5C41C: ('setup', '5C2B4 RBP=rsp-F90. RBP+FD8 is stack chunk-loop index local_res10, incremented per <=128-sample decode block until computed block count; output pointer and remaining byte count advance together.'),
    0x5CBA9: ('setup', '5CA58 RBP=entryRSP-3F. RBP+7F is stack param8 loop index, increments per <=128-sample conversion block; same loop reduces input/output remaining sample counts and advances channel pointers.'),
    0x5CDE2: ('setup', '5CBEC RBP=entryRSP-1018. RBP+1058 is stack remaining output byte budget, reduced by converted sample count times channels times2; block conversion, not elapsed time.'),
    0x5CDEF: ('setup', '5CBEC stack-derived RBP+1030 is local_res18 block-loop index, incremented per conversion block and compared to precomputed block count at5CDF5.'),
    0x5D6AF: ('setup', 'Leaf5D6AC decrements record use/ref count [rcx] and copies record+18 back to+14; paired queue insertion5DB94 increments same record count. Queue ownership bookkeeping.'),
    0x5DBB0: ('setup', 'Leaf5DB94 appends record rdx to owner head/tail+10/+18 using next+68 then increments record [rdx] ownership count; matches release5D6AC.'),
    0x61269: ('setup', '61184 prologue RBP=RSP. RBP+30 stack local_res8 is produced sample count, initialized0 then adds return from614C0; bounded audio-buffer fill, returns sample count.'),
    0x74E19: ('setup', '74628 prologue RBP=entryRSP-198. RBP+90/+20 are stack finite DSP sample/block-loop counts, decremented while output float pointers advance (40/20-byte strides); local arithmetic buffer processing.'),
    0x752EE: ('setup', '74628 prologue RBP=entryRSP-198. RBP+90/+20 are stack finite DSP sample/block-loop counts, decremented while output float pointers advance (40/20-byte strides); local arithmetic buffer processing.'),
    0x75824: ('setup', '74628 prologue RBP=entryRSP-198. RBP+90/+20 are stack finite DSP sample/block-loop counts, decremented while output float pointers advance (40/20-byte strides); local arithmetic buffer processing.'),
    0x773AE: ('setup', '77334 decrements B83D10 initialization reference count after last-reference shutdown/freeing library resources and zeroing globals.'),
    0x789F8: ('setup', '789B8 decrements B83F5C initialization reference count; last reference destroys exactly8 objects in E697A0 array first.'),
    0x78C85: ('setup', '78C28 increments B83F5C initialization reference count after first-use allocation of8 E697A0 objects.'),
    0x7A1CD: ('setup', 'Leaf7A1B8 links node rdx through next/prev+8/+10 and owner tail+8, then increments owner+10 list membership count.'),
    0x7BC14: ('setup', '7BC08 initialization reference count B83F90: first use queries performance frequency and initializes timing library846D8.'),
    0x7F47C: ('setup', '7F470 initialization reference count B83FB8: first use sanitizes CRI copyright/version string storage, not a frame counter.'),
    0x80920: ('event', 'Leaf80920 increments decoder/parser stage at object+E0; adjacent7FE40 also completes bit-buffer work by advancing+E0. No static references to leaf80920 in inspected cache; this is stage completion, no elapsed-time comparison.'),
    0x819B3: ('event', 'Leaf819A0 advances codec stage+E0, explicitly skips stage1 to2 and stageA toB. A parser/decoder state ordinal, not a duration; no static references to this leaf in inspected cache.'),
    0x826BC: ('setup', '826B0 initialization reference count B83FCC: first use calls85070/7F470, then returns0.'),
    0x85078: ('setup', '85070 initialization reference count B83FF8: first reference increments shared initialization count B83FFC; no time threshold.'),
    0x88B8D: ('setup', '88AD4/8C520 allocate library work handle via8D714, increment live B84080 below configured capacity B84070, and update high-water B84078.'),
    0x8B91C: ('setup', '8B87C/8E9A8 allocate binder handle via8D714, increment live B84084 below configured capacity B84074, and update high-water B8407C.'),
    0x8C578: ('setup', '88AD4/8C520 allocate library work handle via8D714, increment live B84080 below configured capacity B84070, and update high-water B84078.'),
    0x8EA24: ('setup', '8B87C/8E9A8 allocate binder handle via8D714, increment live B84084 below configured capacity B84074, and update high-water B8407C.'),
    0x910E4: ('setup', 'Matched decrement/increment-return leaf accessors for B84744, with no other RIP accesses and no direct callers/pointer refs in inspected cache. Reference/count accessor pair; no reachable clock or elapsed-time consumer established.'),
    0x9114C: ('setup', 'Matched decrement/increment-return leaf accessors for B84744, with no other RIP accesses and no direct callers/pointer refs in inspected cache. Reference/count accessor pair; no reachable clock or elapsed-time consumer established.'),
    0xA0D20: ('setup', 'Matched decrement/increment-return leaf accessors for BA986C, with no other RIP accesses or direct callers/pointer refs in inspected cache. Library count accessor pair; no reachable world-time consumer established.'),
    0xA0D54: ('setup', 'Matched decrement/increment-return leaf accessors for BA986C, with no other RIP accesses or direct callers/pointer refs in inspected cache. Library count accessor pair; no reachable world-time consumer established.'),
    0xA13D2: ('setup', 'A1330 links work node at object+10 into BA9938/BA9940 queue, increments BA9948 queue length, sets object+148 queued flag, and signals worker832FC.'),
    0xA14A0: ('setup', 'A1410 appends node to BA9918/BA9920 list and increments BA9928 list length under mutex.'),
    0xA1675: ('setup', 'A1580 worker-loop removes BA9938 queue head, clears its next, decrements BA9948 queue length; bounded by initial queue size and worker event.'),
    0xA16EB: ('setup', 'A1580 worker-loop requeues existing job by relinking BA9938/BA9940 and increments BA9948 queue length; balances dequeue A1675, not passage of time.'),
    0xA1779: ('setup', 'A1580 worker-loop requeues existing job by relinking BA9938/BA9940 and increments BA9948 queue length; balances dequeue A1675, not passage of time.'),
    0xA1CE8: ('setup', 'A1CD0/A2200 bracket mutex BA99A8 with increment/decrement of BA99F8 lock nesting/active-holder count.'),
    0xA1EB4: ('setup', 'A1DA0 unlinks object+10 from BA9938 queue, clears next and queued flag+148, and decrements BA9948 queue length.'),
    0xA200A: ('setup', 'A1F30 unlinks node from BA9918/BA9920 list, clears node+8, and decrements BA9928 list length under mutex.'),
    0xA220C: ('setup', 'A1CD0/A2200 bracket mutex BA99A8 with increment/decrement of BA99F8 lock nesting/active-holder count.'),
    0xA92D1: ('setup', 'A9200/A92F0 acquire/release singleton library resource BA9A60, update BA9A58 initialization count, and set/reset A2100 owner pointer.'),
    0xA9347: ('setup', 'A9200/A92F0 acquire/release singleton library resource BA9A60, update BA9A58 initialization count, and set/reset A2100 owner pointer.'),
    0xA9868: ('setup', 'A9860 first-use initialization count BA9B70; only transition to1 initializes criMvPly/PCx64 library/version data and storage.'),
    0xB8EE4: ('setup', 'Not executable data: repeated8-byte inline jump-table entries after tail jump126784 atB8EDD. Linear decode invents huge negative-RBP byte decrements.'),
    0xB8EEC: ('setup', 'Not executable data: repeated8-byte inline jump-table entries after tail jump126784 atB8EDD. Linear decode invents huge negative-RBP byte decrements.'),
    0xB8EF4: ('setup', 'Not executable data: repeated8-byte inline jump-table entries after tail jump126784 atB8EDD. Linear decode invents huge negative-RBP byte decrements.'),
    0xB8EFC: ('setup', 'Not executable data: repeated8-byte inline jump-table entries after tail jump126784 atB8EDD. Linear decode invents huge negative-RBP byte decrements.'),
    0xBCB91: ('setup', 'Not an instruction boundary: function BCB90 bytes 8D42FF4C8BD1 decode as lea eax,[rdx-1]; mov r10,rcx. Candidate BCB91 is mid-instruction from prior linear table decode.'),
    0xBD4E5: ('setup', 'BD3E0 finalization removes object+238 from BA9D28/BA9D30 movie-work list, clears links, and decrements BA9D38 membership count.'),
    0xBD969: ('setup', 'BD8B0 iterates initial BA9D38 movie-work count; dequeue decrements atBD969, callback invocation, then requeue increments atBDA32. Membership bookkeeping within one service pass.'),
    0xBDA32: ('setup', 'BD8B0 iterates initial BA9D38 movie-work count; dequeue decrements atBD969, callback invocation, then requeue increments atBDA32. Membership bookkeeping within one service pass.'),
    0xBEA9C: ('setup', 'BE450 registers movie object+238 in BA9D28/BA9D30 work list and increments BA9D38 membership count after allocation/setup succeeds.'),
    0xC00A5: ('event', 'C0030 creates CriManaSoundEx PCM voice/pool state; BA9D88 increments unique ID seed, stored with10000000 tag in object+18C and wraps beyond11111111. Per allocation ID, not time.'),
    0xC1C45: ('setup', 'C1A10 RBP=rsp-98. RBP+E0 is stack aggregate sample/stream offset advanced by per-entry amount; loop bound is input record+10 and record pointer advances, no persistent field.'),
    0xC3395: ('setup', 'C3300 first-use initialization reference count BA9DB0: initializes movie decoder storage/D0290/D0D30 only when prior count0.'),
    0xC3AE9: ('event', 'LeafC3AE0 codec notification increments skipped-picture statistics/backlog+19C/+1A0 unless260==1; vtable entries7D88A8/7D89B8. C48C0 consumes+1A0 on skipped B-picture processing; C42E0 includes it in decoded-picture timestamp. Per picture notification, not world tick.'),
    0xC3AEF: ('event', 'LeafC3AE0 codec notification increments skipped-picture statistics/backlog+19C/+1A0 unless260==1; vtable entries7D88A8/7D89B8. C48C0 consumes+1A0 on skipped B-picture processing; C42E0 includes it in decoded-picture timestamp. Per picture notification, not world tick.'),
    0xCF2A0: ('setup', 'LeafCF2A0 decrements BAD720 library initialization count; transition to0 clears fixed3800-byte global workspace via65D6E2. Last-reference shutdown.'),
    0xD04A0: ('setup', 'LeafD04A0 decrements BAD730 library initialization count; transition to0 clears fixed2400-byte global workspace via65D6E2. Last-reference shutdown.'),
    0xD2370: ('setup', 'Isolated leafD2370 increments BADFB0 and returns; cache has no direct callers/pointer refs, and BADFB0 has no other RIP accesses. No reachable world-update or time consumer established; retained unused library accessor.'),
    0xD4850: ('setup', 'D4840/D4900 decrement/increment BADFC8 worker-library reference count; last/first reference destroys/creates multicore worker resources after GetSystemInfo, not time.'),
    0xD490C: ('setup', 'D4840/D4900 decrement/increment BADFC8 worker-library reference count; last/first reference destroys/creates multicore worker resources after GetSystemInfo, not time.'),
    0xEA030: ('setup', 'Codec macroblock-column cursor+179C increments and wraps at picture width+15A0, then resets to0. E9E90 consumes+179C as X position times16 for image motion compensation.'),
    0xEA044: ('setup', 'Codec macroblock-row cursor+1798 increments only on column+179C wrap at width+15A0. E9E90 uses+1798 as Y position times16 for image motion compensation.'),
    0xEA054: ('setup', 'Codec processed-macroblock count+1794 increments alongside spatial column/row traversal in leafEA030/EBB50, one per image block, not per game frame.'),
    0xEB419: ('setup', 'Pixel interpolation leafsEB400/EB420 write rounded average (a+b+1)>>1 to output byte. Scanner mistakes the rounding add1 plus source load/store for an elapsed counter.'),
    0xEB43D: ('setup', 'Pixel interpolation leafsEB400/EB420 write rounded average (a+b+1)>>1 to output byte. Scanner mistakes the rounding add1 plus source load/store for an elapsed counter.'),
    0xEBB50: ('setup', 'Codec macroblock-column cursor+179C increments and wraps at picture width+15A0, then resets to0. E9E90 consumes+179C as X position times16 for image motion compensation.'),
    0xEBB64: ('setup', 'Codec macroblock-row cursor+1798 increments only on column+179C wrap at width+15A0. E9E90 uses+1798 as Y position times16 for image motion compensation.'),
    0xEBB74: ('setup', 'Codec processed-macroblock count+1794 increments alongside spatial column/row traversal in leafEA030/EBB50, one per image block, not per game frame.'),
    0xEC43A: ('setup', 'EC420 first-use CRI DLG library reference count E4F3F0; transition to1 creates mutex/work storage viaEC0C0 and sets version string.'),
    0xECD19: ('event', 'Codec ECCA0/F4B70/FB0D0/1035A0 increments histogram array+CF8 indexed by decoded type at+2E0, after bitstream feature flag+71C test; counts parsed block types, not elapsed ticks.'),
    0xF419D: ('event', 'Codec error branch sets object+B80=1, increments error total+D0C, returns -1 (or jumps to shared exit); only decoder failure, not unconditional timer.'),
    0xF41F5: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0xF421D: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0xF4225: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0xF4235: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0xF45F8: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0xF4B0F: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0xF4B19: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0xF4BE8: ('event', 'Codec ECCA0/F4B70/FB0D0/1035A0 increments histogram array+CF8 indexed by decoded type at+2E0, after bitstream feature flag+71C test; counts parsed block types, not elapsed ticks.'),
    0xF4C59: ('event', 'Codec variable-length lookup returns sentinel -80; failure branch increments object+D0C error count then rejoins parser. Other path consumes/refills bits; one per invalid code, not time.'),
    0xF4D17: ('event', 'Codec variable-length lookup returns sentinel -80; failure branch increments object+D0C error count then rejoins parser. Other path consumes/refills bits; one per invalid code, not time.'),
    0xFA723: ('event', 'Codec error branch sets object+B80=1, increments error total+D0C, returns -1 (or jumps to shared exit); only decoder failure, not unconditional timer.'),
    0xFAB98: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0xFABA0: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0xFAE19: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0xFB067: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0xFB071: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0xFB159: ('event', 'Codec ECCA0/F4B70/FB0D0/1035A0 increments histogram array+CF8 indexed by decoded type at+2E0, after bitstream feature flag+71C test; counts parsed block types, not elapsed ticks.'),
    0x102BBB: ('event', 'Codec error branch sets object+B80=1, increments error total+D0C, returns -1 (or jumps to shared exit); only decoder failure, not unconditional timer.'),
    0x103020: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0x103381: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0x103537: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0x103541: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0x103627: ('event', 'Codec ECCA0/F4B70/FB0D0/1035A0 increments histogram array+CF8 indexed by decoded type at+2E0, after bitstream feature flag+71C test; counts parsed block types, not elapsed ticks.'),
    0x1036D6: ('event', 'Codec variable-length lookup returns sentinel -80; failure branch increments object+D0C error count then rejoins parser. Other path consumes/refills bits; one per invalid code, not time.'),
    0x1037D6: ('event', 'Codec variable-length lookup returns sentinel -80; failure branch increments object+D0C error count then rejoins parser. Other path consumes/refills bits; one per invalid code, not time.'),
    0x10A8FF: ('event', 'Codec error branch sets object+B80=1, increments error total+D0C, returns -1 (or jumps to shared exit); only decoder failure, not unconditional timer.'),
    0x10AD84: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0x10AD8C: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0x10B253: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0x10B25D: ('setup', 'Not executable data: inline codec dispatch/lookup tables after routine returns are linear-decoded as writes, with impossible huge displacements or repeated address words/byte ramps. No instruction/update at this candidate.'),
    0x10CB9B: ('setup', '10C890 image interpolation writes rounded spatial average to output byte+1; source old byte plus blended neighbor is rounded by add1/shifts (10CB8E-10CB9B), not a time counter.'),
    0x119E50: ('setup', 'Not executable data: inline117EF0 dispatch table consists of repeated RVA words around119E40; linear decode creates huge-displacement byte increment.'),
    0x126573: ('setup', 'Leaf12654C releases a handle slot: computes index by dividing offset by stride[rcx], verifies allocation bitmap byte, clears it, decrements live handle count owner+8.'),
    0x1281CC: ('setup', 'Leaf1281B0 removes first linked free/heap node through [rcx], updates forward/back pointers, increments E68EE4 allocation/pop statistic; heap operation, not elapsed time.'),
    0x12AA06: ('setup', '12A90C RBP=entryRSP-5F. RBP+67 stack local_res8 counts matched/scanned stream queues; increments while pointer advances10 bytes and index compares against configured stream count.'),
    0x12B89D: ('setup', 'Leaf12B884 sets library version/string pointer E68F78, then advances global E68F70 pointer by4. Initialization cursor arithmetic, not integer lifetime timer.'),
    0x13F79A: ('setup', "RBP aliases this function's stack frame; a bounded local traversal/index, not retained animation time"),
    0x13F7A0: ('setup', "RBP aliases this function's stack frame; a bounded local traversal/index, not retained animation time"),
    0x142973: ('event', 'SaveDataManager request ring: advance one of sixteen entries after submitting or completing a save operation (142890 threadUpdate, callback and semaphore guards)'),
    0x1429E6: ('event', 'SaveDataManager request ring: advance one of sixteen entries after submitting or completing a save operation (142890 threadUpdate, callback and semaphore guards)'),
    0x142A56: ('event', 'SaveDataManager request ring: advance one of sixteen entries after submitting or completing a save operation (142890 threadUpdate, callback and semaphore guards)'),
    0x142C53: ('event', 'SaveDataManager request ring: advance one of sixteen entries after submitting or completing a save operation (142890 threadUpdate, callback and semaphore guards)'),
    0x142DC4: ('event', 'SaveDataManager request ring: advance one of sixteen entries after submitting or completing a save operation (142890 threadUpdate, callback and semaphore guards)'),
    0x142EE3: ('event', 'SaveDataManager request ring: advance one of sixteen entries after submitting or completing a save operation (142890 threadUpdate, callback and semaphore guards)'),
    0x1431B1: ('event', 'SaveDataManager request ring: advance one of sixteen entries after submitting or completing a save operation (142890 threadUpdate, callback and semaphore guards)'),
    0x143424: ('event', 'SaveDataManager request ring: advance one of sixteen entries after submitting or completing a save operation (142890 threadUpdate, callback and semaphore guards)'),
    0x143535: ('event', 'SaveDataManager request ring: advance one of sixteen entries after submitting or completing a save operation (142890 threadUpdate, callback and semaphore guards)'),
    0x14369C: ('event', 'SaveDataManager request ring: advance one of sixteen entries after submitting or completing a save operation (142890 threadUpdate, callback and semaphore guards)'),
    0x1437F5: ('event', 'SaveDataManager request ring: advance one of sixteen entries after submitting or completing a save operation (142890 threadUpdate, callback and semaphore guards)'),
    0x15130D: ('setup', "RBP aliases this function's stack frame; a bounded local traversal/index, not retained animation time"),
    0x160289: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x16B5E6: ('setup', "RBP aliases this function's stack frame; a bounded local traversal/index, not retained animation time"),
    0x16E978: ('per_tick', 'Retained per-tick elapsed/UV/flipbook/emission phase; fps_followups12.spec supplies its count row (and emission gate where zero triggers an event)'),
    0x16F624: ('event', 'Celestial brush: append one recorded point to 803650, increment 7E71E4 once per accepted point; recorded-point counts must retain the sampling cadence'),
    0x173570: ('setup', "RBP aliases this function's stack frame; a bounded local traversal/index, not retained animation time"),
    0x177CB5: ('event', 'Brush recognition loop: RBP points at the matched-stroke result count, incremented once per accepted component while iterating recorded strokes'),
    0x177CC4: ('event', 'Brush recognition loop: RBP points at the matched-stroke result count, incremented once per accepted component while iterating recorded strokes'),
    0x177E95: ('setup', "RBP aliases this function's stack frame; a bounded local traversal/index, not retained animation time"),
    0x17A88B: ('setup', "RBP aliases this function's stack frame; a bounded local traversal/index, not retained animation time"),
    0x17DBE7: ('event', 'Brush result queue 891930: wrap at 32 once per enqueued result in the bounded stroke loop (17DB80..17DBF8)'),
    0x18575F: ('current_tick', 'cPad::Pad_play: index the next 32-byte recorded input sample per playback tick; pairs with recording each simulation tick, not an animation-duration counter'),
    0x1895AC: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x1A9BD2: ('event', 'esp creation acceptance callback 1A9BA0: 9A6B40 counts accepted effects (source type at +138/+18C <=1); exceeding the population budget invokes 18DEB0 to shed one'),
    0x1AEC8B: ('setup', "RBP aliases this function's stack frame; a bounded local traversal/index, not retained animation time"),
    0x1B0490: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x1C10AC: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x1C10B4: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x1C10D8: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x1C10E0: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x1D0570: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x1D1C20: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x206579: ('event', 'Insert one pointer into a free slot in a 32-element list, then increment its population; returns immediately'),
    0x211A36: ('family', 'frame_gates.h 2119F5 widens the fc &1 guard of this four-frame UV cycle; one increment per stock two-frame interval'),
    0x211E11: ('event', 'cDefiniteHeap::alloc succeeded: decrement free-slot population and update its low-water mark, then construct the allocated object'),
    0x2284C5: ('per_tick', 'Retained per-tick elapsed/UV/flipbook/emission phase; fps_followups12.spec supplies its count row (and emission gate where zero triggers an event)'),
    0x22BFE6: ('per_tick', 'Retained per-tick elapsed/UV/flipbook/emission phase; fps_followups12.spec supplies its count row (and emission gate where zero triggers an event)'),
    0x23B659: ('event', 'Insert one pointer into a free slot in a 32-element list, then increment its population; returns immediately'),
    0x23EF8A: ('family', 'world_anims.h count rows at these exact global countdown stores, plus notyet 23EF90/23F0ED, already pace battle reinforcements'),
    0x23F0E7: ('family', 'world_anims.h count rows at these exact global countdown stores, plus notyet 23EF90/23F0ED, already pace battle reinforcements'),
    0x24AA87: ('event', 'em02 24AA60 chooses state 1B01/1C01 and toggles +14AA once per selected action'),
    0x24AAA3: ('event', 'em02 24AA60 chooses state 1B01/1C01 and toggles +14AA once per selected action'),
    0x25185E: ('event', 'em0b 2516D0 chooses its next action/state and advances the eight-entry action pattern; not elapsed ticks'),
    0x273778: ('per_tick', 'Retained per-tick elapsed/UV/flipbook/emission phase; fps_followups12.spec supplies its count row (and emission gate where zero triggers an event)'),
    0x276CC0: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x2878E7: ('family', "frame_gates.h 287892 widens the four-frame material cycle's fc &1 guard"),
    0x287AF9: ('family', "frame_gates.h 287AA4 widens this four-frame UV cycle's fc &1 guard"),
    0x287BE3: ('family', "frame_gates.h 287B8E widens this four-frame UV cycle's fc &1 guard"),
    0x288189: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x288198: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x293C72: ('event', 'em initialization 293A90 assigns alternating starting phase 0/300 to each newly constructed actor (9C47DC), then sets state1'),
    0x2A4F5C: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x2AB050: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x2AC781: ('event', 'em60 2AC4D0 phase0 changes +E36 to1 before incrementing 9C47E4: number of actors starting the action, compared with group population'),
    0x2B9B99: ('event', 'em61 2B9AD0 picks its next state (7/D/E) and advances a four-entry action pattern'),
    0x2D8815: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x2D8D97: ('per_tick', 'Retained per-tick elapsed/UV/flipbook/emission phase; fps_followups12.spec supplies its count row (and emission gate where zero triggers an event)'),
    0x2F1290: ('setup', 'Unreferenced one-instruction leaf increments the state byte +E34, not a duration; isolated after return/int3'),
    0x2F3D8D: ('setup', "RBP aliases this function's stack frame; a bounded local traversal/index, not retained animation time"),
    0x302E20: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x304E40: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x3368C3: ('per_tick', 'Retained per-tick elapsed/UV/flipbook/emission phase; fps_followups12.spec supplies its count row (and emission gate where zero triggers an event)'),
    0x344940: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x3449C0: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x35B2D2: ('setup', 'objScroll init 35B1E0 temporarily increments then restores frameCounter B6AC20 around material initialization loops; no elapsed tick'),
    0x35B308: ('setup', 'objScroll init 35B1E0 temporarily increments then restores frameCounter B6AC20 around material initialization loops; no elapsed tick'),
    0x363900: ('event', 'Unused leaf advances a script/sequence index +14D2, clears +14D3 and loads the next RVA from +14D8; no time accumulation'),
    0x3763E8: ('event', '3763D0 appends an (RCX,RDX) pair to a registration array using byte B6B300; one increment per registration call'),
    0x37D360: ('setup', "RBP aliases this function's stack frame; a bounded local traversal/index, not retained animation time"),
    0x37D368: ('setup', "RBP aliases this function's stack frame; a bounded local traversal/index, not retained animation time"),
    0x37D740: ('setup', "RBP aliases this function's stack frame; a bounded local traversal/index, not retained animation time"),
    0x37D748: ('setup', "RBP aliases this function's stack frame; a bounded local traversal/index, not retained animation time"),
    0x385A3F: ('family', 'memory_timers.h contains exact sub word [rcx+E3C],1 at385A3F; countdown and JNE flags already paced'),
    0x3A3468: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x3B03AC: ('event', 'Player resource transaction: add signed amount (here -200) to global B4DF94, clamp at its bound; once at the action/state transition or explicit resource helper call'),
    0x3C6DA5: ('event', 'Player resource transaction: add signed amount (here -200) to global B4DF94, clamp at its bound; once at the action/state transition or explicit resource helper call'),
    0x3CAD4C: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x3CD8E9: ('event', 'Player resource transaction: add signed amount (here -200) to global B4DF94, clamp at its bound; once at the action/state transition or explicit resource helper call'),
    0x3DF1F1: ('event', 'cDefiniteHeap::alloc succeeded: decrement free-slot population and update its low-water mark, then construct the allocated object'),
    0x3F9F38: ('event', 'Append/count HUD notification entries (+116/+DC); +7A counts duplicate notifications of the same key, not frames'),
    0x3F9F9A: ('event', 'Append/count HUD notification entries (+116/+DC); +7A counts duplicate notifications of the same key, not frames'),
    0x3F9F9F: ('event', 'Append/count HUD notification entries (+116/+DC); +7A counts duplicate notifications of the same key, not frames'),
    0x3F9FA9: ('event', 'Append/count HUD notification entries (+116/+DC); +7A counts duplicate notifications of the same key, not frames'),
    0x3FAA6F: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x3FAAB9: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x3FAAD0: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x3FAAE0: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x3FAB80: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x3FABBB: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x3FD130: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x3FD137: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x3FD150: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x3FD159: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x3FD290: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x3FD297: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x3FF325: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x406250: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x407390: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x4149B0: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x417C38: ('event', 'Destroy/release one UI resource: decrement B1F5F0 references, free shared data when the last reference leaves'),
    0x418810: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x41C59E: ('event', 'Files/menu four-entry ring selection: decrement/increment +16A while changing the selected entry and rebuilding the panels'),
    0x41C7C1: ('event', 'Files/menu four-entry ring selection: decrement/increment +16A while changing the selected entry and rebuilding the panels'),
    0x42437B: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x42C652: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x4385E9: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x4385ED: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x439BCC: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x439BFB: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x439C2A: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x439C40: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x43A6FF: ('event', 'Explicit player resource/score transaction helpers: add caller-supplied amount (43AA70 adds one per collection) and clamp at min/max; not an elapsed-time update'),
    0x43A76D: ('event', 'Explicit player resource/score transaction helpers: add caller-supplied amount (43AA70 adds one per collection) and clamp at min/max; not an elapsed-time update'),
    0x43A8C6: ('event', 'Explicit player resource/score transaction helpers: add caller-supplied amount (43AA70 adds one per collection) and clamp at min/max; not an elapsed-time update'),
    0x43A909: ('event', 'Explicit player resource/score transaction helpers: add caller-supplied amount (43AA70 adds one per collection) and clamp at min/max; not an elapsed-time update'),
    0x43AA7F: ('event', 'Explicit player resource/score transaction helpers: add caller-supplied amount (43AA70 adds one per collection) and clamp at min/max; not an elapsed-time update'),
    0x43B13A: ('setup', '43B0E0 resource-loading state machine: seven poll invocations before checking asynchronous scene/audio load readiness; callers may poll several times per tick, not a visual duration'),
    0x43B3DD: ('event', 'Explicit player resource/score transaction helpers: add caller-supplied amount (43AA70 adds one per collection) and clamp at min/max; not an elapsed-time update'),
    0x43B439: ('event', 'Explicit player resource/score transaction helpers: add caller-supplied amount (43AA70 adds one per collection) and clamp at min/max; not an elapsed-time update'),
    0x44C57F: ('event', 'Audio/control state bits +70 rebuilt as ((old&2)*2)|1; add eax,eax shifts bits, not a count step'),
    0x44FEB9: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x44FEBD: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x44FEC1: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x44FEC5: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x450C64: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x450C6C: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x45107F: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x455361: ('event', '455350 generates a nonzero serial B57A24 for audio requests; called on request submission, not as a clock'),
    0x45C015: ('setup', "RBP aliases this function's stack frame; a bounded local traversal/index, not retained animation time"),
    0x45DA01: ('setup', "RBP aliases this function's stack frame; a bounded local traversal/index, not retained animation time"),
    0x466EFE: ('setup', "RBP aliases this function's stack frame; a bounded local traversal/index, not retained animation time"),
    0x488228: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x4A4000: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x4A9872: ('setup', 'Unused standalone leaf copy after a return/int3 boundary: no direct incoming call/jump, .rdata/.data function pointer, RIP address-taking reference or export. The reachable implementations are in the preceding functions, separately censused'),
    0x4B6ECC: ('setup', "Animation-channel decoder advances the caller's serialized key cursor by eight bytes per decoded channel; not elapsed ticks"),
    0x4B72C0: ('setup', "Animation-channel decoder advances the caller's serialized key cursor by eight bytes per decoded channel; not elapsed ticks"),
    0x4B74DC: ('setup', "Animation-channel decoder advances the caller's serialized key cursor by eight bytes per decoded channel; not elapsed ticks"),
    0x4B758A: ('setup', "Animation-channel decoder advances the caller's serialized key cursor by eight bytes per decoded channel; not elapsed ticks"),
    0x4B76F0: ('setup', "Animation-channel decoder advances the caller's serialized key cursor by eight bytes per decoded channel; not elapsed ticks"),
    0x4BAC6D: ('current_tick', 'System readiness confirmation: count three consecutive samples of readiness/menu/resource guards before a control-state handoff, resetting on any failed sample; reflects current scheduler samples'),
    0x4BAEC0: ('current_tick', 'System readiness confirmation: count three consecutive samples of readiness/menu/resource guards before a control-state handoff, resetting on any failed sample; reflects current scheduler samples'),
    0x4C5C2D: ('per_tick', 'Stage callback elapsed counter, registered through48C8C0/136400 and called each tick through48BE20/48C120/48C280/135940; paced count plus its old-count15 sound comparison gate (fps_followups12.spec).'),
    0x4C5FE1: ('per_tick', 'Stage callback elapsed counter, registered through48C8C0/136400 and called each tick through48BE20/48C120/48C280/135940; paced count plus its old-count15 sound comparison gate (fps_followups12.spec).'),
    0x4D03A1: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x4D03A5: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x4D03A9: ('setup', 'Linear disassembly decoded a switch/RVA table or instruction interior; the surrounding bytes are data, not a reachable counter instruction'),
    0x51F7A1: ('family', '51F5C0 loop resumes through task_waits.h wait(1) at51F916; both global counters already advance at the paced loop cadence'),
    0x51F8D0: ('family', '51F5C0 loop resumes through task_waits.h wait(1) at51F916; both global counters already advance at the paced loop cadence'),
    0x5A7B36: ('per_tick', 'Retained per-tick elapsed/UV/flipbook/emission phase; fps_followups12.spec supplies its count row (and emission gate where zero triggers an event)'),
    0x65C62B: ('setup', 'MSVC _Init_thread_footer: thread-safe static initialization epoch and TLS bookkeeping, under the runtime lock'),
}


def canonical(reg):
    for wide, aliases in {
        "rax": ("rax", "eax", "ax", "al", "ah"),
        "rbx": ("rbx", "ebx", "bx", "bl", "bh"),
        "rcx": ("rcx", "ecx", "cx", "cl", "ch"),
        "rdx": ("rdx", "edx", "dx", "dl", "dh"),
        "rsi": ("rsi", "esi", "si", "sil"),
        "rdi": ("rdi", "edi", "di", "dil"),
        "rbp": ("rbp", "ebp", "bp", "bpl"),
        "rsp": ("rsp", "esp", "sp", "spl"),
    }.items():
        if reg in aliases:
            return wide
    return re.sub(r"[dwb]$", "", reg) if reg.startswith("r") else reg


def memory(op, at, size):
    mo = MEM.search(op)
    if not mo:
        return None
    expr = mo[1]
    if re.search(r"\b(?:[re]?sp)\b", expr):
        return None
    rip = re.fullmatch(r"rip(?: ([+-]) (0x[0-9a-f]+))?", expr)
    if rip:
        disp = int(rip[2], 16) * (-1 if rip[1] == "-" else 1) if rip[2] else 0
        expr = "absolute:%X" % (rc.BASE + at + size + disp)
    return expr


def scan(insns):
    found = {}
    totals = collections.Counter()
    for k, (at, mn, ops, size) in enumerate(insns):
        args = ops.split(", ")
        if mn in ("inc", "dec", "add", "sub") and memory(args[0], at, size) and \
                (mn in ("inc", "dec") or len(args) == 2 and IMM.fullmatch(args[1])):
            totals["memory"] += 1
            found[at] = dict(site=at, load=at, step=at, shape="memory", field=memory(args[0], at, size))
        if mn not in ("mov", "movzx", "movsx", "movsxd") or len(args) != 2 or \
                not REG.fullmatch(args[0]):
            continue
        field = memory(args[1], at, size)
        if field is None:
            continue
        # Track copies of the loaded value and the instruction that steps it.
        values = {canonical(args[0]): None}
        for a, m, o, sz in insns[k + 1:k + 7]:
            if m.startswith("j") or m.startswith("loop") or m in ("call", "ret", "retf", "int3", "ud2"):
                break
            aa = o.split(", ")
            if m == "mov" and len(aa) == 2 and memory(aa[0], a, sz) == field and \
                    REG.fullmatch(aa[1]) and values.get(canonical(aa[1])) is not None:
                totals["load_step_store"] += 1
                prior = found.get(a)
                found[a] = dict(site=a, load=at, step=values[canonical(aa[1])],
                                shape="load_step_store", field=field)
                if prior:
                    found[a]["shape"] += "+memory"
                break
            if not aa or not REG.fullmatch(aa[0]):
                continue
            dst = canonical(aa[0])
            if m in ("inc", "dec") and dst in values:
                values[dst] = a
            elif m in ("add", "sub") and len(aa) == 2 and dst in values:
                values[dst] = a
            elif m == "lea" and len(aa) == 2:
                mo = MEM.search(aa[1])
                le = re.findall(r"\b(?:r[0-9]+[dwb]?|[re]?[abcd]x|[re]?[sdb]i|[re]?bp)\b", mo[1]) if mo else []
                if any(canonical(reg) in values for reg in le):
                    values[dst] = a
                else:
                    values.pop(dst, None)
            elif m == "mov" and len(aa) == 2 and REG.fullmatch(aa[1]) and canonical(aa[1]) in values:
                values[dst] = values[canonical(aa[1])]
            elif m in ("mov", "movzx", "movsx", "movsxd", "pop") or m == "xor" and len(aa) == 2 and aa[0] == aa[1]:
                values.pop(dst, None)
    return found, totals


def candidates():
    cache = pickle.load(open(rc.CACHE, "rb"))
    seen = set()
    for row in csv.DictReader(open(os.path.join(DOCS, "sites.csv"), encoding="utf-8")):
        seen.update(int(row[key], 16) for key in ("site", "load") if row[key])
    found, totals = scan(cache["insns"])
    outside = {a: r for a, r in found.items() if a not in seen}
    return cache, outside, totals


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--csv")
    ap.add_argument("--all", action="store_true", help="also print reviewed sites")
    args = ap.parse_args()
    cache, found, totals = candidates()
    src = open(rc.DECOMP, encoding="utf-8", errors="replace").read()
    starts = sorted(int(m[1], 16) for m in rc.FUNC_HDR.finditer(src))
    ins = {a: (m, o) for a, m, o, _ in cache["insns"]}
    rows = {int(r["site"], 16): r["kind"] for r in csv.DictReader(
        open(os.path.join(DOCS, "world_anims.csv"), encoding="utf-8")) if r["status"] == "selected"}
    out, bad = [], []
    for a, r in sorted(found.items()):
        verdict, why = REVIEWED.get(a, ("", ""))
        kind = next((rows[x] for x in (a, r["load"], r["step"]) if x in rows), "")
        fn = starts[max(0, bisect.bisect_right(starts, a) - 1)]
        rec = dict(site="%X" % a, function="%X" % fn, load="%X" % r["load"],
                   step="%X" % r["step"], shape=r["shape"], field=r["field"],
                   instruction="%s %s" % ins[a], row=kind, verdict=verdict, evidence=why)
        out.append(rec)
        if verdict not in {"setup", "event", "family", "current_tick", "per_tick"} or \
                not why or verdict == "per_tick" and not kind:
            bad.append(a)
        if args.all or a in bad:
            print("%(site)s in %(function)s load %(load)s step %(step)s: %(instruction)s "
                  "[%(verdict)s %(row)s] %(evidence)s" % rec)
    print("shapes before census exclusion: %s" % dict(totals))
    print("uncensused: %d; verdicts %s; rows %d; open %d" % (
        len(out), dict(collections.Counter(r["verdict"] for r in out)),
        sum(bool(r["row"]) for r in out), len(bad)))
    if args.csv:
        with open(args.csv, "w", encoding="utf-8", newline="") as fo:
            wr = csv.DictWriter(fo, fieldnames=list(out[0]))
            wr.writeheader()
            wr.writerows(out)
    return int(args.check and bool(bad))


if __name__ == "__main__":
    sys.exit(main())
