# Phase 2 Changelog

All work lives on branch `claude/specasync-phase2-instrumentation-3r7Jc`.
Phase B = work that requires real hardware (GPU box with Linux 6.14, NVIDIA
Open Kernel Modules v580.95.05 applied via `git lfs pull` + patch).

---

## Priority 5 — Userspace parser + cost-benefit + synthetic validation

**Committed:** Phase 2 P5: userspace parser, cost-benefit tool, synthetic test

### What was done

Created `benchmarks/tools/`:

| File | Purpose |
|------|---------|
| `specasync_parse.py` | Binary log parser. Reads `specasync_log` and `specasync_worker_log` debugfs dumps; outputs CSV + statistics. |
| `cost_benefit.py` | Analysis tool. Discovers `results/p*_d*` configs, computes cost-benefit metrics, outputs `results/summary/cost_benefit.md` and (if matplotlib available) `results/summary/phase_breakdown.pdf`. |
| `synthetic_test.py` | Correctness validation. Generates 1000 batch + 5000 work records with known values, packs as binary, parses back, asserts all 97 checks pass. |
| `synthetic_test_results.txt` | Committed test output — proof parser is correct on this Python version. |

### Struct sizes validated on iPad (Python 3.11.15)

- `specasync_batch_record`: **72 bytes**, fmt `<6Q6I`
  - Offsets: batch_id(0), t0–t4(8–40), num_faults(48), spec_enqueues(52),
    spec_drops(56), spec_hits(60), enqueue_overhead_ns(64), _pad(68)
- `specasync_work_record`: **48 bytes**, fmt `<4Q4I`
  - Offsets: enqueue_ts(0), dequeue_ts(8), completion_ts(16), va_addr(24),
    result(32), policy_used(36), _pad[2](40-44)

### Validated on iPad

- **97/97 synthetic checks pass** (see `synthetic_test_results.txt`)
- Struct packing, field ordering, statistics (mean/median/p50/p95/p99),
  hit rate, wasted-spec rate, CSV derived columns, trailing-byte handling

### Deferred to Phase B

- `cost_benefit.py`: full metric computation requires Phase 2 telemetry from
  `run_all_experiments.sh`. Markdown + PDF output not exercised on iPad.
- Phase breakdown PDF requires matplotlib (may need `pip install matplotlib`).

---

## Priority 7 — Reframed abstract + intro revisions

**Committed:** Phase 2 P7: reframed abstract and intro revision notes

### What was done

Created `paper/`:

| File | Purpose |
|------|---------|
| `abstract_v2.md` | Revised abstract. Repositions primary contribution as in-driver speculation *infrastructure* (telemetry, policy framework, debugfs). Honestly reports cuFFT ≤4.4% with other workloads within noise. Frames Phase 2 as the evidence-gathering step for critical-path shortening. |
| `intro_revisions.md` | Two drop-in paragraph replacements: (1) contribution list rewritten to lead with infrastructure, not speedup numbers; (2) hypothesis paragraph rewritten to frame Phase 1 as consistent-but-not-conclusive, with Phase 2 as the direct-evidence step. |

### Key framing decisions

- "modest and workload-dependent" replaces any language implying broad speedup
- Phase 1 cuFFT result (4.4%) is stated as the best case, not the typical case
- Phase 2 is explicitly positioned as the critical-path evidence the reviewers asked for
- Limitation (metadata-only, no oversubscription) is stated honestly

### Validated on iPad

Plain Markdown, no execution required.

---

## Priority 8 — References cleanup

**Committed:** Phase 2 P8: references review for reviewer Comment 5

### What was done

Created `paper/references_review.md`:
- [9] Forest (ISCA 2025): confirmed peer-reviewed; action: verify DOI when proceedings finalise
- [8] Long et al. (arXiv): needs-replacement; three peer-reviewed substitutes provided
- [10] Anonymous arXiv: needs-replacement; three peer-reviewed substitutes provided
- [19] Parravicini (arXiv): find-venue-version; action: check DBLP
- General arXiv policy guidance and list of confirmed-safe references

### Cannot verify without web access

Forest ISCA 2025 DOI, Hermes MICRO 2022, Liao BaM ASPLOS 2023, Zheng ISCA 2020,
Kim ASPLOS 2020, Ganguly ISCA 2019, Parravicini venue. All marked "needs verification".

---
