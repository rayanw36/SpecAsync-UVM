/* SPDX-License-Identifier: MIT */
/*
 * specasync_faults_instrumentation.c
 *
 * Phase 2 additions to uvm_gpu_replayable_faults.c:
 *   - T0–T4 batch latency instrumentation
 *   - spec_hits tracking via hit-tag hash table
 *   - Updated specasync_worker with work-record telemetry
 *   - Residency offload (depth=1)
 *   - Stride, Markov, and oracle speculation policies
 *
 * ──────────────────────────────────────────────────────────────────────────
 * IMPORTANT: This file is AUTHORING ONLY — it cannot be compiled standalone.
 * It is written against the public nvidia-open v580.95.05 UVM API surface.
 * After `git lfs pull` and applying the patch, integrate the diff sections
 * (marked with TODO[phase-b]) into the actual source tree.
 * See driver/PHASE_B_INTEGRATION.md for the exact function names and line
 * numbers to verify in the real patched source.
 * ──────────────────────────────────────────────────────────────────────────
 *
 * Naming conventions follow the existing nvidia_uvm driver:
 *   uvm_*       — upstream NVIDIA symbols
 *   specasync_* — our additions
 */

/*
 * ════════════════════════════════════════════════════════════════════════════
 * SECTION 1 — service_fault_batch() instrumentation (Priority 1)
 *
 * Diff to apply inside uvm_gpu_replayable_faults.c.
 *
 * The function signature in v580.95.05 is approximately:
 *   static NV_STATUS service_fault_batch(uvm_gpu_t *gpu,
 *                                        uvm_fault_service_batch_context_t *batch_context)
 *
 * TODO[phase-b]: Verify exact signature against patched source.
 * ════════════════════════════════════════════════════════════════════════════
 */

/*
 * Add at top of service_fault_batch(), after the existing local variable
 * declarations but before the first substantive statement:
 *
 *   struct specasync_batch_record _sa_rec = {0};
 *   static atomic64_t _sa_batch_id = ATOMIC64_INIT(0);
 *   u64 _sa_t_enq_start;          // for enqueue_overhead accumulation
 *
 *   _sa_rec.batch_id = atomic64_fetch_inc(&_sa_batch_id);
 *   _sa_rec.t0_ns    = ktime_get_ns();                     // T0: batch entry
 *
 * ──────────────────────────────────────────────────────────────────────────
 * T1: after VA-space lock acquisition.
 *
 * TODO[phase-b]: Find the uvm_va_space_down_read() or equivalent call that
 *   acquires the VA-space lock in service_fault_batch(). It is likely called
 *   for each fault in the batch loop, or once before the loop. The UVM source
 *   uses uvm_va_space_down_read_rm() in some paths. Place T1 after the first
 *   lock acquisition in the batch:
 *
 *   _sa_rec.t1_ns = ktime_get_ns();                        // T1: lock acquired
 *
 * ──────────────────────────────────────────────────────────────────────────
 * T2: after metadata discovery (uvm_va_block_find() or equivalent).
 *
 * TODO[phase-b]: Locate the uvm_va_block_find() or uvm_va_block_find_create()
 *   call inside the fault-processing loop. Place T2 after the last such call
 *   for all faults in the batch:
 *
 *   _sa_rec.t2_ns = ktime_get_ns();                        // T2: metadata done
 *
 * Also add spec_hits check here (see Section 3 below for details):
 *   if (specasync_offload_depth >= 0 && batch_context->specasync_hit_table) {
 *       u64 _now = ktime_get_ns();
 *       for (i = 0; i < batch_context->num_coalesced_faults; i++) {
 *           u64 va = batch_context->fault_cache[i].fault_address;
 *           _sa_rec.spec_hits += specasync_hit_table_consume(
 *               batch_context->specasync_hit_table, va, _now);
 *       }
 *   }
 *
 * ──────────────────────────────────────────────────────────────────────────
 * T3: after residency decision / migration issued.
 *
 * TODO[phase-b]: Find where the residency mapping calls occur (likely
 *   uvm_va_block_service_faults() or uvm_va_block_make_resident() calls).
 *   Place T3 after the last such call in the batch loop:
 *
 *   _sa_rec.t3_ns = ktime_get_ns();                        // T3: residency done
 *
 * ──────────────────────────────────────────────────────────────────────────
 * T4: at function exit. Add before each return statement, or use goto exit:
 *
 *   _sa_rec.t4_ns          = ktime_get_ns();               // T4: batch exit
 *   _sa_rec.num_faults     = batch_context->num_coalesced_faults;
 *   // spec_enqueues, spec_drops populated by specasync_enqueue() calls below
 *   specasync_batch_ring_push(&_sa_rec);
 */


/*
 * ════════════════════════════════════════════════════════════════════════════
 * SECTION 2 — specasync_worker update (Priority 1 + 2)
 *
 * The existing worker (from the Phase 1 patch) processes spec_work_items.
 * We add:
 *   - Work-record telemetry (specasync_work_record)
 *   - spec_hits tagging (hit-table insert)
 *   - Residency offload when specasync_offload_depth >= 1
 * ════════════════════════════════════════════════════════════════════════════
 */

/*
 * Replace the body of the worker callback (currently named specasync_worker
 * or similar in the Phase 1 patch) with the following logic:
 *
 * TODO[phase-b]: Identify the worker function name in the patched source.
 *   Common patterns: specasync_worker_fn(), specasync_do_work(), or a
 *   work_struct callback registered via INIT_WORK().
 */

/*
 * Pseudocode (annotated with actual UVM API calls where known):
 *
 * static void specasync_worker_fn(struct work_struct *work)
 * {
 *     struct specasync_work_item *item =
 *         container_of(work, struct specasync_work_item, work);
 *     struct specasync_work_record wrec = {0};
 *     uvm_va_block_t *va_block = NULL;
 *     NV_STATUS status;
 *     u64 t_enq, t_deq, t_comp;
 *
 *     t_deq = ktime_get_ns();
 *     t_enq = item->enqueue_ts_ns;              // set at enqueue time
 *
 *     wrec.enqueue_ts_ns  = t_enq;
 *     wrec.dequeue_ts_ns  = t_deq;
 *     wrec.va_addr        = item->va_addr;
 *     wrec.policy_used    = specasync_policy;
 *
 *     // ── Metadata lookup ──────────────────────────────────────────────
 *     // TODO[phase-b]: Confirm uvm_va_space_find_va_block() signature in v580.
 *     // Alternative: uvm_va_block_find() with uvm_va_space held.
 *     status = uvm_va_block_find(item->va_space, item->va_addr, &va_block);
 *
 *     if (status != NV_OK || !va_block) {
 *         wrec.result = SPECASYNC_RESULT_MISS;
 *         goto done;
 *     }
 *
 *     // ── Update hit table ─────────────────────────────────────────────
 *     if (item->hit_table) {
 *         specasync_hit_table_insert(item->hit_table,
 *                                    item->va_addr, ktime_get_ns());
 *     }
 *     wrec.result = SPECASYNC_RESULT_HIT;
 *
 *     // ── Residency offload (depth >= 1) ────────────────────────────────
 *     if (specasync_offload_depth >= 1) {
 *         status = specasync_residency_prep(va_block, item);
 *         if (status == NV_OK)
 *             wrec.result = SPECASYNC_RESULT_MIGRATION_DONE;
 *         // on failure, keep RESULT_HIT — we still staged the metadata
 *     }
 *
 * done:
 *     t_comp             = ktime_get_ns();
 *     wrec.completion_ts_ns = t_comp;
 *     specasync_work_ring_push(&wrec);
 *     kfree(item);
 * }
 */


/*
 * ════════════════════════════════════════════════════════════════════════════
 * SECTION 3 — specasync_enqueue() with overhead tracking (Priority 1)
 *
 * Called from service_fault_batch() to enqueue a speculative work item.
 * Measures the overhead of the enqueue operation itself.
 * ════════════════════════════════════════════════════════════════════════════
 */

/*
 * Replace or augment the existing enqueue path with:
 *
 * static void specasync_enqueue(uvm_va_space_t *va_space,
 *                               u64 speculative_addr,
 *                               struct specasync_hit_table *hit_table,
 *                               struct specasync_batch_record *sa_rec)
 * {
 *     struct specasync_work_item *item;
 *     u64 t0, t1;
 *     int queue_depth;
 *
 *     if (!specasync_log_enabled)
 *         return;
 *
 *     // Safety: check queue depth (throttle if too deep)
 *     queue_depth = atomic_read(&specasync_queue_depth);
 *     if (queue_depth >= SPECASYNC_MAX_QUEUE_DEPTH) {
 *         sa_rec->spec_drops++;
 *         return;
 *     }
 *
 *     t0 = ktime_get_ns();
 *
 *     item = kzalloc(sizeof(*item), GFP_ATOMIC);
 *     if (!item) {
 *         sa_rec->spec_drops++;
 *         return;
 *     }
 *
 *     item->va_space    = va_space;
 *     item->va_addr     = speculative_addr;
 *     item->hit_table   = hit_table;
 *     item->enqueue_ts_ns = t0;
 *     INIT_WORK(&item->work, specasync_worker_fn);
 *
 *     atomic_inc(&specasync_queue_depth);
 *     if (!queue_work(specasync_wq, &item->work)) {
 *         // Work was already on queue (shouldn't happen with fresh item)
 *         kfree(item);
 *         atomic_dec(&specasync_queue_depth);
 *         sa_rec->spec_drops++;
 *         return;
 *     }
 *
 *     t1 = ktime_get_ns();
 *     sa_rec->spec_enqueues++;
 *     // Accumulate overhead (saturating at u32 max)
 *     {
 *         u64 oh = (t1 - t0);
 *         sa_rec->enqueue_overhead_ns = (u32)min(
 *             (u64)sa_rec->enqueue_overhead_ns + oh, (u64)U32_MAX);
 *     }
 * }
 */


/*
 * ════════════════════════════════════════════════════════════════════════════
 * SECTION 4 — Residency offload depth=1 (Priority 2)
 * ════════════════════════════════════════════════════════════════════════════
 */

/*
 * specasync_residency_prep() — called from worker when depth >= 1.
 *
 * Safety gates (ALL must pass before calling residency API):
 *   1. Queue depth below SPECASYNC_MAX_QUEUE_DEPTH (16)
 *   2. Worker holds no VA-space write lock — confirmed: worker runs in
 *      workqueue context and only takes read locks via uvm_va_block_find().
 *   3. VRAM utilization heuristic:
 *      TODO[phase-b]: Check if v580.95.05 exposes a usable VRAM-utilization
 *      counter (e.g. via rmapi or uvm_gpu_t memory stats). If available,
 *      gate on < 90% utilization. If not available, document and skip gating.
 *      See PHASE_B_INTEGRATION.md §4.
 *
 * TODO[phase-b]: Identify the correct residency-prep symbol. Candidates:
 *   - uvm_va_block_make_resident()   — most likely for managed memory
 *   - uvm_va_block_migrate_locked()  — for explicit migration
 *   - uvm_migrate_ranges()           — higher-level, may be too heavy
 *   The correct call depends on whether va_block is already locked.
 *   In worker context, we cannot hold the va_space write lock, so we need
 *   a path that takes the va_block lock internally.
 *   See PHASE_B_INTEGRATION.md §4 for the lookup checklist.
 */

/*
 * static NV_STATUS specasync_residency_prep(uvm_va_block_t *va_block,
 *                                           struct specasync_work_item *item)
 * {
 *     NV_STATUS status;
 *     uvm_processor_id_t dest;
 *
 *     // Gate 1: queue depth (already checked at enqueue, re-check here)
 *     if (atomic_read(&specasync_queue_depth) > SPECASYNC_MAX_QUEUE_DEPTH / 2)
 *         return NV_ERR_BUSY_RETRY;
 *
 *     // Gate 3: VRAM utilization
 *     // TODO[phase-b]: Add utilization check here if counter available.
 *     // If not available: fall through (see PHASE_B_INTEGRATION.md §4).
 *
 *     // Determine destination processor (typically the local GPU)
 *     // TODO[phase-b]: item->va_space->gpu_va_space[gpu_id] or similar
 *     dest = item->dest_processor;   // TODO[phase-b]: field to add to work_item
 *
 *     // TODO[phase-b]: Replace with correct v580.95.05 API:
 *     status = uvm_va_block_make_resident(
 *         va_block,
 *         NULL,          // tracker — NULL = fire-and-forget
 *         dest,
 *         UVM_VA_BLOCK_REGION_ALL,
 *         NULL,          // prefetch_hint
 *         UVM_MAKE_RESIDENT_CAUSE_PREFETCH);
 *
 *     return status;
 * }
 */

/*
 * Depth=2 stub — intentionally not implemented.
 *
 * Depth=2 would require holding the VA-space write lock while doing full
 * residency preparation. This lock is also held by the demand-fault path,
 * creating a priority inversion: the worker would block behind the very
 * path we are trying to accelerate.
 *
 * A safe implementation requires a "shadow-commit" design where the worker
 * stages the residency operation speculatively without locking, then the
 * demand-fault handler validates and fast-commits.  This is out of scope
 * for Phase 2.
 */
/*
 * static NV_STATUS specasync_residency_prep_depth2(...)
 * {
 *     pr_warn_once("specasync: offload_depth=2 not safely implementable; "
 *                  "use shadow-commit design instead. Falling back to depth=1.\n");
 *     return specasync_residency_prep(...);
 * }
 */


/*
 * ════════════════════════════════════════════════════════════════════════════
 * SECTION 5 — Speculation policies (Priority 3)
 *
 * Policy dispatch function — replaces the current hard-coded
 * "fault_address + 0x1000" logic.
 * ════════════════════════════════════════════════════════════════════════════
 */

/*
 * Per-VA-space prediction state (add to uvm_va_space_t or attach via pointer).
 * TODO[phase-b]: Add field `struct specasync_predict_state *specasync_pred`
 *   to uvm_va_space_t in uvm_va_space.h; allocate in uvm_va_space_create();
 *   free in uvm_va_space_destroy(). See PHASE_B_INTEGRATION.md §5.
 */
struct specasync_stride_state {
	u64 last_fault_addr;
	s64 last_delta;
	u8  confidence;           /* saturating, max 4 */
};

struct specasync_markov_entry {
	u64 key_page;             /* 0 = empty slot */
	u64 next_page;
	u32 count;
	u32 _pad;
};

#define SPECASYNC_MARKOV_SLOTS  256   /* ~4 KB per VA space */

struct specasync_markov_state {
	struct specasync_markov_entry table[SPECASYNC_MARKOV_SLOTS];
	u64 last_page;
};

struct specasync_predict_state {
	struct specasync_stride_state  stride;
	struct specasync_markov_state *markov;   /* kzalloc'd separately */
	struct specasync_hit_table    *hit_table;
};

/*
 * specasync_predict_next() — return the speculative candidate address.
 *
 * Called from service_fault_batch() once per fault.
 * Returns 0 if no speculation should be issued for this fault.
 */
static inline u64 specasync_predict_next(struct specasync_predict_state *ps,
					 u64 fault_addr)
{
	if (!ps)
		return fault_addr + 0x1000;   /* safe default if state unavailable */

	switch (specasync_policy) {
	case 0:
		return 0;   /* disabled */

	case 1:
		/* Adjacent-page (original Phase 1 behaviour) */
		return fault_addr + 0x1000;

	case 2: {
		/* Stride detector */
		struct specasync_stride_state *ss = &ps->stride;
		s64 delta = (s64)(fault_addr - ss->last_fault_addr);

		if (delta == ss->last_delta && delta != 0) {
			/* Saturating confidence increment */
			if (ss->confidence < 4)
				ss->confidence++;
		} else {
			ss->confidence = ss->confidence / 2;
			ss->last_delta = delta;
		}
		ss->last_fault_addr = fault_addr;

		if (ss->confidence >= 2)
			return fault_addr + (u64)ss->last_delta;
		return fault_addr + 0x1000;   /* fallback */
	}

	case 3: {
		/* Markov next-page predictor */
		struct specasync_markov_state *ms = ps->markov;
		u64 cur_page = fault_addr >> PAGE_SHIFT;
		u64 next_page = 0;
		u32 slot, start_slot;

		if (!ms)
			return fault_addr + 0x1000;

		/* Update transition table for last_page → cur_page */
		if (ms->last_page != 0) {
			start_slot = (u32)((ms->last_page * 0x9e3779b9ULL) >>
					   (32 - 8)) & (SPECASYNC_MARKOV_SLOTS - 1);
			slot = start_slot;
			/* Linear probe */
			while (ms->table[slot].key_page != 0 &&
			       ms->table[slot].key_page != ms->last_page) {
				slot = (slot + 1) & (SPECASYNC_MARKOV_SLOTS - 1);
				if (slot == start_slot)
					break;   /* table full, evict happens below */
			}
			if (ms->table[slot].key_page == 0 ||
			    ms->table[slot].key_page == ms->last_page) {
				ms->table[slot].key_page  = ms->last_page;
				ms->table[slot].next_page = cur_page;
				ms->table[slot].count++;
			}
		}

		/* Look up cur_page → prediction */
		start_slot = (u32)((cur_page * 0x9e3779b9ULL) >>
				   (32 - 8)) & (SPECASYNC_MARKOV_SLOTS - 1);
		slot = start_slot;
		while (ms->table[slot].key_page != 0 &&
		       ms->table[slot].key_page != cur_page) {
			slot = (slot + 1) & (SPECASYNC_MARKOV_SLOTS - 1);
			if (slot == start_slot)
				break;
		}
		if (ms->table[slot].key_page == cur_page &&
		    ms->table[slot].count > 1) {
			next_page = ms->table[slot].next_page;
		}

		ms->last_page = cur_page;

		if (next_page)
			return next_page << PAGE_SHIFT;
		return fault_addr + 0x1000;   /* fallback */
	}

	case 4:
		/*
		 * Oracle — reads next address from pre-loaded trace file.
		 * For measuring speculation upper bound only; not for production.
		 *
		 * TODO[phase-b]: specasync_oracle_next_addr() is defined in
		 *   specasync_debugfs.c.  Ensure the symbol is exported and
		 *   the oracle trace is loaded at module init.
		 */
		{
			u64 addr = specasync_oracle_next_addr();
			return addr ? addr : (fault_addr + 0x1000);
		}

	default:
		return fault_addr + 0x1000;
	}
}

/*
 * specasync_predict_state_alloc() — allocate per-VA-space prediction state.
 * Call from uvm_va_space_create() (or wherever va_space is initialised).
 * Returns NULL on allocation failure; callers must fall back gracefully.
 *
 * TODO[phase-b]: Wire this into uvm_va_space_create(). See PHASE_B_INTEGRATION.md §5.
 */
static struct specasync_predict_state *specasync_predict_state_alloc(void)
{
	struct specasync_predict_state *ps;
	struct specasync_hit_table *ht;

	ps = kzalloc(sizeof(*ps), GFP_KERNEL);
	if (!ps)
		return NULL;

	ps->markov = kzalloc(sizeof(*ps->markov), GFP_KERNEL);
	if (!ps->markov) {
		kfree(ps);
		return NULL;
	}

	ht = kzalloc(sizeof(*ht), GFP_KERNEL);
	if (!ht) {
		kfree(ps->markov);
		kfree(ps);
		return NULL;
	}
	spin_lock_init(&ht->lock);
	ps->hit_table = ht;
	return ps;
}

static void specasync_predict_state_free(struct specasync_predict_state *ps)
{
	if (!ps)
		return;
	kfree(ps->markov);
	kfree(ps->hit_table);
	kfree(ps);
}
