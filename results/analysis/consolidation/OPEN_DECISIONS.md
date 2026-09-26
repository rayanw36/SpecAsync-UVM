# Gate C1 Step 6 — Open decisions

These are things the consolidation cannot settle without a decision from the author.
Each gives the options and what the evidence does and does not support. **No option
is applied.**

### D1 · Does a practical block-level predictor belong in this paper or the follow-on?
- **Context:** CS2-N1's positive result uses a **perfect** first-touch table. E4/E5
  show *where* the gain comes from: whole-block staging, with the prefetcher mapping
  the staged regions. They do not show that any realisable predictor captures it.
- **Options:**
  - **(a) Follow-on.** Present the result as an upper-bound demonstration and a
    mechanism, and state plainly that no practical predictor was tested.
  - **(b) This paper.** Add a pre-registered gate with a block-level predictor (for
    example the stride or Markov policies at W = 512, or "stage the whole block on
    the first fault in it"), run against C0 on the same protocol.
- **Evidence bearing on it:**
  - At W = 512 on Stencil the worker makes only about one call per 2 MB block (2,198
    enqueues; `E4.mech.stencil.C7-W512`). A block-level predictor needs to be right
    about *which block comes next*, not which page. That is a much easier target,
    but still an unmeasured one.
  - GraphBFS shows nothing even with the perfect table.
- **Risk if deferred:** the paper's positive result is oracle-only.

### D2 · T4 replication scope
- **Context:** every Gate E result (E0.5 → E5) is RTX 5070 Ti, driver 595.91.07.
  The T4 carries the older C0–C3 results (CS2-7/8/9) under the misaligned oracle.
- **Options:**
  - **(a) No T4 replication.** State Gate E as single-platform.
  - **(b) Replicate the E4 F1 cells** (C0 vs C7-W1 / C7-W512, Stencil and GraphBFS)
    on T4. This needs a port of the E3a-2 module to 595.71.05 and the T4 kernel, and
    a new review cycle for the kernel code.
  - **(c) Replicate E5's T_off test** on T4 as well, to establish H-feed
    cross-platform.
- **Evidence bearing on it:**
  - The mechanisms (H-map, H-feed) are source-level properties of UVM. They should
    transfer wherever the prefetcher and the service path are the same.
  - The *magnitude* of the gain, a cost ratio, would not necessarily transfer.
    CS2-8's 3.55× vs 3.88× shows the prefetch benefit is similar, but not identical,
    across platforms.

### D3 · How GraphBFS's weakened-cursor oracle is presented
- **Context:** policy 6's cursor jumps to one past the highest rank seen, so one
  out-of-order fault skips everything in between. GraphBFS's first-touch order is
  only loosely stable (CS2-N6), and coverage stays low even at L = 4096: 0.2229 at
  C6-W1 (`E4.mech.graphbfs.C6-W1`), 0.8057 at C6-W512 (`E4.mech.graphbfs.C6-W512`).
  In GraphBFS, "no gain" is a null for *this oracle*, not for first-touch knowledge.
- **Options:**
  - **(a) Report it as a weakened-oracle null** with a limitation, as the
    pre-registrations did.
  - **(b) Build a non-skipping first-touch oracle** (stage in rank order regardless
    of observed faults) and rerun GraphBFS. This needs new kernel code and a review
    cycle.
  - **(c) Drop GraphBFS** from the positive-result claim, keeping it only as the
    example where the prefetcher already does most of the work: C1/C0 is 1.05×
    (`T1B5.5070Ti-595.84.bench_graph_bfs`) and 1.07× on T4.
- **Note:** GraphBFS C6-W512 still staged 80.6% of pages and cut D5 (0.7308 →
  0.4116 s; `E4.mech.graphbfs.C1` / `C6-W512`), yet gained only 0.97% over C1.
  GraphBFS is compute-dominated: about 31 s of wall-clock is mostly CPU graph build.
  That argues for (a) or (c) over (b).

### D4 · Claims the ledger could not resolve
1. **CS2-4 (trylock throttle, 76.1%).** Gate E's width worker also uses `trylock`,
   and E4 shows lost-after-enqueue at W > 1 (for example 33,727 at Stencil C7-W64;
   `results/analysis/gate_e/e4/mechanism.csv`, field `lost_after_enqueue`). It is
   not decided whether the claim should be restated for the
   current design, or left as a Gate 2 historical measurement.
2. **CS2-17 ("safety-invariant-preserving").** The E0.9a-2 crash was in the
   project's instrumentation. It is not decided whether the claim keeps that wording
   with a qualifier, or is restated as "passes the E3a-2 review protocol".
3. **B9's oversubscription C3 wall-clock** (`B9.2c.*`). It is a measurement of a
   configuration whose oracle was truncated, rotated and misaligned (AC-19). CS2-N9
   excludes B10's *mechanism* narrative. It is not decided whether B9's C3-vs-C0
   numbers stay in the paper (as AC-12's worked example) or are excluded entirely.
4. **E0.9b's "5.65%" and E1's +3.9–8.4%.** They stand as expensive-oracle
   measurements. It is not decided whether the paper reports them at all, now that
   E4 re-measured both questions with the cheap oracle.
5. **The E5 wall-clock split at the default threshold.** How much of the 5.26% comes
   from fault prevention (H-feed) and how much from copy offload (D5) is not
   separable from E5's data. A claim that apportions it needs a new pre-registered
   design, or must be phrased as "two mechanisms, not apportioned".

### D5 · Do averted hazards belong in the artifact catalog?
- `uvm_perf_prefetch_threshold` values above 100 silently fall back to 51, while
  read-back still shows the raw value (`E5_MECHANISM.md` §3). This was caught by
  source reading before any run, so it never produced a result.
- **Options:**
  - **(a)** A catalog appendix of "averted hazards".
  - **(b)** A methodology note only.
  - **(c)** Omit.

### D6 · Evidence gaps: PROSE-ONLY numbers that the paper may need
Several central numbers exist only in prose, because their raw data is gitignored:
- E0.8's index-drift statistics (CS2-N6);
- E0.5's misalignment ratios 11.7× / 2.1× (CS2-7, R1, AC-13);
- the corrected pipelining ceilings 0.08–7.94% (CS2-15);
- E0.9a-2's "prevented = 0.0000%".

**Options:**
- **(a)** Regenerate derived CSVs from the gitignored raw data where it still exists
  on disk, and commit them.
- **(b)** Cite them as report prose, with the producing script's path.
- **(c)** Avoid them in the paper.

Checking which raw files still exist is a no-run, read-only task. It was **not** done
in C1.
