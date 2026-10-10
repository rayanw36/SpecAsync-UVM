# Section III source checks (Gate C5 step 2; read-only)

Source: the pristine DKMS tree for driver **595.91.07**, `/usr/src/nvidia-595.91.07/nvidia-uvm/` (the tree the stock module is built from; `uvm_perf_prefetch.c` is
unmodified in every module used, see `CPU_FAULT_CHECK.md`). Nothing was run. `paper/section3_background.tex` is **not edited**.

## [SRC-1] D5 classification on 595.91.07: HOLDS

`D5_CHARACTERIZATION.md` classified the D5 span on **595.71.05** as CPU work plus an asynchronous GPU submit, with one wait that is gated on a CPU destination. **The 595.71.05 tree is not on this machine
(it was the T4 instance), so this is not a diff of two source trees.** What was checked is that every function the characterization cites starts at the **same line** in 595.91.07 as the 595.71.05 trace recorded, and that the
classifying code is as quoted.

| function (`uvm_va_block.c`) | 595.71.05 (D5_CHARACTERIZATION §2) | 595.91.07 (this check) |
|---|---|---|
| `uvm_va_block_service_locked` | `12021` (12021-12074) | `12021` (ends `12073`) |
| `uvm_va_block_service_copy` | `11541` (11541-11686) | `11541` (ends `11685`) |
| `uvm_va_block_make_resident_copy` | `4740` (4740-4846) | `4740` (ends `4845`) |
| `block_copy_begin_push` | `3267` | `3267` |
| `block_copy_pages` | `3787` | `3787` |
| `block_copy_end_push` | `3737` | `3737` |
| `block_copy_resident_pages_between` | `3907` | `3907` |
| `uvm_va_block_service_finish` | `11926` | `11926` |
| **`uvm_push_end(push)`** (not `uvm_push_end_and_wait`) in `block_copy_end_push` | `3749` | **`3749`** |
| `uvm_tracker_add_push_safe(copy_tracker, push)` | `3754` | **`3754`** |
| the gated `uvm_tracker_wait(&va_block->tracker)` in `uvm_va_block_service_copy` | `11633` | **`11633`** |

- The gate is as quoted: `if (service_context->operation == UVM_SERVICE_OPERATION_REPLAYABLE_FAULTS && UVM_ID_IS_CPU(new_residency) && !uvm_processor_mask_empty(all_involved_processors))` at `uvm_va_block.c:11625-11628`, the wait at `:11633`,
  with the comment "make sure all of the GPU work is finished" before checking ECC and NVLINK errors. It fires only for a CPU destination.
- In `uvm_gpu_replayable_faults.c` (pristine) `service_fault_batch_dispatch` is at `1927` (the characterization's number for the pristine 595.71.05 file) and `service_fault_batch_block` at `1585` (the characterization's `1923` is the SpecAsync-instrumented file's numbering).
  The batch tracker merge `uvm_tracker_add_tracker_safe(&batch_context->tracker, &va_block->tracker)` is at `:1615` and does not wait.
- **Three other `uvm_tracker_wait` / `uvm_push_wait` calls fall inside the line ranges the characterization traced and are not mentioned there.** None is on the GPU-destination, non-confidential path:
  - `uvm_va_block.c:3354` inside `block_copy_begin_push` (3267-3386): `uvm_tracker_wait(&local_tracker)`, inside `if (g_uvm_global.conf_computing_enabled)` (`:3332`) and only for `channel_type == UVM_CHANNEL_TYPE_CPU_TO_GPU`: **Confidential Computing only**;
  - `uvm_va_block.c:3659` `uvm_push_wait(push)` in `conf_computing_copy_pages_finish` (`:3641`), called from `block_copy_end_push` only `if ... is_cc_sysmem_copy(copy_state)` (`:3751-3752`) and returning early for a GPU destination (`:3654-3655`): **Confidential Computing only**;
  - `uvm_va_block.c:3809` `uvm_tracker_wait(&va_block->tracker)` in `block_copy_pages` (3787-3830), in the **CPU-to-CPU `memcpy`** branch ("CPU-to-CPU copies using memcpy() don't have any inherent ordering with copies using GPU CEs"): not a GPU-destination migration.
- **Verdict: the "CPU work plus async-submit" classification holds on 595.91.07** for GPU-destination faults without Confidential Computing. The characterization's statement "the only `uvm_tracker_wait` in the chain is the gated one" is **incomplete**: the three above exist and are inapplicable; a one-line caveat would make it exact.
- **Limit of this check:** it compares line numbers and the quoted code, not the two source trees line by line (595.71.05 unavailable). Identical start lines for 8 functions and identical lines for the three key statements are strong, but not a proof of byte-identity.

## [SRC-2] Eviction (`uvm_pmm_gpu.c`, with callers in `uvm_va_block.c`)

**Eviction unit: a root chunk of 2 MB, carried out one VA block at a time.**
- Root chunk size is the maximum chunk size: `UVM_CHUNK_SIZE_2M = 2*1024*1024`, `UVM_CHUNK_SIZE_MAX = UVM_CHUNK_SIZE_2M` (`uvm_pmm_gpu.h:89-90`). Victims are always root chunks: `root_chunk_update_eviction_list` asserts `uvm_gpu_chunk_get_size(chunk) == UVM_CHUNK_SIZE_MAX` (`uvm_pmm_gpu.c:1424`).
- `evict_root_chunk` (`:1291`) pins all the free subchunks, then loops `find_and_retain_va_block_to_evict` (`:1305`) and **`evict_root_chunk_from_va_block` (`:1157`) once per VA block** that has pages backed by that root chunk, which locks the block and calls `uvm_va_block_evict_chunks(va_block, gpu, &root_chunk->chunk, &tracker)` (`:1173`). The overview comment: "all resident pages backed by it are moved to the CPU one VA block at a time" (`:111-114`).
- So eviction is **per root chunk (2 MB), and within it per VA block**: not per 4 KB page and not per 64 KB big page.

**Victim selection: `pick_root_chunk_to_evict` (`:1487`).**
```c
// Check if there are root chunks sitting in the free lists. Non-zero chunks are preferred.
chunk = list_first_chunk(find_free_list(pmm, UVM_PMM_GPU_MEMORY_TYPE_USER, UVM_CHUNK_SIZE_MAX, UVM_PMM_LIST_NO_ZERO));
if (!chunk) { chunk = list_first_chunk(find_free_list(..., UVM_CHUNK_SIZE_MAX, UVM_PMM_LIST_ZERO)); }
// TODO: Bug 1765193: Move the chunks to the tail of the used list whenever they get mapped.
if (!chunk)
    chunk = get_first_allocated_chunk(pmm);
```
1. **Free root chunks first** (non-zeroed before zeroed); nothing needs migrating for them.
2. Otherwise the **head of the first non-empty allocated list** (`get_first_allocated_chunk`, `:1472-1485`), scanning `UVM_PMM_ALLOC_LIST_UNUSED`, then `DISCARDED`, then `USED` (`uvm_pmm_gpu.h:189-200`): unused root chunks (allocated, no resident pages: "these take priority ... as no data needs to be migrated"), then discarded, then used.
3. **Within a list the order is allocation-order LRU, not access recency.** The file comment says the lists are "LRU lists" and that "a root chunk is moved to the tail of the used list whenever any of its subchunks is allocated (unpinned) by a VA block" (`uvm_pmm_gpu.c:101-105`; `root_chunk_update_eviction_list`, `:1420-1436`, `list_move_tail`), and the code itself records **"TODO: Bug 1765193: Move the chunks to the tail of the used list whenever they get mapped"** (`:1510-1511`), i.e. a chunk is **not** refreshed when it is touched or mapped. The head is therefore the chunk whose last subchunk allocation is oldest.
- The UNUSED list is approximate and tracks "unused chunks only from root chunk sized (2M) VA blocks" (`uvm_pmm_gpu.h:183-188`); it is updated by `uvm_pmm_gpu_mark_root_chunk_unused` from `uvm_va_block.c:3435` and `:12279`, and USED from `:3401`.

**Consequence for Section III's wording** ("the driver selects victims at block granularity"): consistent (a 2 MB root chunk is the size of a VA block, and the eviction work is per VA block), with the added precision that the unit is the 2 MB root chunk, victim choice is oldest-allocated and **not** access-based, and the driver prefers chunks that hold no data. The citation to Go et al. and Ganguly et al. is not needed for these facts; they are in the source.

## [SRC-3] CPU faults and the density prefetcher: **YES, the same threshold**

`CPU_FAULT_CHECK.md` (C4 step 5a) already traced from `uvm_va_block_cpu_fault` down to the density test. This check adds the **upstream** part, from the kernel's page-fault handler to that function, and finishes the trace:

| step | where |
|---|---|
| kernel `vm_operations_struct .fault = uvm_vm_fault_entry` | `uvm.c:573` |
| `uvm_vm_fault_entry` -> `uvm_vm_fault` -> `uvm_va_space_cpu_fault_managed(va_space, vmf)` | `uvm.c:564`, `:558-561` |
| `uvm_va_space_cpu_fault_managed` (`uvm_va_space.c:2701`) -> `uvm_va_space_cpu_fault` (`:2491`) | `uvm_va_space.c:2701`, `:2491` |
| `uvm_va_block_cpu_fault(va_block, fault_addr, is_write, service_context)` | called at `uvm_va_space.c:2646`; defined `uvm_va_block.c:12476` |
| `block_cpu_fault_locked` (`:12358`) -> `uvm_va_block_service_locked(UVM_ID_CPU, ...)` | `uvm_va_block.c:12507`, `:12467` |
| `uvm_va_block_service_locked` -> `uvm_va_block_get_prefetch_hint` | `uvm_va_block.c:12046` (defined `:11487`) |
| -> `uvm_perf_prefetch_get_hint_va_block` | `uvm_va_block.c:11504`; defined `uvm_perf_prefetch.c:488` |
| -> `uvm_perf_prefetch_prenotify_fault_migrations` -> `compute_prefetch_mask` (`:295`) -> `compute_prefetch_region` | `uvm_perf_prefetch.c:408-431`, `:295`, `:102` |
| the strict test with the global threshold | **`uvm_perf_prefetch.c:118`**: `if (counter * 100 > subregion_pages * g_uvm_perf_prefetch_threshold)` |

The threshold has **one definition and one use** (parameter `:48`/`:60`, validated into `g_uvm_perf_prefetch_threshold` at `:552-560`, used at `:118`), so a CPU fault and a GPU fault see the same value. On a CPU fault the destination is the CPU
(`uvm_va_block_service_locked(UVM_ID_CPU, ...)`, `uvm_va_block.c:12467`) and the bitmap is built from the CPU's resident mask (`uvm_perf_prefetch.c:396-397`). With no preferred location set, `should_apply_prefetch_logic` returns true
("No preferred location set - always allow prefetching", `uvm_perf_prefetch.c:329-330`). `CPU_FAULT_CHECK.md` already contains the E9 phase split and the E8 estimate that complete C4 step 5 (see step 3 of C5).

## Statements in Section III checked against source

| # | Section III statement (`paper/section3_background.tex`) | verdict | evidence |
|---|---|---|---|
| 1 | "faulted pages are first widened to their 64 KB region" in the density bitmap | **CONFIRMED**, with two qualifiers | `update_bitmap_tree_from_va_block` (`uvm_perf_prefetch.c:239-281`): "Assume big pages by default. Prefetch the rest of 4KB subregions within the big page region unless there is thrashing" (`:274-276`) calls `grow_fault_granularity` (`:164-215`), which fills each 64 KB big-page region that contains a faulted page (`grow_fault_granularity_if_no_thrashing`, `:148-161`; `UVM_BIG_PAGE_SIZE = UVM_PAGE_SIZE_64K`, `uvm_va_block_types.h:52`). **Qualifiers:** (a) a region containing a thrashing page is **not** widened; (b) if the block has **no big-page region** (`big_pages_region.outer == 0`) the **whole prefetch region** is filled instead (`:173-181`, "Migrate whole block if no big pages and no page in it is thrashing"); the prefix and suffix around the big pages are widened as whole regions too (`:183-212`) |
| 2 | "at 0 it passes for any subregion containing a single counted page, so the whole region the prefetcher considers is taken on the first fault in it" | **CONFIRMED** | `counter * 100 > subregion_pages * 0` is `counter > 0` (`uvm_perf_prefetch.c:118`); `compute_prefetch_region` keeps the **largest** passing subregion in a leaf-to-root walk (`:109-120`), and the root contains the (widened) faulted page, so the prefetch region is the whole `max_prefetch_region`, which for a non-HMM block is the whole VA block (`uvm_perf_prefetch.c:391`). **Qualifiers:** pages that are thrashing are left out (`:418-422`, `:447-449`); and "taken" means added to the service set, with the copy limited to non-resident pages (statement 3). At 100 the test cannot pass (`counter <= subregion_pages` is asserted at `:117`) |
| 3 | "Its non-resident pages are added to the batch's destination set and marked as prefetches" | **WRONG (imprecise)** | **All** pages of the prefetch region other than the faulted ones are added and marked, **resident or not**. `uvm_perf_prefetch_prenotify_fault_migrations` removes only the faulted pages (`:432-433`), CPU-mapped pages for a CPU destination (`:440-445`) and thrashing pages (`:447-449`), **not** pages already resident on the destination. `uvm_va_block_get_prefetch_hint` marks every page in the hint `UVM_FAULT_ACCESS_TYPE_PREFETCH` (`uvm_va_block.c:11517-11521`) and ORs the whole mask into `new_residency_mask` (`:11532`). Residency is applied later, at copy time: `block_copy_resident_pages` computes `copy_page_mask = page_mask & ~resident_mask` (`:4537`), so only non-resident pages are copied. This is consistent with Section III's own later sentence ("including pages that needed no copy because they were already resident"). **Correct wording:** "Every page of the prefetch region other than the faulted ones, resident or not, is added to the batch's destination set and marked as a prefetch; the copy then moves only those not already resident." |
| 4 | the first-touch whole-block rule needs "resident nowhere" AND "preferred location == destination" (Section III: "the block is resident nowhere and the faulting GPU is the block's preferred location") | **CONFIRMED** | `if (uvm_processor_mask_empty(&va_block->resident) && uvm_id_equal(new_residency, policy->preferred_location)) uvm_page_mask_region_fill(prefetch_pages, max_prefetch_region);` (`uvm_perf_prefetch.c:404-407`). The test is against the **destination** (`new_residency`), which for a GPU fault is normally the faulting GPU; "faulting GPU" is a slight narrowing of "destination". An unset preferred location is not equal to any GPU, so the rule does not fire for the benchmarks (matches the paper's sentence), and `should_apply_prefetch_logic` then takes the density path (`:329-330`) |
| 5 | the fault batch drains a hardware fault buffer and replays after service | **CONFIRMED** | the ISR top half masks the interrupt and schedules a bottom half (`uvm_gpu_isr.c:99-116`); the bottom half runs `uvm_parent_gpu_service_replayable_faults` (`uvm_gpu_replayable_faults.c:2873`), whose loop does `fetch_fault_buffer_entries` (`:2898`), `preprocess_fault_batch` (`:2907`), `service_fault_batch` (`:2916`), then **replays according to the policy**: default `UVM_PERF_FAULT_REPLAY_POLICY_BATCH_FLUSH` (`:80`): flush the buffer and issue a replay after each batch (`fault_buffer_flush_locked(..., UVM_FAULT_REPLAY_TYPE_START, ...)`, `:2957-2969`) and wait for the replay (`uvm_tracker_wait(&replayable_faults->replay_tracker)`, `:2969`); policy `BATCH` replays after each batch (`:2951-2956`); policy `ONCE` replays once at the end (`:2985`). "Replays after service" is exact for the default policy |

## Other observations

- **Section III's header comment `[SRC-2]` says eviction granularity and policy "is cited from [go2023earlyadaptor, ganguly2019interplay], not read" from source.** It is now read: see SRC-2. The two citations in the sentence at `section3_background.tex:200-201` can stay for context, but the facts do not depend on them.
- **Section III's "[SRC-1] NOT re-traced on 595.91.07"** is resolved by SRC-1 above (with the caveat that the 595.71.05 tree was unavailable).
- No claim was found WRONG other than statement 3, and none NOT FOUND.
