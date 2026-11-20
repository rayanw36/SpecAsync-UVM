# Session C22: verification and analysis items from the revision list (no GPU, no text edits)

Repo: SpecAsync-UVM, branch `manuscript-prep`. This session needs no GPU, loads no modules, and edits no section text. It runs unattended with a cap of 3 h. Log every step in `consolidation/C22_STATUS.md`.

Every number must come from a script and carry an evidence id. Each item below has a revision-list ID; use the ID in the file names and in the status log. Commit after each item.

## 1. III-1: eviction order (read-only, pristine 595.91.07 source)
Section III-D says the driver chooses eviction victims "in allocation order, not by recency of access". C5 reported that. The reviewer suspects that a root chunk's position in the eviction list is refreshed when memory in it is used.

Answer from the source, citing file:line for each claim:
- Which function moves a root chunk to the tail of the used or eviction list? Check `uvm_pmm_gpu_mark_root_chunk_used`, `root_chunk_update_eviction_list`, and their callers in `uvm_va_block.c`, such as `block_mark_memory_used`.
- On which events is it called: allocation, every `make_resident` into the chunk, or every fault service on the block?
- How does `pick_root_chunk_to_evict` choose its victim?

End with a one-line verdict:
- ALLOCATION ORDER, or
- REFRESHED ON USE (state what counts as "use"), or
- MIXED.

Write the answer to `consolidation/C22_III1_EVICTION.md`.

## 2. VII-4: does Eq. 1 explain E8's failed expectations? (descriptive, from existing data)
The hypothesis has three parts:
- **K = 1 at t51.** The faulted page is widened to 64 KB, which is 16 of 512 pages, and the next level fails 51%. So about 3.1% of the array moves.
- **t25.** A 32-page subregion passes (50% > 25%) but a 64-page one does not.
- **K = 8.** Up to 128 counted pages, which is exactly 25% of the block. So t25 behaves like t0 for some blocks and not others.

Do the following:
1. Using the strict test `100*count > threshold*size`, the 64 KB widening and the binary subregion tree, write a script that simulates the expected migrated fraction for each K ∈ {1, 8, 64, 512} and t ∈ {0, 25, 51}, for in-memory and oversubscribed sizes. The script reads the pages that E8's page list (seed 202610081) touches in each block.
2. Compare the simulation with E9's traced HtoD bytes (all cells E9 has) and with the H2 HMM residency.
3. Report predicted against measured values per cell, and whether the XS4 and XS5 failures follow from the rule.

Write the results to `consolidation/C22_VII4_DENSITY_SIM.md`.

## 3. VII-5 / M4: CPU-side share for Stencil-24K
- **Data:** compute the share of the threshold-0 wall-clock gain that falls outside the GPU kernels, for Stencil-24K itself. Use E9's traced Stencil-24K runs (kernel time against everything else, t0 and t51), with the same method as `c4_e8_outside_kernels.csv`.
- **Missing kernel time:** if E9 has no kernel-time split for Stencil-24K, say so. Then report what is available: the CPU-fault counts and the host-initialisation phase duration at t0 and t51.

Write to `consolidation/C22_VII5_STENCIL_CPU.md`.

## 4. M5 / V-4 / VII-3: bootstrap confidence intervals
For every comparison the paper cites, compute a 95% bootstrap CI of the difference of medians, as a percentage of the baseline median. Use 10,000 resamples within cells and seed 20261117. The comparisons are:
- E4 F1 and F4, E5, and E6 families 1 to 3;
- E7 Families A and B, and E7-T4 Families A and B;
- E8 (16 cells), H1, and H2 (8 cells).

Write `consolidation/C22_BOOTSTRAP_CI.csv`, with columns: gate, comparison, delta %, CI low, CI high, MWU p, Holm-adjusted p, MDE % at the family α, and evidence id. Then answer these questions:
- **(a)** For each null result the paper relies on (E6 at t0 and t10; GraphBFS-23 in E4 and E7; E7 Stencil-8K, Sweep-4K and cuFFT), give the CI. State whether the CI excludes an effect of ±2% and of ±5%.
- **(b)** SGEMM on the T4: delta −2.24%, Holm-significant, SD-based MDE 7.72%. Give its CI. Say whether outliers inflate its SD: give the SD with and without Tukey outliers, and the number of runs flagged.
- **(c)** List every comparison where the bootstrap CI and the Holm decision disagree in sign or significance.

Add the new evidence ids to the extract.

## 5. VI-1 / VI-2: copy offload against fault reduction (E4 and E5)
1. From `e4/mechanism.csv` and `e5/mechanism.csv`, for C0 and C7-W512 at t51, compute:
   - demand faults, D5 total, and D5 per fault;
   - the D5 that C7's fault count would cost at C0's per-fault D5;
   - the split of C7's D5 reduction into a fault-count part and a per-fault part.
   Do it separately for each gate.
2. Report what `fault_already_resident` counts exactly, citing the counter's increment site file:line in our driver source, and why it is 2.07% while the worker requested 832,392 pages.
3. State which gate each number in Table V (`t_mech`) comes from.

Write to `consolidation/C22_VI1_DECOMPOSITION.md`.

## 6. IV-4: GraphBFS repeated staging
For GraphBFS-23, Table V shows 25,553,498 pages requested for 287,956 distinct pages, and 231,996 faults already resident. Explain both from the counters and the code:
- whether a page can be requested more than once: width W = 512 regions overlapping, region history 8, cursor skips;
- what `pages requested` counts: pages in the regions enqueued, or the predictions.

Reconcile this with the Section IV sentence "the graph oracle stages only part of the working set": what fraction of distinct pages was made resident by the worker at least once, if the counters allow it?

Write to `consolidation/C22_IV4_GRAPHBFS.md`.

## 7. M3: fault-dispatch share
For Stencil-24K and GraphBFS-23 under C0 and C7-W512, compute the servicing window and D5 as fractions of process wall-clock, from E4 or E1 Part B, whichever has C0 phase data; name the source.

Write to `consolidation/C22_M3_DISPATCH_SHARE.md`.

## 8. VIII-1 / I-4: in-gate catches
From the catalog's families table and the supplement, list for all 31 entries:
- the catching mechanism;
- whether the catch happened inside the gate that made the error;
- whether it was a check written before the measurement.

Give the counts behind two statements: "caught inside its own gate" and "caught by a pre-registered check". Include #5, #14 (each instance), #20 and #21.

Write to `consolidation/C22_VIII1_CATCHES.md`.

## 9. V-1: workloads table
For every workload in the paper, list:
- the benchmark source file;
- the command line and arguments;
- the problem size;
- the managed-memory footprint in GiB;
- the passes or iterations;
- the median wall-clock at t51 on the 5070 Ti.

Take each value from the code and the CSVs. Write `paper/tables/t_workloads.tex` (generated) and `consolidation/C22_WORKLOADS.md`. Do not input the table into any section yet.

## 10. S-7: missing supplementary tables
Generate full test tables, in the same style as the existing ones, for:
- E7 on both GPUs, with p-values;
- H1;
- H2.

Add them to `paper/tables/`. Do not wire them into `supplementary.tex` yet.

## 11. Status
Finish `C22_STATUS.md` with one line per item: its result, or the verdict for III-1. Commit and push, then print a short summary.
