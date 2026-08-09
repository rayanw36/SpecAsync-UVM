#!/usr/bin/env python3
"""Task 0 -- build results/figures/exclusion_manifest.csv and .md.

Canonical, hand-curated from a full read of every gate/decision report in the repo
(results/phaseB/gate_reports/gate{0-5}_*.md, results/phaseB1/GATE_{A,B,C,D}_*.md +
PIPELINE_VALIDATION.md + DATAFLOW_READBACK.md, results/phaseB2/{GATE1-4,DECISION}.md,
results/phaseC/PHASEC_REPORT.md, results/phaseB/SUMMARY.md, results/summary/cost_benefit.md,
driver/PIPELINE_FIXES.md). This is the single source of truth for exclusions; figure
scripts load the CSV and must not hardcode exclusion logic.

exclusion_type:
  demonstrated -- the value was itself rerun under a corrected protocol and changed.
  inferred     -- the value shares a protocol/bug with a demonstrated artifact but was
                  never itself rerun.

Two hypotheses the brief raised that were TESTED AND REJECTED are deliberately NOT rows
here: (1) "hit counter never fires" (GATE_A_report.md -- counter is sound, 99.2% positive
control); (2) "oracle replay is O(n^2)" (GATE_B_diagnosis.md -- replay was already O(1)).
Neither invalidates a measured value; both are dead ends, not exclusions.
"""
import csv
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_CSV = REPO / "results/figures/exclusion_manifest.csv"
OUT_MD = REPO / "results/figures/EXCLUSION_MANIFEST.md"

ORACLE_EV = ("results/phaseB1/GATE_B_diagnosis.md; driver/PIPELINE_FIXES.md; "
             "results/phaseB1/PIPELINE_VALIDATION.md; "
             "results/phaseB/gate_reports/gate4_oracle.md")
ORACLE_REASON = ("Oracle cursor desync: specasync_oracle_next_addr() was consulted once "
                  "per service batch (advancing the cursor by 1) while the fault trace was "
                  "recorded once per demand fault, so a batch coalescing k faults consumed "
                  "k trace entries but advanced the cursor by 1 -- after the first "
                  "multi-fault batch every oracle prediction points at an already-faulted "
                  "page (permanent desync). Compounded by no ASLR control (no setarch -R), "
                  "so cudaMallocManaged's re-randomized VA base broke absolute-VA trace "
                  "replay alignment even when the cursor was right. Fixed by "
                  "specasync_oracle_next_addr_n(consumed) + setarch -R for collect/replay.")

# The 6 (benchmark, size) cells that received a p4/oracle row in Phase B
# (results/phaseB/gate_reports/gate4_oracle.md's oracle sweep table).
ORACLE_CELLS = [
    ("GraphBFS", "23"), ("SGEMM", "24000"), ("STREAM", "268435456"),
    ("Stencil", "24000"), ("Stencil_OvSub", "28300_20_11264"), ("cuFFT", "268435456"),
]

STREAM_CELLS = [("STREAM", "134217728"), ("STREAM", "268435456")]
STREAM_EV = "results/phaseB1/GATE_C_report.md; results/phaseB1/PIPELINE_VALIDATION.md"
STREAM_REASON_DEMO = ("Phase B measured STREAM all-baseline-then-all-treatment (block "
                       "order), giving p1 (adjacent) -8.8% to -8.9% at these two sizes. "
                       "Gate C reran INTERLEAVED (p0->p1->p5 alternating, 40 cycles/policy/"
                       "size, runtime param switch, no reload): the effect vanishes and "
                       "reverses to a +1.5% to +2.05% slowdown (MWU p<1e-4), tracking p5 "
                       "(null worker, no prediction at all) within 0.5% -- a pure "
                       "worker-presence side effect (enqueue + WQ wakeup + VA-space "
                       "read-lock acquisition), not speculation. It does not track hit "
                       "rate. Verdict: 'drop the STREAM speedup claim.'")
STREAM_REASON_INFER = ("Measured under the same all-baseline-then-all-treatment protocol "
                        "as p1 at these two sizes. Gate C's interleaved rerun covered only "
                        "p1 and the p5 null control, not p2/p3, so no corrected value "
                        "exists for p2/p3 here -- excluded by protocol association, not by "
                        "a rerun of p2/p3 itself.")

TIMER_EV = ("results/phaseB1/GATE_C_report.md; results/phaseB2/GATE4_report.md; "
            "results/phaseB1/PIPELINE_VALIDATION.md")
TIMER_REASON = ("T2 and T3 in service_fault_batch() (uvm_gpu_replayable_faults.c) were both "
                 "set to the same ktime_get_ns() call immediately after "
                 "service_fault_batch_dispatch() returned, so the 'residency' phase "
                 "(T2->T3) was identically zero in every Phase B measurement and the "
                 "'metadata' window (T1->T2) silently absorbed the entire dispatch cost -- "
                 "giving the false appearance that metadata lookup was ~99% of service "
                 "time. Fixed in Phase B.2 (Gate 4) by moving T2 to before dispatch; the "
                 "corrected T2->T3 is non-zero (7.83us median, single-fault probe; 3.63us "
                 "median, real stencil-24K) and dispatch (not metadata) dominates CPU time.")

PHASEC_EV = "results/phaseC/PHASEC_REPORT.md"
PHASEC_REASON = ("ring_read_binary() (specasync_debugfs.c) returned to_copy bytes to the "
                  "caller while only writing floor(to_copy/record_size)*record_size bytes "
                  "via copy_to_user; the resulting *ppos drift accumulated to exactly 32 "
                  "bytes by slot 1170, making the Python parser misread record boundaries "
                  "and produce apparently-corrupt decomposition data. The ring push code "
                  "itself was correct throughout. Fixed by snapping to_copy to a multiple "
                  "of record_size before advancing *ppos. These are early Phase C debug "
                  "captures made before that fix, superseded by the clean "
                  "decomp_{stencil_8K,stencil_24K,graphbfs_23,stencil_sweep_*}.csv "
                  "(all regenerated after the fix, same 2026-07-06 15:47-15:49 session).")

rows = []


def add(source_file, benchmark, size, policy, metric, reason, evidence, kind):
    rows.append(dict(source_file=source_file, benchmark=benchmark, size=size, policy=policy,
                      metric=metric, reason=reason, evidence_report=evidence,
                      exclusion_type=kind))


for bench, size in ORACLE_CELLS:
    add("results/phaseB/phaseB_timing.csv", bench, size, "p4", "wall_time",
        ORACLE_REASON, ORACLE_EV, "demonstrated")
    add("results/phaseB/phaseB_telemetry.csv", bench, size, "p4", "hit_rate",
        ORACLE_REASON, ORACLE_EV, "demonstrated")
    add("results/summary/cost_benefit.md", bench, size, "p4", "net_benefit_ns",
        ORACLE_REASON, ORACLE_EV, "demonstrated")

for bench, size in STREAM_CELLS:
    add("results/phaseB/phaseB_timing.csv", bench, size, "p1", "wall_time",
        STREAM_REASON_DEMO, STREAM_EV, "demonstrated")
    for pol in ("p2", "p3"):
        add("results/phaseB/phaseB_timing.csv", bench, size, pol, "wall_time",
            STREAM_REASON_INFER, STREAM_EV, "inferred")

add("results/phaseB/phaseB_telemetry.csv", "ALL", "ALL", "ALL",
    "ph01_median_ns / ph12_median_ns (lock_acq / metadata phase split)",
    TIMER_REASON, TIMER_EV, "demonstrated")
add("results/summary/phase_breakdown.pdf", "ALL", "ALL", "ALL",
    "T0-T1-T2-T3 stacked phase attribution",
    TIMER_REASON, TIMER_EV, "demonstrated")

for fname in ("decomp_24K_inpush.bin", "decomp_noinline_24K.bin",
              "decomp_stencil_24K_diag.bin", "decomp_stencil_24K_diag2.bin",
              "decomp_stencil_8K_smoke.csv"):
    add(f"results/phaseC/{fname}", "Stencil", "24000 or 8000 (diagnostic capture)", "n/a",
        "all decomposition fields (d1-d7, svc, total, num_faults, num_va_spaces, num_blocks)",
        PHASEC_REASON, PHASEC_EV, "demonstrated")

FIELDS = ["source_file", "benchmark", "size", "policy", "metric", "reason",
          "evidence_report", "exclusion_type"]

OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)

demo_n = sum(1 for r in rows if r["exclusion_type"] == "demonstrated")
inferred_n = sum(1 for r in rows if r["exclusion_type"] == "inferred")

md = [
    "# Exclusion manifest",
    "",
    f"Generated by `tools/figures/_build_exclusion_manifest.py`. {len(rows)} rows: "
    f"{demo_n} demonstrated, {inferred_n} inferred.",
    "",
    "`benchmark`/`size`/`policy` of `ALL` is a wildcard: the row applies to every value in "
    "that file/metric, not to one specific cell (used for the T2==T3 timer artifact, which "
    "is file-wide, and the pre-fix Phase C diagnostic captures, which are whole-file).",
    "",
    "Two hypotheses the original brief raised were **tested and rejected** -- they are not "
    "exclusion rows because no measured value turned out to be wrong:",
    "- \"hit counter never fires on the v595 port\" -- `GATE_A_report.md`: counter is sound, "
    "99.2% (254/256) on a deterministic positive control.",
    "- \"oracle replay is O(n^2)\" -- `GATE_B_diagnosis.md`: `specasync_oracle_next_addr()` "
    "was already O(1) (atomic cursor + modulo); the real bug was the desync (below), not scan cost.",
    "",
    "| source_file | benchmark | size | policy | metric | exclusion_type | reason | evidence_report |",
    "|---|---|---|---|---|---|---|---|",
]
for r in rows:
    reason_short = r["reason"][:140] + ("..." if len(r["reason"]) > 140 else "")
    md.append(f"| `{r['source_file']}` | {r['benchmark']} | {r['size']} | {r['policy']} | "
              f"{r['metric']} | **{r['exclusion_type']}** | {reason_short} | "
              f"{r['evidence_report']} |")

OUT_MD.write_text("\n".join(md) + "\n")

print(f"wrote {OUT_CSV} ({len(rows)} rows: {demo_n} demonstrated, {inferred_n} inferred)")
print(f"wrote {OUT_MD}")
