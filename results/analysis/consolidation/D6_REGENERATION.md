# D6 regeneration (Gate C3 session, Phase 2)

Computation only: no runs, no driver interaction, no report or claim edited. Script: `tests/d6_regenerate.py` (reuses
`tests/gate_e07_accuracy_analysis.py` and `tests/gate_e08_index_drift_analysis.py`; the other rows are the reports' own recorded
commands turned into code). Outputs (small, committed): `results/analysis/derived/d6_row*.csv` and
`results/analysis/derived/d6_comparison.csv` (one row per number: derived value, prose value, source, MATCH/MISMATCH).
The raw gitignored files were read, never committed. Evidence ids: `D6.rNN.*` in `EVIDENCE_EXTRACT.md` (157 rows; 418 in all).

**Headline: 157 comparisons across the ten rows with raw input on disk: 154 MATCH, 3 MISMATCH.** Rows 11-13 (events) are not data and are not regenerated.

| row | number(s) | derived CSV | committed script reused | result |
|---|---|---|---|---|
| 1 | E0 trace entries 276,961 / 207,564; ratios 11.7 / 2.1 | `d6_row01_02_trace_entries.csv` | none (size / 8) | all MATCH. Needed the right files: `results/phaseB2/gate3_interleaved/c3_bench_*_trace.bin` (not the `t_a1_worker` copies, which hold 277,407 / 207,616). The coalesced-fault counts (3,237,375 / 445,721) are T4 figures quoted from `GATE_T4_REPORT.md`; they cannot be regenerated from a raw file |
| 2 | 2,953,867 / 483,896 | same | none | MATCH (trace entries of the fresh collections; the `demand_faults` counter itself is prose) |
| 3 | 442/56, 23/56, 1/57, 442/450 | `d6_row03_oracle_coalesce.csv` | the script's own embedded parse block | all 14 MATCH |
| 4 | 254/256 on both modules; 0.99 | `d6_row04_oracle_probe.csv` | the script's own embedded parse block | MATCH |
| 5 | E0.8 max rank displacement, Spearman, GraphBFS 36,618-38,990, count differences | `d6_row05_06_e08_checks.csv`, `d6_row06_e08_pairs.csv` | `gate_e08_index_drift_analysis.py`, `gate_e07_accuracy_analysis.py` | 10 MATCH, **2 MISMATCH** (below) |
| 6 | forward 98.48% / backward 0.0708%; 51.19%; symmetric 99.9997%; 31.4 -> 47.5 -> 51.7 | same | same | all 36 MATCH |
| 7 | E4 table check 98 / 35,823 vs 96 / 37,992 | `d6_row07_e4_table_check.csv` | none (new script; the original was an inline shell comparison) | all 8 MATCH |
| 8 | "prevented = 0.0000% at every L" | `d6_row08_prevented.csv` | none | prevented = 0.0000% and usefulness = 100.0000% reproduce at every L on both workloads; **1 MISMATCH** (below) |
| 9 | corrected ceilings 0.08-7.94%, 7.25%; window share | `d6_row09_ceilings.csv` | `gatec1_decomp_analysis.py` record layout | all 62 MATCH: every cell of the four-convention table on both platforms, and the 0.08-7.94% range |
| 10 | B10 "truncated + rotated" | `d6_row10_b10_trace_capacity.csv` | none | the 7 B10 C4 trace files all hold exactly 1,048,576 entries (the ring capacity), consistent with **truncation**. **Rotation is not regenerated**: it needs the push count (`head mod capacity`), which the file does not contain |

## The three mismatches (both values recorded; no prose corrected)

| row | quantity | derived from the raw file | report prose | source |
|---|---|---:|---:|---|
| 5 | Stencil-24K trace vs **depth=1** replay, max \|rank diff\| | **107** | 105 | `GATE_E0_8_REPORT.md` section 4 table |
| 5 | Stencil-24K trace vs **depth=0** replay, max \|rank diff\| | **105** | 107 | same table |
| 8 | Stencil-24K L=1 depth=1, logged predictions | **141,484** | 140,909 | `GATE_E0_9_REPORT.md` section 4 |

- **Rows 5, the two displacement values** are the same two numbers swapped between the depth=1 and depth=0 rows. In the same table the
  forward-set and backward-set values, the reduced exact-match counts (25,134 for depth=1, 25,891 for depth=0) and the Spearman values do
  agree with the data under the same file-to-depth mapping, so the swap is in one column of the report table or in the mapping of the
  `replay_order*.bin` files to depth for that column; I did not determine which. Neither number changes any conclusion (every other place
  in the reports says "about 105-107").
- **Row 8's count** compares an E0.9a figure with the raw files of E0.9a-2, which is a different run; the two need not agree. The usefulness
  (100%) and prevented (0%) results do not depend on it.

## Caveats

- The row 5 Spearman comparison uses a tolerance of 6e-8 because the prose gives 10 significant digits for Stencil and 7 for GraphBFS; the
  derived values are in `d6_row05_06_e08_checks.csv` at full precision.
- The mapping of `*_replay_order.bin` to depth=1 and `*_replay_order_depth0.bin` to depth=0 is from the file names; it is consistent with every
  value except the displacement column (above).
- Row 1's and row 9's wall-clock denominators are the committed paired-time CSVs (`wall_s`, rounded to 10 ms in the source).
