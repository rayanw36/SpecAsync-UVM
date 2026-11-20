# C22 III-1: eviction order in the 595.91.07 driver (read-only)

Source: pristine `/usr/src/nvidia-595.91.07/nvidia-uvm/` (the unmodified distribution tree; `uvm_pmm_gpu.c` md5 `72ca4ee9...`, `uvm_va_block.c` md5 `61352e13...`). No module loaded, nothing run. Section III-D says victims are chosen "in allocation order, not by recency of access".

## Which function moves a root chunk to the tail of an eviction list
1. **`root_chunk_update_eviction_list`** (`uvm_pmm_gpu.c:1420-1437`): takes `pmm->list_lock` and, if the root chunk is not pinned and not already in eviction, does `list_move_tail(&chunk->list, &pmm->root_chunks.alloc_list[alloc_list])` (`:1434`). Three thin wrappers pick the list: `uvm_pmm_gpu_mark_root_chunk_used` -> `UVM_PMM_ALLOC_LIST_USED` (`:1440-1443`), `..._unused` -> `UNUSED` (`:1445-1448`), `..._discarded` -> `DISCARDED` (`:1450-1453`).
2. **`chunk_update_lists_locked`** (`uvm_pmm_gpu.c:640-663`): for a user chunk whose root is not pinned and not free it does `list_move_tail(&root_chunk->chunk.list, &...alloc_list[UVM_PMM_ALLOC_LIST_USED])` (`:655`). It runs when a chunk is claimed or initialised (`:1685` in `claim_free_chunk`, `:1918` in `init_root_chunk`), when it is unpinned after allocation (`uvm_pmm_gpu_unpin_allocated`, `:670-678`) and when it is freed (`:2304`).

## On which events is it called
- **Allocation:** yes. A new root chunk is placed at the tail of the USED list through `chunk_update_lists_locked` (above).
- **Callers in `uvm_va_block.c`:** `block_mark_memory_used` (`:3387-3403`) calls `uvm_pmm_gpu_mark_root_chunk_used` (`:3401`) only for a non-HMM VA block whose size is the root-chunk size (2 MB) and whose GPU is resident (`:3398-3402`; "HMM always allocates PAGE_SIZE GPU chunks so skip HMM va_blocks"). It is called
  - from `block_set_resident_processor` (`:3405-3413`, `:3412`) only on the *first* page becoming resident on that GPU (`uvm_processor_mask_test_and_set` returns early if already set, `:3409`);
  - **from `uvm_va_block_make_resident_finish` (`:4911`, call at `:4958`) on every call where the destination processor is resident**, with the comment "Update eviction heuristics ... this could repeat the call done in block_set_resident_processor(), but that doesn't do anything bad" (`:4950-4958`);
  - likewise from `uvm_va_block_make_resident_read_duplicate` (`:5046`, call at `:5212`).
  `uvm_va_block_make_resident_finish` is called by `uvm_va_block_make_resident` (`:4968`, call at `:4990`), by the HMM path (`uvm_hmm.c:3281`) and at `uvm_va_block.c:11941`. `uvm_va_block_make_resident` is the migration entry used by fault service, so every **migration of pages into the block's GPU chunk** (demand or prefetch) moves the chunk to the tail of USED.
- **Unused / discarded:** `block_clear_resident_processor` marks the root chunk UNUSED when the block's last page leaves the GPU (`:3415-3437`, call at `:3435`); `:8316`, `:12014`, `:12279-12281` mark chunks discarded or unused.
- **Not called** on a GPU access to a page that is already resident and mapped (no fault, no `make_resident`), and not on a mapping change alone: the source says so itself, `// TODO: Bug 1765193: Move the chunks to the tail of the used list whenever they get mapped.` (`uvm_pmm_gpu.c:1511-1512`).

## How `pick_root_chunk_to_evict` chooses its victim (`uvm_pmm_gpu.c:1487-1527`)
1. A free root chunk, non-zeroed first (`:1494-1499`), then zeroed (`:1501-1507`).
2. Otherwise `get_first_allocated_chunk` (`:1473-1485`, call at `:1511`): the head of the first non-empty list in the order UNUSED, DISCARDED, USED (enum order, `uvm_pmm_gpu.h:180-202`; `list_first_chunk` is `list_first_entry_or_null`, `:1147`). Items are appended at the tail, so the head is the entry whose last `list_move_tail` is oldest.
3. `chunk_start_eviction` (`:1514-1515`) removes it from the list and marks it in eviction.

## Verdict
**REFRESHED ON USE, where "use" means a migration (make_resident, including prefetch and read duplication) into the block's 2 MB GPU chunk, plus allocation; it is not refreshed by GPU accesses to data that is already resident, and HMM blocks and sub-2 MB blocks are not tracked at all.** The order is therefore "least recently migrated into", not "allocation order". UNUSED and DISCARDED chunks are always evicted before USED ones. (Section III-D's "allocation order, not by recency of access" is right only in the sense that plain access does not refresh; for a streaming sweep where every block is migrated once, last-migration order equals allocation order.)
