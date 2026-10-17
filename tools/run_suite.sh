#!/bin/bash
# The full offline suite for the built .build/bin/dinput8.dll, the one each
# round runs before a deploy. The runs are independent (each copies the DLL
# into a temp dir of its own), so up to JOBS of them run at once; the world
# pass at 64 states is the longest.
# Every verifier copies the DLL when it starts and the surveys import
# gen_world_anims.MANIFEST, so do not rebuild .build or edit tools/ while it
# runs.
#
#     bash tools/run_suite.sh SEED [OUT_DIR] [JOBS]
#
# OUT_DIR/summary.txt gets the DLL's sha1, then one line per run in a fixed
# order: PASS when it met its expectation (a --break must fail), FAIL when not,
# and DONE at the end. Each run's output is OUT_DIR/<name>.log.
set -u
SEED=${1:?usage: run_suite.sh SEED [OUT_DIR] [JOBS]}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT=${2:-"$ROOT/.suite"}
JOBS=${3:-$(( $(nproc) > 3 ? $(nproc) - 2 : 1 ))}
PY="$ROOT/.venv/Scripts/python"
BREAK_STATES=8  # the world breaks only have to fail; 8 states is what earlier rounds' counts used
OUT=$(realpath -m "$OUT")
case "$OUT" in
    "$ROOT"/.suite*) ;;
    *) echo "suite output must be under $ROOT with a .suite name" >&2; exit 2 ;;
esac
if [ -e "$OUT" ]; then
    echo "suite output already exists: $OUT" >&2
    exit 2
fi
mkdir -p "$OUT/res"
cd "$ROOT"
t_start=$(date +%s)
SHA=$(sha1sum .build/bin/dinput8.dll)  # what every run copies

NAMES=()
job() {  # expect(pass|fail) name args...: runs in the background, at most JOBS at once
    local expect=$1 name=$2
    shift 2
    NAMES+=("$name")
    while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do wait -n; done
    (
        t0=$(date +%s)
        "$PY" "$@" > "$OUT/$name.log" 2>&1
        rc=$?
        ok=FAIL
        if [ "$expect" = pass ] && [ $rc -eq 0 ]; then ok=PASS; fi
        if [ "$expect" = fail ] && [ $rc -ne 0 ]; then ok=PASS; fi
        echo "$ok $name (rc $rc, expect $expect, $(( $(date +%s) - t0 )) s)" > "$OUT/res/$name"
    ) &
}

# the longest first, so the rest fill in around them
job pass world_anims tools/verify_world_anims.py --states 64 --seed "$SEED"
for b in scale root gate literal mask2 smode intn; do
    job fail world_anims_break_$b tools/verify_world_anims.py --states $BREAK_STATES \
        --seed "$SEED" --break $b
done
job pass cave_pressure tools/verify_cave_pressure.py
job fail cave_pressure_break_old tools/verify_cave_pressure.py --break old
job pass check_patch_sites tools/check_patch_sites.py
job pass player_anim_rates tools/verify_player_anim_rates.py
for b in walk reg; do
    job fail player_anim_rates_break_$b tools/verify_player_anim_rates.py --break "$b"
done
job pass chance_rolls tools/verify_chance_rolls.py
job fail chance_rolls_break_gate tools/verify_chance_rolls.py --break gate
job pass quakes tools/verify_quakes.py --seed "$SEED"
for b in retention context; do
    job fail quakes_break_$b tools/verify_quakes.py --seed "$SEED" --break "$b"
done
job pass chance_chains tools/verify_chance_chains.py
job fail chance_chains_break_gate tools/verify_chance_chains.py --break gate
job pass chance_decisions tools/verify_chance_decisions.py
for b in em16 em85 em89 attempts; do
    job fail chance_decisions_break_$b tools/verify_chance_decisions.py --break "$b"
done
job pass forward_movers tools/verify_forward_movers.py
for b in missing double; do
    job fail forward_movers_break_$b tools/verify_forward_movers.py --break "$b"
done
job pass heading_movers tools/verify_heading_movers.py
job pass vector_movers tools/verify_vector_movers.py
for b in missing double; do
    job fail heading_movers_break_$b tools/verify_heading_movers.py --break "$b"
    job fail vector_movers_break_$b tools/verify_vector_movers.py --break "$b"
done
job fail heading_movers_break_spin tools/verify_heading_movers.py --break spin
for s in mode_reads turn_limits turn_steps flag_reads double_pacing event_counters; do
    job pass survey_$s tools/survey_$s.py
done
job pass survey_frame_events tools/frame_events.py --check
job pass early_countdowns tools/early_countdowns.py --check
job pass uncensused tools/find_uncensused.py --check
job pass trace_steps tools/trace_steps.py --check
job fail trace_steps_break_rows tools/trace_steps.py --check --break rows
job pass step_limits tools/step_limits.py --check
job fail step_limits_break_limsq tools/step_limits.py --check --break limsq
job pass task_waits tools/verify_task_waits.py
for b in n cap loop hist; do
    job fail task_waits_break_$b tools/verify_task_waits.py --break $b
done
for v in menu_transitions const_pools frame_clocks day_clock integer_skips shadow_mode \
         stick_drift brush_watch loading_watch turn_callers stubs turn_stub install_failure \
         fault_guard draw_distance enemy_watch; do
    job pass $v tools/verify_$v.py
done
job fail enemy_watch_break_sample tools/verify_enemy_watch.py --break sample
wait

{
    echo "$SHA"
    for n in "${NAMES[@]}"; do cat "$OUT/res/$n" 2>/dev/null || echo "FAIL $n (no result)"; done
    echo "DONE in $(( $(date +%s) - t_start )) s, $JOBS at a time"
} > "$OUT/summary.txt"
grep -c "^PASS" "$OUT/summary.txt" | xargs -I{} echo "{} of ${#NAMES[@]} met their expectation"
