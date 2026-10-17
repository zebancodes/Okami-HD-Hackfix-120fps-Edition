# Integer updates outside the original census

Static review, 2026-10-11, against installed main.dll SHA1
`703d292ab2cb50cc9e237e44722dec51d956b79c`. Addresses are RVAs.

`tools/find_uncensused.py` reads the matching instruction cache, resolves RIP
operands before comparing load/store addresses, follows register copies for
six following instructions, and stops at control transfers. It excludes RSP
addresses; RBP is retained conservatively because it often holds objects.
True stack aliases and non-code decoding artifacts receive explicit setup
reviews. This broader scan is not numerically identical to the original
one-off scan: it finds 4,502 memory updates and 502 load/step/store shapes
before census exclusion. Their union outside the site/load columns of
`sites.csv` is **302 candidates**.

All 302 have evidence in the tool's `REVIEWED` dictionary:

| Verdict | Sites |
|---|---:|
| Library/setup, including stack aliases and non-code artifacts | 211 |
| Once per event | 70 |
| Existing pacing family | 9 |
| Current tick by design | 3 |
| Per-tick counter requiring a row | 9 |

The 149 low-address library candidates have additional evidence in
`uncensused_library12.txt`. Unreferenced leaf verdicts are bounded static
reachability findings, not claims that execution was observed. Resource
references, list sizes, event serials, brush points, and animation loop
counts remain event counts. Recorded pad samples and readiness confirmation
samples retain their current-tick behavior.

The nine new counts are:

| Store | Retained state | Group |
|---|---|---|
| `16E978` | Brush idle gap `896BEC`, reset to 30 on a new point | player |
| `22BFE6` | Camera-facing UV phase `+1158`, modulo 512 | objects |
| `3368C3` | hm8f UV phase `+1310`, modulo 512 | objects |
| `5A7B36` | utd8 UV phase `+115E`, modulo 512 | objects |
| `273778` | em2b eight-frame material phase `+1440`, modulo 16 | actor |
| `2D8D97` | em8c material phase `+1234`, modulo 4 | actor |
| `2284C5` | type892 emission phase `+10E6`, modulo 8 | objects |
| `4C5C2D` | Stage sound delay `B6D6DC` | actor |
| `4C5FE1` | Stage sound delay `B6D6E4` | actor |

Compare gates at `22848B`, `4C5C33`, and `4C5FE7` prevent repeated emissions
or sounds while a count is held. Their held paths reach only the matching
count row or return; no other family's enabled state is assumed. The brush
gap's nonpositive side only ORs a flag on the last point, so it has no gate;
it retains the up-to-25-ms resting-side tolerance at 120. Brush point append
`16F624` and input sampling remain unchanged. `kJogParams` and
`mode_constants.h` were checked; this gap does not consume their movement
constants. See `script_seconds12.md` for the brush and stage call chains.

All rows are archived in `fps_followups12.spec`. The audit's `--check` rejects
missing/invalid reviews and a per-tick verdict without a selected row. It is
part of `run_suite.sh`. Synthetic checks covered RIP identity, register
copies, six-instruction limits, mismatched stores, stack exclusion, and
branch/call/return rejection. Negative controls removed a review and marked
an unpatched library counter per-tick; both correctly failed `--check`.
