# Gate E0.7 — Diagnosing the oracle accuracy collapse

E0.6 (§6) is cancelled per instruction, not run. This gate answers whether
E0.5's accuracy collapse is local reordering, genuine divergence, or a mix,
and whether it aligns with a workload phase boundary. **No changes to the
Step 2/3 fix logic.** One narrow addition was made and is fully described
below (Check 1's instrumentation). All work: RTX 5070 Ti, driver 595.91.07,
kernel 7.0.0-31-generic, headless (`systemctl isolate multi-user.target`,
confirmed via `gdm`/`graphical.target` inactive and `nvidia-smi` still
working), restored to `graphical.target` at the end (confirmed active).
`MemAvailable` logged throughout (60.79-60.89 GB across this session, no
drift toward the 6 GiB floor). Every run: fresh module reload, `setarch -R`,
`specasync_clear` before replay reps.

## 0. Push confirmation

`8997e79` (E0.5's final commit) was **not yet pushed** when this gate began
— confirmed via `git fetch` + comparing `origin/manuscript-prep` (`ea72f33`)
against local `HEAD` (`8997e79`, one commit ahead). Pushed successfully
before any further work (`ea72f33..8997e79`, exit 0). Everything in this
gate builds on that pushed commit.

## 1. Was Check 1 post-hoc, or did it need an instrumented run?

**Needed a new instrumented run.** E0.5 logged only aggregate counters
(`oracle_correct`, `oracle_predictions`, and their per-decile buckets) —
these say *whether* fault *k*+1 was predicted correctly, never *what the
fault sequence actually was* when it wasn't. Reconstructing an ordering
from those counts would be exactly the "reconstruct an ordering from an
aggregate" the standing rules forbid, so a short instrumented replay run
was added instead. Code added (full diff in commit `a8230fb`, pushed):

- `driver/src/specasync_telemetry.h`: a new opt-in ring
  (`g_replay_order_ring`, reusing the existing `specasync_trace_ring`
  struct/read-path machinery) and `specasync_replay_order_push()`, gated by
  a new module param `specasync_log_replay_order` (default 0).
- `driver/src/specasync_debugfs.c`: allocation/free/debugfs-file wiring for
  the new ring (mirrors `alloc_trace_ring`/`trace_ring_read` exactly; the
  wrap-rotation logic was factored into a shared `generic_trace_ring_read()`
  helper rather than duplicated, so there is only one copy of that logic to
  get right), plus one call site: `specasync_replay_order_push(current_fault_addr)`
  added as the first line inside `specasync_oracle_next_addr_n()`.
- **Nothing else changed.** No change to `g_oracle_idx`, the scoring logic,
  Step 2's recording loop, or Step 3's counters.

**The predicted-address sequence is not separately logged** — it doesn't
need new instrumentation. `specasync_oracle_next_addr_n()`'s cursor
arithmetic is a proven, deterministic identity (verified exactly against
`group_probe`'s `oracle_correct=7/7` in E0.5): starting from a fresh
`g_oracle_idx==0`, the *k*-th call reads `trace[k % len(trace)]` and that
becomes the prediction scored against the fault serviced at call *k*+1.
This is a closed-form derivation from data that **is** fully logged (the
trace file), not a reconstruction from an aggregate. **This derivation was
verified, not assumed**, in every one of the four runs below: the derived
exact-next-correct count is checked against the kernel's own
`oracle_correct`/`oracle_predictions` counters before anything else is
computed, and reproduced exactly in all four cases (Stencil depth=1: 187/187;
Stencil depth=0: 488/488; GraphBFS depth=1: 7294/7294; GraphBFS depth=0:
7303/7303). None failed; none needed a stop.

Analysis script: `tests/gate_e07_accuracy_analysis.py` (committed).

## 2. Check 1 — accuracy measures, both workloads, by decile

Ran the oracle replay twice per workload — `offload_depth=1` (real
migration, matches this project's "C3") and `offload_depth=0` (metadata
only, zero migrations) — because the two gave qualitatively different
answers and reporting only one would hide that (see §4/§6).

**Sanity check (required before anything else):** derived exact-next
correctness reproduced the kernel's own counters exactly in all four runs —
table above. Proceeding on that basis.

### Stencil-24K, depth=1 (2,954,436 trace entries, 2,998,046 replay-order entries)

| measure | overall | d0 | d1 | d2 | d3 | d4 | d5 | d6 | d7 | d8 | d9 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| exact-next | 0.0062% | 0.0624% | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| window W=10 | 0.0262% | 0.2615% | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| window W=100 | 0.2125% | 2.1254% | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| window W=1,000 | 2.0770% | 20.7702% | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| window W=10,000 | 15.2901% | 99.3616% | 53.5391% | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **set (anywhere in remainder)** | **98.4807%** | 99.3616% | 100.0000% | 100.0000% | 100.0000% | 100.0000% | 100.0000% | 100.0000% | 100.0000% | 100.0000% | 85.4452% |

### Stencil-24K, **depth=0** (same trace, 2,909,628 replay-order entries) — the clean, migration-free control

| measure | overall | d0 | d1-d9 |
|---|---:|---:|---:|
| exact-next | 0.0168% | 0.1677% | 0 (all) |
| window W=10 | 0.0557% | 0.5575% | 0 (all) |
| window W=100 | 0.3205% | 3.2049% | 0 (all) |
| window W=1,000 | 0.4344% | 4.3442% | 0 (all) |
| window W=10,000 | 0.4344% | 4.3442% | 0 (all) |
| **set (anywhere in remainder)** | **0.4346%** | 4.3456% | 0 (all) |

**This is the single most important comparison in this gate.** At depth=1
Stencil's set accuracy is 98.48% (deciles 1-8 exactly 100.0000%); at depth=0,
with the identical collection trace, replaying the identical benchmark, it
is 0.4346% — **three orders of magnitude lower, and zero past decile 0**.
The only difference between these two runs is `offload_depth`, i.e. whether
real speculative migration happens (depth=1: 2,821,745 successful migrations
this run; depth=0: 0). The near-total overlap at depth=1 is not evidence
about the fault stream's own structure — it is an effect of the migrations
themselves reshaping which pages still need to fault. See §4.

### GraphBFS-23, depth=1 (486,980 trace entries, 481,955 replay-order entries)

| measure | overall | d0 | d1 | d2 | d3 | d4 | d5 | d6 | d7 | d8 | d9 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| exact-next | 1.5134% | 15.0659% | 0.0021% | 0 | 0.0228% | 0.0062% | 0.0166% | 0.0062% | 0.0041% | 0.0104% | 0 |
| window W=10 | 1.5715% | 15.2547% | 0.0436% | 0.0104% | 0.0788% | 0.0747% | 0.0809% | 0.0602% | 0.0519% | 0.0311% | 0.0290% |
| window W=100 | 2.2118% | 16.3544% | 0.8424% | 0.3880% | 1.0229% | 0.6743% | 1.0105% | 0.5146% | 0.4585% | 0.3776% | 0.4751% |
| window W=1,000 | 6.1736% | 22.2969% | 3.2700% | 3.2970% | 6.0483% | 3.3571% | 7.1169% | 5.4611% | 3.8655% | 3.3696% | 3.6538% |
| window W=10,000 | 21.2070% | 44.6499% | 22.4961% | 26.6329% | 20.7158% | 5.1872% | 22.3011% | 19.5933% | 11.0445% | 18.8713% | 20.5785% |
| **set (anywhere in remainder)** | **36.5062%** | 74.9518% | 55.1987% | 37.7811% | 21.0126% | 7.1105% | 31.9182% | 33.3956% | 35.9158% | 29.3516% | 38.4264% |

### GraphBFS-23, **depth=0** (same trace, 484,403 replay-order entries)

| measure | overall | d0 | d1 | d2 | d3 | d4 | d5 | d6 | d7 | d8 | d9 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| exact-next | 1.5076% | 14.9876% | 0.0062% | 0.0165% | 0.0103% | 0.0041% | 0.0083% | 0.0186% | 0.0062% | 0.0103% | 0.0083% |
| window W=10,000 | 22.8601% | 46.5751% | 26.6020% | 29.1412% | 17.5454% | 3.4764% | 18.0698% | 18.2721% | 13.9430% | 27.8799% | 27.0969% |
| **set (anywhere in remainder)** | **35.5494%** | 67.6734% | 45.7432% | 39.5851% | 17.6156% | 5.5428% | 27.7519% | 31.9158% | 36.4926% | 37.4339% | 45.7402% |

**GraphBFS-23 barely changes between depth=0 and depth=1** (35.55% vs.
36.51% overall set accuracy; decile shapes nearly identical). Unlike
Stencil, migration is not a meaningful confound for this workload — see §4
for why.

## 3. Check 2 — hardware nondeterminism alone, no oracle machinery at all

Three independent plain-C1 runs per workload (`specasync_policy=0`, no
enqueue, no replay, `prefetch=0`, fresh reload + `setarch -R` each time),
compared pairwise (A = "predictions", B = "actual", same measures).

### Stencil-24K, three pairs (set accuracy row; full windowed/decile tables in the script's saved stdout, `results/phaseB1/gate_e07_check2/` raw traces gitignored per convention, rerunnable from this report's commands)

| pair | n compared | exact-position | window W=10,000 | **set (remainder)** |
|---|---:|---:|---:|---:|
| rep1 vs rep2 | 2,940,654 | 0.0391% | 1.9447% | **1.9447%** |
| rep1 vs rep3 | 2,941,901 | 0.0160% | 2.9479% | **2.9480%** |
| rep2 vs rep3 | 2,940,654 | 0.0831% | 21.2074% | **21.2074%** |

(Set accuracy equals the W=10,000 figure in all three Stencil pairs because
no match ever occurred beyond position *k*+10,000 in these particular
pairs — a coincidence of this data, not a general property.) Decile shapes
are irregular and inconsistent across pairs — e.g. decile 7 is nonzero in
all three pairs, decile 2 only in rep2-vs-rep3, decile 8/9 only in
rep2-vs-rep3 — there is no clean early/late split here at all.

### GraphBFS-23, three pairs

| pair | n compared | exact-position | window W=10,000 | **set (remainder)** |
|---|---:|---:|---:|---:|
| rep1 vs rep2 | 480,809 | 1.5251% | 60.6145% | **70.8947%** |
| rep1 vs rep3 | 480,809 | 1.5201% | 68.6774% | **80.5732%** |
| rep2 vs rep3 | 482,174 | 1.5146% | 67.3580% | **78.6083%** |

GraphBFS's three pairs agree closely with each other (70.9%, 80.6%, 78.6%
set accuracy) and show a much smoother decile progression than Stencil's
pairs, with early deciles substantially recovering by W=10,000 (e.g.
decile 4 reaches 85-98% at W=10,000 in two of the three pairs).

**Check 2 reverses the naive reading of Check 1's depth=1 numbers.**
Comparing only the "clean" measurements (Check 2 for both workloads, and
Check 1's depth=0 for the migration confound check): **Stencil is the
low-overlap workload (0.4%-21%, uneven) and GraphBFS is the high-overlap
workload (35%-80%)** — the opposite ranking from what Check 1's depth=1
numbers alone would suggest (Stencil 98%, GraphBFS 37%). Depth=1's apparent
Stencil advantage was manufactured by the migrations themselves, not by the
fault stream's own structure.

## 4. Why depth confounds Stencil but not GraphBFS

Not chased as a separate investigation — the mechanism is visible directly
in already-collected counters. At depth=1, both workloads have similarly
high migration success rates (Stencil 96.97% of enqueued, GraphBFS 97.49%),
so the difference isn't in whether migrations succeed. It's in what a
success *removes*: Stencil's kernel (`bench_stencil.cu`) re-touches its
**entire** grid on every one of 20 ping-pong iterations — a single
successful speculative migration for one page pre-empts that page's demand
fault on potentially several of the remaining iterations, compounding
across the run. GraphBFS's traversal touches each vertex/edge according to
the graph's own (data-dependent, non-repeating) structure — a migration
success removes at most the one demand fault it pre-empted, with no
iteration-level compounding. This is consistent with, not separately
verified beyond, the numbers above.

## 5. Check 3 — where does the knee fall?

**Method 1: cumulative address-diversity.** For Stencil-24K's collection
trace, computed the running count of distinct addresses seen at 200
evenly-spaced checkpoints (resolution: 0.5% of run length, ~14,772
entries). Result: the fraction of distinct-so-far addresses is **flat at
~38.1% from the 5% checkpoint through 100%** (37.85% at 5%, 38.08% at
100%), and the very first repeated address occurs at index 1 (i.e.
essentially immediately). **This method finds no phase transition at all**
— it directly contradicts the plausible a priori account (a long
fully-unique initialization sweep followed by a repetitive compute phase)
stated in this gate's brief. Total distinct addresses across the whole run:
1,125,000 — matching a back-of-envelope estimate of the grid's total page
count (2 arrays x 24000² floats / 1024 floats-per-page ≈ 1,125,000),
consistent with every page being touched roughly `2,954,436 / 1,125,000 ≈
2.6` times on average, spread throughout the run rather than concentrated
in a late "compute" region.

**Method 2: exact position of the last correct exact-next prediction**
(resolution: single-fault, i.e. ±1 position out of millions) — far more
decisive:

| run | first correct position | last correct position | 99th-pct position |
|---|---:|---:|---:|
| Stencil depth=1 | 1 (0.0000%) | 10,011 (**0.334%**) | 9,877 (0.330%) |
| Stencil depth=0 | 1 (0.0000%) | 45,388 (**1.560%**) | 44,186 (1.519%) |
| GraphBFS depth=1 | 1 (0.0002%) | 433,595 (89.97%) | 7,221 (1.498%) |
| GraphBFS depth=0 | 1 (0.0002%) | 483,042 (99.72%) | 7,230 (1.493%) |

**The knee is real, sharp, and located at roughly the first 0.3-1.6% of the
run for both workloads — not at 10%, and not at any point corresponding to
the theoretical end of Stencil's CPU-side sequential initialization sweep**
(which Method 1 shows spans the *entire* run's address footprint, not just
a leading fraction of it). 99% of all correct predictions land within the
first ~1.5% of the run for three of the four configurations; **Stencil's
cutoff is a hard wall** (zero correct predictions past 1.56% of the run in
either depth); **GraphBFS has a long, thin tail** — its 99th percentile is
at 1.5%, matching Stencil, but its single *last* correct match lands at
90-99.7% into the run, i.e. isolated coincidental matches keep occurring
at low rate all the way to the end, which Stencil never shows.

**Reading against the brief's plausible account:** the hypothesized
mechanism (deterministic single-stream init, nondeterministic massively-
parallel compute, knee at the boundary between them) does not match what
was measured. The actual knee is far earlier than any plausible init-phase
boundary, and Method 1 shows the address *footprint* itself has no such
boundary either — pages from the "final" ~90% of the address space, by
whatever ordering the collection trace records them in, are already being
touched within the first 5% of the run. Whatever makes prediction fail
happens almost immediately, not at a kernel-launch boundary. This gate does
not have a replacement mechanism to offer — recorded as a finding, not
investigated further, per instruction.

Benchmark launch boundaries were not independently instrumented (no
benchmark source changes were made, consistent with keeping this gate's
code changes to the one diagnostic ring described in §1); Method 1 and
Method 2 above are both derived directly from the fault-address sequences
already collected, at the stated resolutions.

## 6. Verdict

**Mixed, and not reducible to "local reordering" or "genuine divergence"
as a single answer for either workload alone — stated plainly, per
instruction, rather than forced.**

- **Stencil-24K, on the cleanest available evidence (depth=0's migration-free
  replay, and Check 2's three independent plain-C1 pairs): closer to
  genuine divergence than reordering.** Set accuracy 0.4%-21% (uneven
  across the three C1 pairs), essentially zero past the first ~1.6% of the
  run in the depth=0 measurement. The 98.48% figure from depth=1 is an
  artifact of real migration compounding across this workload's 20 repeated
  ping-pong passes over the same footprint (§4), not a property of the
  fault order itself.
- **GraphBFS-23: a genuine mix, tilted toward reordering more than
  Stencil.** Set accuracy is consistent across depth=0/depth=1 (35.5%/36.5%)
  and rises further under the migration-free, oracle-free Check 2 comparison
  (70.9%-80.6% across three pairs) — a majority of predicted addresses do
  recur somewhere later in an independent run, but a substantial minority
  (20-30%, worse if the oracle machinery itself is active) never do.
- **The knee's location (~0.3-1.6% into the run, both workloads) does not
  correspond to any workload phase boundary this gate could locate** — it is
  far too early to be the compute-kernel boundary and does not line up with
  any structure found in the address-diversity signal either.
- **A confound neither original check anticipated: the oracle mechanism's
  own real migrations distort exactly the kind of comparison Check 1 was
  designed to make, and by a workload-dependent amount that can flip the
  qualitative ranking between workloads (Stencil looks best at depth=1,
  worst everywhere else).** Any future accuracy measurement of a trace-replay
  oracle against a real workload should report depth=0 and depth=1
  separately, or explicitly justify treating them as equivalent.

Per instruction, no new oracle design and no rebuild-the-paper's-argument
work was done in this gate. Both of the two paths named in the brief remain
live, and neither is preferred by this evidence alone:

- A self-synchronizing, resync-on-match oracle would need to search forward
  from the *current* position, not assume adjacency — Check 1/2's evidence
  supports this being worth trying for GraphBFS-23 (real, if partial, set
  recurrence) but gives little reason to expect it would rescue Stencil-24K
  (whose migration-free divergence is closer to total).
- The alternative — abandoning trace replay as an upper bound and building
  the paper's argument on the pipelining ceiling and dispatch-latency race
  instead — is not contradicted by anything found here either.

## Flags for review (not edited)

- `CLAIM_SCOPE.md` row 7 and others citing C3's oracle-upper-bound framing
  should be read against this gate's finding that the oracle's own
  "accuracy" is not a stable, workload-independent property, and that the
  clean (depth=0) accuracy is far below what E0.5's depth=1 numbers alone
  would suggest.
- Any future gate reusing `oracle_correct`/`oracle_predictions` as a proxy
  for "is the oracle any good" should report depth=0 alongside depth=1,
  given §4's finding.

## Artifacts

- `driver/src/specasync_telemetry.h`, `driver/src/specasync_debugfs.c`:
  Check 1 instrumentation (commit `a8230fb`).
- `tests/gate_e07_accuracy_analysis.py`: Check 1/2 analysis script.
- `driver/build/595.91.07/nvidia-uvm-specasync-NEW-e0.7diag.ko`: built,
  gitignored, reproducible from the committed source.
- Raw traces/replay-order dumps: `results/phaseB1/gate_e07_check1/`,
  `results/phaseB1/gate_e07_check2/` (gitignored per this gate's `.gitignore`
  entries; regenerable via the `insmod`/`setarch -R` commands quoted
  throughout this report).

**HARD STOP.**
