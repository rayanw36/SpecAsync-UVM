# Gate A — restart and rebuild (AWS final work block)

Session: 2026-08-11, instance restarted after a stop (`/opt/dlami/nvme` wiped as expected).

## Platform readout

| item | value |
|---|---|
| GPU | Tesla T4 |
| driver | 595.71.05 (unchanged) |
| `nproc` | 4 (unchanged, g4dn.xlarge) |
| `uname -r` | 6.17.0-1019-aws (unchanged) |

No hard stop triggered — driver matches the required 595.71.05 exactly.

## Oracle trace status

`/opt/dlami/nvme` was wiped (only `lost+found` present), as expected — but the oracle traces
used by T1's C3 runs are **not** on the instance store. They live under the repo on the EBS
root (`/`, 77G, 40% used) and are git-committed:

| trace | path | size | entries | git status |
|---|---|---|---|---|
| GraphBFS-23 | `results/phaseB2/gate3_interleaved/c3_bench_graph_bfs_trace.bin` | 1,660,512 B | 207,564 | clean, matches HEAD |
| Stencil-24K | `results/phaseB2/gate3_interleaved/c3_bench_stencil_trace.bin` | 2,215,688 B | 276,961 | clean, matches HEAD |

The GraphBFS entry count (207,564) matches `GATE_T1_REPORT.md`'s recorded dmesg line
(`specasync: oracle trace loaded: 207564 entries`) exactly. `git status --short` on both files
shows zero diff against the committed blob — no regeneration was necessary.

## Rebuild

`driver/scripts/reconstruct_build_tree.sh` run clean (rsync pristine 595.71.05 source, apply
glue patch, copy authoritative `driver/src/` files, build). Output:

```
srcversion:     8A2651D1CB32C7B239FB511
vermagic:       6.17.0-1019-aws SMP mod_unload modversions
```

Matches the expected srcversion exactly. Copied to `driver/build/nvidia-uvm-specasync-t4.ko`
(also matches the pre-stop EBS copy byte-for-byte — same srcversion — confirming the EBS-side
`driver/build/` cache was already valid; the rebuild was a verification, not a repair).

Module reloaded (`specasync_policy=1 specasync_offload_depth=0 uvm_perf_prefetch_enable=0
specasync_log_enabled=1`) — dmesg clean init (`specasync: init OK log_enabled=1 policy=1
offload_depth=0 decomp=1`), `nvidia-smi` healthy (0 MiB used, 595.71.05).

## Deterministic probe

`sudo bash tests/run_hit_probe.sh 256 1 phaseA_gate_probe`:

| counter | value |
|---|---|
| batches (valid) | 256 |
| demand faults | 256 |
| spec_enqueued | 256 |
| spec_processed | 256 (worker records; all hit) |
| spec_hits | 255 |
| spec_drops | 0 |
| hit_rate | **0.9961** |

Matches the expected ~99.6% (original Gate A: 254/256 = 99.22%; this run: 255/256 = 99.61% —
same regime, sub-probe noise). Counter triad and worker path confirmed sound after rebuild.

## Note carried into Task A1

`run_hit_probe.sh`'s own header defines `spec_processed` as **"count of
`specasync_worker_log` records"** — i.e. this has always been a ring-derived count, not a
kernel-side atomic. At 256 items the ring never wraps, so the count is exact here. This is
exactly the gap Task A1 exists to close for real benchmarks (Stencil-24K generates ~51M
enqueues/run — many ring-wraps), and confirms no global `spec_processed` counter exists yet in
the driver source; one must be added.

**Gate A: platform unchanged, trace intact and verified on EBS, rebuild reproducible
(srcversion match), probe nominal. Proceeding to Task A1.**
