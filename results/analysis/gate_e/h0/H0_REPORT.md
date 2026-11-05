# Gate H0: can the threshold result be tested on HMM-managed (malloc'd) memory?

Read-only source and platform check, plus one capability query (`tests/h0_caps.cu`, output `h0_caps_output.txt`; no timing, no allocation). Driver source: `/usr/src/nvidia-595.91.07/nvidia-uvm/` (pristine DKMS copy, abbreviated below by file name only). Host: RTX 5070 Ti, kernel 7.0.0-34-generic, stock `nvidia_uvm` srcversion 6284DA42F15EDC3AB92332B, threshold 51. No benchmark was run, no module was loaded.

## Verdict: **A** (same prefetcher, same threshold; a malloc'd threshold sweep is valid on the GPU side), with one structural caveat

The two decisive citations:
1. `uvm_va_block.c:12046` `uvm_va_block_get_prefetch_hint(...)` is called in `uvm_va_block_service_locked` **before** the `uvm_va_block_is_hmm(va_block)` dispatch at `:12051-12060`, so HMM blocks go through the same density prefetcher (`uvm_perf_prefetch_get_hint_va_block`, `uvm_va_block.c:11504`).
2. `uvm_perf_prefetch.c:118` `if (counter * 100 > subregion_pages * g_uvm_perf_prefetch_threshold)` is the only use of the threshold; `uvm_perf_prefetch.c` mentions HMM at three places only (`:384`, `:440`, `:502`), none of which gates prefetching off or changes the threshold.

**The caveat:** the CPU side differs. Host initialisation of a malloc'd array is ordinary Linux page faulting, **not** UVM CPU faults, so the E9 mechanism "threshold 0 populates each 2 MB block on its first CPU fault" (CS2-N10, `E9.cpu_phase.*`) has no HMM counterpart. Any HMM wall-clock difference by threshold is therefore GPU-side only; this is a cleaner measurement of the GPU-fault effect, and a different experiment from E8.

## 1a. How a GPU fault on HMM memory is serviced
| step | function | file:line |
|---|---|---|
| batch of coalesced faults | `service_fault_batch_dispatch` | `uvm_gpu_replayable_faults.c:1927` |
| no UVM `va_range` covers the address, a `mm` exists -> HMM block | `uvm_hmm_va_block_find_create(va_space, fault_address, &va_block_context->hmm.vma, &va_block)` | `uvm_gpu_replayable_faults.c:1951-1959` (the `if (va_range) ... else if (mm)` chain) |
| find or create the block | `hmm_va_block_find_create`: block = the 2 MB-aligned interval around the address, shrunk to avoid existing ranges and blocks; `mmu_interval_notifier_insert` | `uvm_hmm.c:614-700` (`UVM_VA_BLOCK_ALIGN_DOWN` at `:652`) |
| per-block service | `service_fault_batch_block` -> `uvm_va_block_service_locked(gpu->id, va_block, ...)` | `uvm_gpu_replayable_faults.c:1568` |
| prefetch hint (same for every block type) | `uvm_va_block_get_prefetch_hint` | `uvm_va_block.c:12046` (defined `:11487`) |
| dispatch | `if (uvm_va_block_is_hmm(va_block)) uvm_hmm_va_block_service_locked(...)` else `uvm_va_block_service_copy` + `uvm_va_block_service_finish` | `uvm_va_block.c:12051-12066` |
| HMM service: destination CPU -> `hmm_block_cpu_fault_locked`; destination GPU: pre-allocate GPU pages, then `migrate_vma_setup_locked` / `migrate_vma_pages` / `migrate_vma_finalize` with `MIGRATE_VMA_SELECT_DEVICE_PRIVATE \| MIGRATE_VMA_SELECT_SYSTEM`, then `uvm_hmm_gpu_fault_finalize_and_map` | `uvm_hmm.c:3040-3170` (flags at `:3130-3136`; `migrate_vma_setup_locked` `:3142`; `migrate_vma_pages` `:3168`; map `:3169`, defined `:2985`) |

The service region passed to `migrate_vma` is `service_context->region`, which the prefetch hint widened to cover the prefetch pages (`uvm_va_block.c:11532-11533`).

## 1b. Does it call the density prefetcher with the same `g_uvm_perf_prefetch_threshold`? **Yes.**
`uvm_va_block_get_prefetch_hint` (above) -> `uvm_perf_prefetch_get_hint_va_block` (`uvm_perf_prefetch.c:488`) -> `uvm_perf_prefetch_prenotify_fault_migrations` (`:365`) -> `compute_prefetch_region` -> the strict test at `:118`. One global threshold: parameter `:48`, `:60`; `g_uvm_perf_prefetch_threshold` `:64`. The enable switch is global (`uvm_perf_prefetch_enabled`, `:454-461`).

## 1c. Same bitmap? HMM-only restrictions
- **Same bitmap:** `init_bitmap_tree_from_region(bitmap_tree, max_prefetch_region, resident_mask, faulted_pages)` (`uvm_perf_prefetch.c:408-410`) with the destination's resident mask and the faulted pages, then `update_bitmap_tree_from_va_block` (the same 64 KB big-page widening, `:239-281`) and `compute_prefetch_mask`. Nothing in that sequence tests `uvm_va_block_is_hmm`. `uvm_va_block_big_page_region_subset` is address arithmetic (`uvm_va_block.c:2075-2091`), so the widening applies to HMM bitmaps; HMM GPU **PTEs** are 4 KB regardless (`uvm_va_block.c:7347-7355`: "Limit HMM GPU allocations to PAGE_SIZE ... migrate_vma_*() ... don't handle folios yet"), which does not change the bitmap.
- **HMM-only restrictions (all in `uvm_perf_prefetch_prenotify_fault_migrations`):**
  1. **`max_prefetch_region` is clamped:** for an HMM block it is `uvm_hmm_get_prefetch_region(...)` (`uvm_perf_prefetch.c:384-388`), which limits it to the VMA and to the policy range (`uvm_hmm.c:1553-1583`: `start = max(block->start, vma->vm_start)`, `end = min(block->end, vma->vm_end - 1)`, then the policy-tree hole or node). A managed block uses the whole block (`:391`). For a large malloc'd array the clamp only matters at the ends of the VMA.
  2. **No CPU-mapped exclusion** for a CPU destination (`:438-445`: "For HMM, we don't know what pages are mapped by the CPU unless we try to migrate them"). This affects CPU-destination faults only.
  3. **Thrashing and preferred-location handling are the same** (`:404-407`, `:447-449`). The first-touch whole-block rule needs `preferred_location == destination`; a malloc'd region has the default policy (no preferred location), so it does not fire, as for the benchmarks' managed memory.
  4. HMM blocks can be smaller than 2 MB (the interval-shrinking at `uvm_hmm.c:652-680`), so the bitmap tree can be built over fewer than 512 pages.
- Not restricted: no "prefetch disabled for HMM" condition exists in `uvm_perf_prefetch.c`.

## 1d. HMM eviction
- GPU memory for HMM is **device-private pages** (ZONE_DEVICE) backed by the same PMM chunks: `uvm_pmm_devmem_*` (`uvm_pmm_gpu.c:2950-3100`; `devmem_page_free` `:3024`; CPU access to a device-private page enters `devmem_fault` -> `uvm_va_space_cpu_fault_hmm`, `:3075-3097`, `.migrate_to_ram`).
- **Allocation unit: PAGE_SIZE.** "HMM always allocates PAGE_SIZE GPU chunks" (`uvm_va_block.c:3396-3397`); consequently HMM blocks are never marked as 2 MB used root chunks (`:3398`, `:3431`, `:12013`), so the PMM's UNUSED/USED bookkeeping (SRC-2) does not include them.
- **Victim selection is the same PMM root-chunk selection** (`pick_root_chunk_to_evict`, `uvm_pmm_gpu.c:1487`, 2 MB root chunks, free chunks first, then the head of the allocated lists; see `SECTION3_SOURCE_CHECKS.md` SRC-2). HMM chunks pin their root chunk the same way ("HMM evictions will end up here", `uvm_pmm_gpu.c:2271-2282`).
- **Eviction execution differs:** `uvm_va_block_evict_chunks` takes the HMM branch (`uvm_va_block.c:12948-12994`): `uvm_hmm_va_block_evict_chunk_prep` per chunk (`:12971`), then `uvm_hmm_va_block_evict_chunks` (`:12994`; `uvm_hmm.c:3621`) -> `hmm_va_block_evict_chunks` (`:3525-3617`) which moves pages to **system pages with `migrate_device_pages` / `migrate_device_finalize`** (`:3596-3617`), not UVM's own CE copy into CPU chunks. The unit evicted at a time is therefore "the pages of every HMM block that has a 4 KB chunk inside the victim 2 MB root chunk", per block, as for managed memory, but each page is a separate device-private page and a separate migration entry.
- Device-private pages also leave the GPU through `uvm_hmm_pmm_gpu_evict_pfn` (`uvm_hmm.c:235`, `migrate_device_range`), but that is the GPU-unregister path, not the oversubscription path.

## 1e. Module parameters gating HMM
- `uvm_disable_hmm` (`uvm_hmm.c:29-49`, 0444): default **false** on x86_64 (HMM enabled if possible). `uvm_hmm_is_enabled_system_wide` (`:141-159`) also requires: ATS not enabled (`g_uvm_global.ats.enabled`), Confidential Computing off, and `uvm_va_space_mm_enabled_system()`; per VA space `uvm_hmm_is_enabled` (`:161-166`) additionally needs the space's mm and not `UVM_INIT_FLAGS_DISABLE_HMM`.
- `uvm_enable_va_space_mm` (`uvm_va_space_mm.c:159`, default 1); `uvm_ats_mode` (`uvm_ats.c:29`, default 1: ATS is used only on hardware that supports it).
- Compile-time: `UVM_IS_CONFIG_HMM()` needs `CONFIG_HMM_MIRROR`, `CONFIG_DEVICE_PRIVATE` and `NV_MIGRATE_DEVICE_RANGE_PRESENT` (`uvm_linux.h:91`).

## 2. Platform (this host)
| item | value | source |
|---|---|---|
| `CONFIG_HMM_MIRROR` | y | `/boot/config-7.0.0-34-generic:1330` |
| `CONFIG_DEVICE_PRIVATE` | y | `:1332` |
| `CONFIG_ZONE_DEVICE` | y | `:1329` |
| `CONFIG_MIGRATION`, `CONFIG_DEVICE_MIGRATION` | y, y | `:1271`, `:1272` |
| `CONFIG_MMU_NOTIFIER` | y | `:1278` |
| `CONFIG_TRANSPARENT_HUGEPAGE` / mode | y / `madvise` (`/sys/kernel/mm/transparent_hugepage/enabled` = `always [madvise] never`); `CONFIG_ARCH_ENABLE_THP_MIGRATION=y` | `:1288-1291`, `:1274` |
| `uvm_disable_hmm` | `N` | `/sys/module/nvidia_uvm/parameters/uvm_disable_hmm` |
| `uvm_ats_mode` | 1 (ATS not in use on this PCIe GPU, see the attribute below) | `.../uvm_ats_mode` |
| `uvm_enable_va_space_mm` | 1 | `.../uvm_enable_va_space_mm` |
| `nvidia-smi -q` "Addressing Mode" | **HMM** | `nvidia-smi -q` |
| `nvidia_uvm` dmesg lines mentioning HMM | **none** (`sudo -n dmesg` reports no line matching hmm, nvidia-uvm, device private) | read-only |

## 3. Capability query (`tests/h0_caps.cu`, one run, `h0_caps_output.txt`)
```
cudaDevAttrPageableMemoryAccess = 1
cudaDevAttrPageableMemoryAccessUsesHostPageTables = 0
cudaDevAttrConcurrentManagedAccess = 1
CUDA driver version = 13020, runtime version = 13000
```
The GPU can access pageable (malloc'd) memory (1) **without** sharing the host page tables (0), which is the HMM mode (the value 1 would indicate ATS/coherent hardware). Concurrent managed access = 1. The driver reports CUDA 13.2 while the runtime used for the benchmarks is 13.0; the build used `nvcc` 13.0 (`sm_120`).

## 4. Feasibility: the exact change to the benchmarks (not made; no runs)
**`benchmarks/bench_sparse.cu`** (`:139`, `cudaMallocManaged(&arr, bytes)`; `:177-179` `cudaFree(arr)`): under `--sysalloc` (or an environment variable read in `main`), replace the allocation by `arr = (uint32_t*)aligned_alloc(2 << 20, bytes)` (bytes rounded up to 2 MiB; check for NULL), call `madvise(arr, bytes, MADV_NOHUGEPAGE)` (THP mode is `madvise`, so none is expected, but make it explicit), and replace `cudaFree(arr)` by `free(arr)`. `d_idx`, `d_acc`, the kernel, the checksum and the host initialisation loop (`:148`) are unchanged: the kernel already takes a raw pointer.
**`benchmarks/bench_stencil.cu`** (`:88-89` two `cudaMallocManaged`, `:134-135` `cudaFree`): the same substitution for `grid0` and `grid1`.
**Things that make the comparison unequal, to control or to record:**
1. **First-touch placement and host initialisation.** For managed memory the host init faults through UVM (CPU faults, governed by the threshold: `E9.cpu_phase.fill_only`). For malloc'd memory it is plain kernel page faulting: lower cost, and **independent of the threshold**. The wall-clock baseline therefore differs and the threshold effect on the host part vanishes (this is the structural caveat).
2. **THP:** UVM HMM does not handle huge pages (`uvm_va_block.c:7347-7355`, "Bug 3368756"). THP is `madvise`-only here and not requested, but `MADV_NOHUGEPAGE` should be set so a future kernel setting cannot change the page size silently.
3. **2 MB alignment:** UVM HMM blocks are 2 MB-aligned in the address space regardless of the allocation's alignment (`uvm_hmm.c:652`); `aligned_alloc(2 MiB)` keeps blocks whole at the ends. A mapping not 2 MB-aligned would create partial blocks and clamp the prefetch region (`uvm_hmm.c:1563-1564`).
4. **Page size on the GPU:** 4 KB PTEs only for HMM (`uvm_va_block.c:7347-7355`), against up to 2 MB for managed memory; the device-private page count is 512 per block, so each migration is 512 times more entries. The mechanism under test (the bitmap) is unchanged, the cost per migrated page differs, so absolute times are not comparable with E7/E8; only within-HMM threshold contrasts are.
5. **Host memory:** an oversubscribed 24 GiB array needs the same `MemAvailable` floor as E8 (30.4 GiB were available), plus the device-private bookkeeping (`struct page` for the device-private range is allocated at module load, not per array).
6. **No `cudaMemAdvise`/`cudaMemPrefetchAsync`** (as in E8) so the default policy applies and the first-touch whole-block rule does not fire.
7. **NUMA balancing is on** (`CONFIG_NUMA_BALANCING=y`): for malloc'd memory the kernel may migrate or unmap pages between CPU nodes (one node here), which can add host-side faults; record `numa_balancing` in the pre-registration.

## 5. Cells I would pre-register (mirroring E7 Family A and E8; not registered here)
Stock module, `uvm_perf_prefetch_enable=1`, thresholds {0, 25, 51}, n = 10, **malloc'd** allocation behind the flag:
- **Family A (confirmatory):** Stencil-24K, t0 vs t51 (one test; the E7 Family A analogue), and t10 vs t51 (descriptive).
- **Family B (sparse, E8 K in {1, 512}):** `bench_sparse`, size {8 GiB in memory, 24 GiB oversubscribed} x K {1, 512} x t {0, 25} vs t51 = 8 tests; one Holm family of 9 with Family A.
- **Control:** the same cells with `cudaMallocManaged` in the same session, so the managed-vs-HMM contrast is within-session; and E9-style nsys counts (HtoD/DtoH bytes) on 3 runs per cell for the mechanism, because the migrated bytes are the point of E9.
- Expectation to commit first (reviewer's): HMM follows the managed pattern in direction (K=512 faster at t0; K=1 oversubscribed slower at t0); the host-initialisation share of the t0 gain is absent.

## 6. Section III statements that would be wrong or need a qualifier for HMM memory (`paper/section3_background.tex`)
- Line 61: "UVM manages memory in VA blocks: aligned 2 MB regions of virtual ..." is true for managed ranges; HMM blocks are created on demand, 2 MB-aligned but **shrunk** around existing ranges and blocks, and clamped to the VMA for prefetching.
- Lines 149-151, 174: the prefetch region is "the block's pages" (managed). For HMM: the VMA/policy-clamped region.
- Lines 190-191 (first-touch whole-block rule) is unchanged (needs a preferred location).
- Lines 199-200 (eviction "at block granularity"; SRC-2 root chunk of 2 MB): victim selection is the same, but HMM chunks are PAGE_SIZE and eviction runs through `migrate_device_pages`.
- Lines 129-130 (the mapping step `block_service_finish_map`): the HMM path maps in its own `uvm_hmm_gpu_fault_finalize_and_map` (`uvm_hmm.c:2985`), **not traced here**; that prefetched pages are mapped on HMM is plausible (the service region includes them) but unverified.
- The CPU-fault statements added by C4/C6 (CS2-N10's mechanism bullet) are specific to managed memory.

## Open items
- Whether `uvm_hmm_gpu_fault_finalize_and_map` maps every page of `service_context->region` or only the migrated ones was not traced.
- The `nvidia_uvm` dmesg has no HMM line; this is consistent with HMM being enabled without a message, not a proof (the `nvidia-smi` "Addressing Mode: HMM" line and the attribute pair are the evidence).
