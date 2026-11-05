# H0 mapping trace: are prefetched pages mapped on the HMM GPU-fault path? (Gate C9 phase 2; read-only)

Source: `/usr/src/nvidia-595.91.07/nvidia-uvm/` (pristine DKMS copy). Closes the open item of `H0_REPORT.md` ("`uvm_hmm_gpu_fault_finalize_and_map` ... not traced").

## Verdict: **MAPS** (same step, same mapping code as the managed path), with three stated exceptions that do not occur in the H1 benchmarks

## 1. Are prefetched pages mapped for the faulting GPU in the same service step?
Yes. The chain, in order:
1. `uvm_va_block_service_locked` calls `uvm_va_block_get_prefetch_hint` (`uvm_va_block.c:12046`), which ORs the prefetch pages into the destination's `new_residency` mask and widens `service_context->region` to the span of that mask (`uvm_va_block.c:11532-11533`); it also marks them `UVM_FAULT_ACCESS_TYPE_PREFETCH`.
2. It then dispatches HMM blocks to `uvm_hmm_va_block_service_locked` (`uvm_va_block.c:12051-12060`; `uvm_hmm.c:3040`).
3. For a GPU destination the migration mask is **a copy of that same `new_residency` mask**, prefetch pages included: `uvm_page_mask_copy(page_mask, &service_context->per_processor_masks[...].new_residency)` (`uvm_hmm.c:2961-2962`, in `uvm_hmm_gpu_fault_alloc_and_copy`). GPU 4 KB chunks for the whole mask are allocated first by `uvm_va_block_populate_pages_gpu` (`uvm_hmm.c:3116`).
4. `dmamap_src_sysmem_and_fill_dst` (`uvm_hmm.c:2830`, called at `:2964`) walks the mask, DMA-maps the CPU source pages and fills `dst_pfns[]`; `uvm_va_block_service_copy` (`:2978`, the managed path's copy function) does the copy.
5. `migrate_vma_pages(args)` (`uvm_hmm.c:3168`) commits, then **`uvm_hmm_gpu_fault_finalize_and_map`** (`:2985`, called at `:3169`) removes from the mask the pages that did not migrate (`:3007-3023`, loop at `:3012`) and, if any remain, calls **`uvm_va_block_service_finish(processor_id, va_block, service_context)`** (`uvm_hmm.c:3028`). That is the same function the managed path calls.
6. `uvm_va_block_service_finish` (`uvm_va_block.c:11926`) computes the new permission for **every page in `new_residency_mask`** over the service region (the loop at `:11961-11973`, which builds `mappings_by_prot`), then maps the faulting processor with `block_service_finish_map` (`:11981`, defined `:11770`). So the prefetch pages that migrated are mapped for the faulting GPU **in the same step, by the same code**, with the permission from `compute_new_permission` (`uvm_va_block.c:10714`; for an HMM block the logical protection comes from the VMA, `compute_logical_prot(va_block, hmm_vma, page_index)`, `:10730`, `:7921`).

HMM-specific difference in that mapping code: `block_service_finish_map` skips the "unmap CPU pages first" step for HMM blocks (`uvm_va_block.c:11785-11790`: "HMM cpu mappings can be upgraded at any time"). It affects CPU destinations only.

## 2. Is the prefetch region clamped, and to what?
- **At the prefetcher:** `max_prefetch_region` for an HMM block is `uvm_hmm_get_prefetch_region` (`uvm_perf_prefetch.c:384-388`): the intersection of the block, the VMA (`start = max(block->start, vma->vm_start)`, `end = min(block->end, vma->vm_end - 1)`) and the policy range or policy-free hole (`uvm_hmm.c:1553-1583`). A 2 MB-aligned block inside a large malloc'd VMA is therefore **not clamped** (only the first and last blocks of the allocation can be).
- **At migration:** the service region is the span of the mask (`uvm_va_block.c:11533`), passed as `args->start`/`args->end` to `migrate_vma_setup` (`uvm_hmm.c:3136-3137`) with `MIGRATE_VMA_SELECT_DEVICE_PRIVATE | MIGRATE_VMA_SELECT_SYSTEM` (`:3138`). Only pages in `page_mask` get a `dst_pfn` (`dmamap_src_sysmem_and_fill_dst` iterates the mask only); pages in the span but not in the mask are not migrated.
- **GPU granularity:** HMM GPU chunks are PAGE_SIZE (`uvm_va_block.c:3396-3397`, `:7347-7355`), so each prefetched page is its own device-private page and its own mapping entry.

## 3. Does `migrate_vma` skip pages the prefetcher asked for?
Yes, in these cases; each such page is **dropped from the service masks and not mapped**, and is simply faulted again if touched:
1. **Pages without `MIGRATE_PFN_MIGRATE` after `migrate_vma_setup`**: "HMM currently has some limitations on what pages can be migrated. For example, no file backed pages, device private pages owned by a different device, device exclusive or swapped out pages" (`uvm_hmm.c:2856-2858`, `goto clr_mask`); the same set is cleared again after `migrate_vma_pages` (`:3007-3023`). Pages the kernel cannot isolate (locked, or with extra references such as pins) fall under the same flag.
2. **Swap-cached pages** (`nv_PageSwapCache`, `uvm_hmm.c:2872`): the whole attempt returns `NV_WARN_MISMATCHED_TARGET` (a known limitation, "Bug 4050579").
3. **Failures to insert the source page into the block** (`hmm_va_block_cpu_page_insert_or_replace`, `:2882`).
If **no** page migrates, the function returns `NV_WARN_MORE_PROCESSING_REQUIRED` (`uvm_hmm.c:2929`, `:3025`) and `uvm_hmm_va_block_service_locked` makes the pages resident on the CPU and asks for a retry (`hmm_make_resident_cpu`, `:3156`).
**Not skipped:** a source page that does not exist yet (anonymous memory never touched by the CPU) is migrated as an empty page and a zero page is allocated on the GPU (`uvm_hmm.c:2893-2896`, "It is OK to migrate an empty anonymous page"). So the prefetcher can populate GPU pages for host-untouched pages; the H1 benchmarks initialise every page on the host first, so this does not arise there.

## 4. What this means for H1
- The GPU-side threshold mechanism is intact on HMM: the density rule decides the service mask, and the mask's pages are copied and mapped in the same step as for managed memory. A malloc'd threshold sweep tests the same mechanism.
- Exceptions 1-3 concern file-backed, swapped, pinned or foreign device-private pages. `aligned_alloc` anonymous memory that is host-written and not swapped has none of them, **provided no page is pinned by another path** (CUDA does not pin a pageable allocation for kernel access on this configuration). Not verified at run time: the benchmark has no counter for dropped pages, so a dropped page would show only as extra faults. H1 records the GPU fault evidence the stock module exposes; if none exists that is recorded and the wall-clock difference between thresholds is relied on, as the brief says.

Phase 3 of C9 (benchmark flag, validation, pre-registration) and phase 4 (the runs) may therefore proceed.
