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
