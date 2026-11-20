# C22 VI-1 / VI-2: copy offload against fault reduction (E4 and E5)

Script `tests/c22_vi1_iv4.py`; sources `gate_e/e4/mechanism.csv` and `gate_e/e5/mechanism.csv` (medians of 10 runs per arm; the E4 arms run at the shipped threshold 51 with the E3a-2 module, E5's C0 and C7W512 at t51 likewise, a separate session).

## Decomposition of the D5 reduction (C0 -> C7-W512, prefetcher on, t51)

Let f0, f7 be the demand faults and r0, r7 the D5 per fault of C0 and C7. D5 reduction = f0 r0 - f7 r7 = (f0 - f7) r0 [fault-count part] + f7 (r0 - r7) [per-fault part].

| gate / pair | evidence | faults C0 | faults C7 | D5 C0 (s) | D5 C7 (s) | D5/fault C0 (ns) | D5/fault C7 (ns) | D5 of C7's faults at C0's rate (s) | reduction (s) | fault-count part (s, %) | per-fault part (s, %) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| E4 Stencil-24K, C0 vs C7-W512 (t51) | `E4.mech.stencil.C0 / E4.mech.stencil.C7-W512` | 339,251 | 204,641 | 0.1051 | 0.0565 | 309.8 | 276.3 | 0.0634 | 0.0486 | 0.0417 (85.9%) | 0.0069 (14.1%) |
| E4 GraphBFS-23, C0 vs C7-W512 (t51) | `E4.mech.graphbfs.C0 / E4.mech.graphbfs.C7-W512` | 44,290 | 30,358 | 0.0488 | 0.0333 | 1101.3 | 1097.0 | 0.0334 | 0.0155 | 0.0153 (99.1%) | 0.0001 (0.9%) |
| E5 Stencil-24K, C0 vs C7W512 (t51) | `E5.mech.t51.C0 / E5.mech.t51.C7W512` | 339,386 | 203,331 | 0.1052 | 0.0561 | 310.0 | 276.1 | 0.0630 | 0.0491 | 0.0422 (85.9%) | 0.0069 (14.1%) |

Reading: the D5 reduction is mostly the fault-count part (E4 Stencil-24K 85.9%, per-fault part 14.1% with 310 -> 276 ns per fault; E4 GraphBFS-23 99.1%, per-fault D5 unchanged at 1.10 us; E5 Stencil-24K see the row above). Neither is a measurement of copy offload: the per-fault change at t51 is within what the changed fault mix produces (per-fault D5 is not separable from the fault count, CS2-N4). **Prefetch-on D5 totals are not evidence of copy offload**, as CS2-N4 states: the D5 fall tracks the fault fall (E5 D(51) = +0.4009, `E5.D(51)`). Copy offload shows only with the prefetcher off (E4 C6 vs C1 and E5 t100 vs C0-toff; Table V rows 'C1', 'C6-W512', 'C0-toff', 'C7W512-toff': per-fault D5 0.55 -> 0.17 us on Stencil-24K, 0.59 -> 0.21 us at t100).

## What `fault_already_resident` counts

The counter `g_specasync_fault_already_resident` is incremented in `service_fault_batch_block_locked` (`driver/src-e3a/uvm_gpu_replayable_faults.c:1844`), at `uvm_gpu_replayable_faults.c:2019-2021`, in the loop over the faults of one VA block in a batch: after the check that the page is not already GPU-authorised for the access (`:1986-1990`, otherwise `continue`), `if (uvm_va_block_gpu_state_get(va_block, gpu->id) && uvm_page_mask_test(uvm_va_block_resident_mask_get(va_block, gpu->id, NUMA_NO_NODE), page_index)) atomic_inc(&g_specasync_fault_already_resident);`. So it counts **demand-fault entries that will be serviced although the page is already resident on this GPU** (data there, mapping missing): one count per such fault entry, not per distinct page and not per page staged. Columns `far_frac_distinct` = counter / 1,125,000 (Stencil-24K) or / 287,956 (GraphBFS-23) (`tests/e4_analyze.py:27,122`).

## Why it is 2.07% on Stencil-24K when the worker requested 832,392 pages (C7-W512)

- `spec_pages_requested` is **not** a count of pages made resident or of predictions: the worker adds the size of the region it passes to `uvm_va_block_make_resident`, `atomic64_add(uvm_va_block_region_num_pages(sregion), &g_specasync_spec_pages_requested)` (`uvm_gpu_replayable_faults.c:398-401`, in `specasync_worker_fn`, `:324`), once per processed queue item, whether or not the pages were already resident. With W = 512 each item is a 512-page region (`specasync_width_region`, `:293-321`: the W-aligned region containing the predicted page), so requested = items processed x 512: E4 C7-W512 `spec_migrations` 1,626.5 x 512 = 832,768 (counter: 832,392); the other 571.5 of the 2,198 enqueued regions were lost after enqueue.
- The predictions are first-touch predictions, one per demand fault (204,641); 202,443 of them fall into one of the last 8 enqueued regions and are suppressed (`:2788-2799`), leaving 2,198 regions = 1,125,376 pages, about the 1,125,000 distinct pages.
- The worker's 832,392 pages are therefore **region sizes, and most of those pages are staged after the prefetcher and the demand path have already made them resident or mapped them**: the counter only registers the 22,960 demand faults (11.2% of 204,641 faults; 2.04% of the distinct pages) that arrived after the worker had made their page resident and before it was mapped. With the prefetcher on, the demand path maps whole regions at the first fault (`E5.D(51)`: faults fall from 339,386 to 203,331), so the worker rarely wins: the 2.07% is the share of distinct pages for which it finished first (E5 C7W512 t51: 2.07%, `E5.mech.t51.C7W512`). With the prefetcher off (C6-W512) the same worker finishes first for 99.95% (`E4.mech.stencil.C6-W512`) because nothing else brings the pages in.

## Which gate each number in Table V (`t_mech`) comes from

| Table V rows | gate | evidence ids (`% ` comments in `paper/tables/t_mech.tex`) |
|---|---|---|
| Stencil-24K: C0, C1, C6-W512, C7-W512 (shipped threshold, E3a-2 module) | **E4** | `E4.mech.stencil.C0`, `.C1`, `.C6-W512`, `.C7-W512` |
| GraphBFS-23: C0, C1, C6-W512, C7-W512 | **E4** | `E4.mech.graphbfs.C0`, `.C1`, `.C6-W512`, `.C7-W512` |
| Stencil-24K, t = 100: C0-toff, C7W512-toff | **E5** | `E5.mech.t100.C0`, `E5.mech.t100.C7W512` |
The E5 t51 rows (`E5.mech.t51.*`) are not in Table V; they are used above only for the E5 decomposition. The C0 and C7 rows of E4 and the t51 rows of E5 are separate sessions (C0 demand faults 339,251 against 339,386; D5 0.1051 against 0.1052 s).
