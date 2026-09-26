# Gate E5 Step 1 — Source check: does speculation help by feeding the prefetcher?

Read-only, before any run. Source: pristine `/usr/src/nvidia-595.91.07/nvidia-uvm/`
(the DKMS copy of `kernel-open/nvidia-uvm/`). The SpecAsync build tree's
`uvm_perf_prefetch.c` and `uvm_perf_prefetch.h` are **byte-identical** to it
(`cmp`), and no 595 SpecAsync patch touches the prefetcher.

## 1. Does the density test count already-resident pages? — **Yes. The H-feed premise holds.**

- `uvm_perf_prefetch_prenotify_fault_migrations()` (`uvm_perf_prefetch.c:365`)
  takes `resident_mask = uvm_va_block_resident_mask_get(va_block,
  new_residency, NUMA_NO_NODE)`. That is the **destination processor's**
  resident mask (`:396-397`). It is taken when the destination is the CPU or
  has GPU state in the block, which it does once the worker has made pages
  resident there.
- `init_bitmap_tree_from_region()` builds the density bitmap as
  **`resident_mask | faulted_pages`**: `uvm_page_mask_or(&bitmap_tree->pages,
  resident_mask, faulted_pages)` (`:226-227`). Here `faulted_pages` is the
  demand path's `new_residency` mask (`uvm_va_block.c:11504`).
- `update_bitmap_tree_from_va_block()` → `grow_fault_granularity()`
  (`:276`, `:164-219`) then sets every 64 KB big-page region that contains a
  faulted page and is not thrashing (`uvm_page_mask_region_fill`, `:160`).
- `compute_prefetch_region()` (`:102-146`) counts set bits per subregion,
  `uvm_perf_prefetch_bitmap_tree_iter_get_count` →
  `uvm_page_mask_region_weight(&bitmap_tree->pages, …)` (`:94-100`), up the
  tree from the faulting page.
- **Residency is the only input.** Mapping state does not enter the count.
  A page the speculative worker made resident on the GPU, resident but
  unmapped, therefore **counts** toward the density share.

## 2. Does the service step map prefetched pages that are already resident? — **Yes.**

- `uvm_va_block_get_prefetch_hint()` (`uvm_va_block.c:11487`) ORs the
  prefetch mask into the demand path's `new_residency_mask`
  (`uvm_page_mask_or(new_residency_mask, new_residency_mask,
  prefetch_pages_mask)`, `:11532`). It marks those pages
  `UVM_FAULT_ACCESS_TYPE_PREFETCH` (`:11520`).
- `uvm_va_block_service_finish()` (`:11926`) computes
  `did_not_migrate_mask = new_residency_mask & ~did_migrate_mask` (`:11947`).
  That mask records pages that needed no migration, **but it does not remove
  them.**
- The protection loop then runs over **every page in `new_residency_mask`**
  (`for_each_va_block_page_in_region_mask(page_index, new_residency_mask,
  …)`, `:11961`).
- `block_service_finish_map()` (`:11981`, defined at `:11770`) maps each
  protection group.
- **A prefetched page that is already resident is mapped in the same service
  step as the fault that triggered the prefetch.**

## 3. The threshold parameter

| item | source | value |
|---|---|---|
| declaration | `static unsigned uvm_perf_prefetch_threshold = UVM_PREFETCH_THRESHOLD_DEFAULT;` (`:48`); default **51** (`:42`) | percent |
| module parameter | `module_param(uvm_perf_prefetch_threshold, uint, S_IRUGO);` (`:60`) | **settable at `insmod`**, readable at `/sys/module/nvidia_uvm/parameters/uvm_perf_prefetch_threshold` (0444). The read-back shows the raw parameter. |
| accepted range | `uvm_perf_prefetch_init()`: `if (uvm_perf_prefetch_threshold <= 100) g_… = it; else { UVM_INFO_PRINT("Invalid value …"); g_… = 51; }` (`:552-561`) | **0–100**. A larger value **silently falls back to 51**, while read-back still shows the raw value, so T_off must be ≤ 100. |
| comparison | `if (counter * 100 > subregion_pages * g_uvm_perf_prefetch_threshold) prefetch_region = subregion;` (`:118`) | **strict `>`**, in percent of the subregion's pages. The largest qualifying ancestor wins. |
| invariant | `UVM_ASSERT(counter <= subregion_pages);` (`:117`) | a bit count over the subregion cannot exceed its size |
| **T_off** | at threshold 100 the test is `counter·100 > subregion_pages·100`, i.e. `counter > subregion_pages`, which is impossible | **T_off = 100**: the density rule can never fire, at any level, including the leaf (1·100 > 1·100 is false) |

## 4. What prefetch behaviour survives at T_off = 100

`prefetch_pages` is written in exactly **two** places in
`uvm_perf_prefetch.c`:

| path | source | at T_off, for Stencil-24K |
|---|---|---|
| (a) **density rule** via `compute_prefetch_mask()` → `compute_prefetch_region()` | `:283-303`, `:297` | **never fires** (item 3) |
| (b) **first-touch whole-block population**: `if (uvm_processor_mask_empty(&va_block->resident) && uvm_id_equal(new_residency, policy->preferred_location)) uvm_page_mask_region_fill(prefetch_pages, max_prefetch_region);` | `:404-407` | **cannot fire for Stencil's GPU faults.** It needs the block to be resident *nowhere* **and** the GPU to be the preferred location. `benchmarks/bench_stencil.cu` sets no preferred location (no `cudaMemAdvise`; lines 88-99 are `cudaMallocManaged` followed by host initialisation of every element), so `preferred_location` is invalid and `uvm_id_equal(GPU, invalid)` is false. The host writes every page first, so the block is already CPU-resident when the GPU first faults. |

**Named alternatives, and why none should map speculatively-resident pages
at T_off:**

- **64 KB big-page growth (`grow_fault_granularity`, `:148-219`).** It only
  fills big-page regions in the **density bitmap** (`:160`), which inflates
  the count. It never writes `prefetch_pages` itself. At T_off its inflated
  count still cannot pass the impossible test, so it is **inert**.
- **First-touch whole-block population (`:404-407`).** As above, it does not
  apply to Stencil's GPU faults.
- **PTE-size merging on the demand path (`block_gpu_compute_new_pte_state`,
  `uvm_va_block.c:7329`).** Its documented contract is to merge PTEs only
  over pages that *"will have exactly the same PTE attributes (permissions,
  residency) … after the operation"*. That means pages being mapped plus
  pages already mapped the same way. A resident but **unmapped** page has no
  valid PTE, so it cannot be absorbed into a 64 KB or 2 MB PTE unless it is
  in the mapping mask. This is read from the contract comment and not traced
  through every branch. It is named as the residual candidate should faults
  still drop at T_off.

**Consequence for the test.** At T_off, `uvm_perf_prefetch_enable=1`, so the
hint is still computed and costs time, but for Stencil it yields **no
prefetch pages**. The demand path then maps only the faulting pages.

- If H-feed holds, C7W512's fault reduction should essentially vanish at
  T_off.
- C0-toff should behave like prefetch-off. E4's C1 (prefetch off) median was
  4.30 s and C6-W512 was 3.30 s, both far inside the 22 s timeout.

**Verdict of the source check.** Resident pages *do* count (item 1), and
prefetched already-resident pages *are* mapped (item 2). H-feed is **not
refuted from source**, so Step 3's hypothesis test proceeds as
pre-registered.
