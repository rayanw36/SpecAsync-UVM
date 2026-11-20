# C22 IV-4: GraphBFS-23 repeated staging

Script `tests/c22_vi1_iv4.py`; sources `gate_e/e4/mechanism.csv` (`E4.mech.graphbfs.*`), `driver/src-e3a/uvm_gpu_replayable_faults.c`, `tests/e4_analyze.py:27` (287,956 distinct pages).

## The numbers in Table V (C6-W512, prefetcher off)

| counter | value | meaning |
|---|---|---|
| `spec_pages_requested` | 25,553,498 | sum of region sizes passed to `uvm_va_block_make_resident` by the worker (`uvm_gpu_replayable_faults.c:398-401`) |
| `spec_migrations` | 49,924 | worker items whose `make_resident` returned NV_OK (`uvm_gpu_replayable_faults.c:416-417`) |
| `enqueued` | 51,511 | predictions that passed the last-8-regions filter and were put on the queue |
| `ft_predictions` / `ft_same_region` | 73,496 / 21,502 | first-touch predictions made, and those suppressed because their W-page region equals one of the last 8 enqueued regions (`:2788-2799`) |
| `fault_already_resident` | 231,996 | demand-fault entries on pages already resident on the GPU (`:2019-2021`) |
| distinct pages touched | 287,956 | `tests/e4_analyze.py:27` |

## Can a page be requested more than once? Yes: counts and code

- Requested pages are *region sizes per processed item*, not predictions and not distinct pages: 25,553,498 / 512 = 49,909 items, equal within 0.03% to `spec_migrations` (49,924). The requested total is **88.7x** the distinct pages.
- The same 512-page region can be enqueued again because the duplicate filter remembers only the **last 8 enqueued regions** (`SPECASYNC_REGION_HISTORY` = 8, `specasync_internal.h:165`; the check at `uvm_gpu_replayable_faults.c:2788-2799`). A region that is no longer among the last 8 is enqueued again whenever another of its pages is predicted (follows from the code); that GraphBFS-23's weakened first-touch table does this much more than Stencil-24K is an inference from the counters (88.7x against 1.00x), not separately measured; the worker then calls `make_resident` on the whole 512-page region (`:398-401`), which does nothing for pages already resident but still adds 512 to the counter. Stencil-24K, in contrast, predicts sequentially, so `ft_same_region` removes 99.8% of its predictions and requested = 1,125,000 = its 1,125,000 distinct pages (1.00x).
- Cursor skips and drops: drops = 0; `lost_after_enqueue` = 1,579 (3.1% of the enqueued regions); `ft_predictions` = 73,496 against 15.1% of the 485,603 demand faults (the cursor yields a prediction only for part of the faults: the oracle cursor is weakened, coverage 0.22-0.81 across the C6 arms per CS2-N1).
- So `pages requested` counts **pages in the regions enqueued and processed (512 per item)**, which is why it is 89x the number of distinct pages; it is not a measure of staged working set. At W = 1 (C6-W1) it is 64,236 = one page per migration.

## What fraction of the distinct pages did the worker make resident?

The counters cannot give an exact distinct-page fraction: `fault_already_resident` counts fault entries, one per page serviced while already resident, and a page may fault more than once. As an upper bound on the distinct pages made resident ahead of their fault: `far_frac_distinct` = 231,996 / 287,956 = **80.6%** (C6-W512; C6-W1: 22.3%; C7-W512: 0.85%; C7-W1: 0.22%). Pages staged but never faulted afterwards (mapped by the prefetcher, or never touched) are not counted either, so the true staged set could be larger than this fraction.

## Reconciling with Section IV: "the graph oracle stages only part of the working set"

The sentence is consistent with the counters: with the prefetcher off and W = 512 the worker made at most 81% of the distinct pages resident before their fault (against 99.95% on Stencil-24K), and with W = 1 only 22%; and the cursor produced 73,496 predictions for 485,603 demand faults. The 25.6 million requested pages do not contradict it: they are repeated 512-page region requests (49,909 of them), not distinct staged pages, and the 21,502 suppressed predictions show that the last-8-regions filter removes only part of the repetition. Wording suggestion for the table note (not applied): "pages requested" counts the pages of every region passed to the migration call, so it exceeds the distinct page count whenever a region is requested more than once.
