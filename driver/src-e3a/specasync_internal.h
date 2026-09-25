/* SPDX-License-Identifier: MIT */
/*
 * specasync_internal.h — cross-file declarations for SpecAsync-UVM v595 port
 *
 * Included by uvm.c (for workqueue lifecycle) and uvm_gpu_replayable_faults.c
 * (where g_specasync_wq and g_specasync_queue_depth are defined).
 */

#ifndef SPECASYNC_INTERNAL_H
#define SPECASYNC_INTERNAL_H

#include <linux/workqueue.h>
#include <linux/atomic.h>

/* Defined in uvm_gpu_replayable_faults.c */
extern struct workqueue_struct *g_specasync_wq;
extern atomic_t                 g_specasync_queue_depth;

/*
 * g_specasync_processed — total work items that reached specasync_worker_fn's
 * completion path (every policy/depth branch funnels through it: NULL policy,
 * depth>=1 migration done/throttled, depth=0 hit/miss). Added for Task A1
 * (AWS final work block) because specasync_worker_log is a fixed-size ring
 * (SPECASYNC_WORK_RING_SLOTS = 131072) that wraps many times over on a real
 * workload (Stencil-24K enqueues ~51M items/run) -- counting ring records
 * gives a recent window, not a total. This is a true kernel-side atomic, not
 * ring-derived. There is no distinguishable "dequeued but stale" path in the
 * worker: every dequeued item is unconditionally processed to some result
 * (NULL/HIT/MISS/MIGRATION_DONE/THROTTLED), so no separate stale counter was
 * added -- spec_enqueued - g_specasync_processed is the outstanding+dropped
 * remainder, not a distinct stale population.
 *
 * g_specasync_enqueued / g_specasync_drops mirror this reasoning on the
 * enqueue side: specasync_batch_record's per-batch spec_enqueues/spec_drops
 * fields live in the same fixed-size ring (SPECASYNC_BATCH_RING_SLOTS =
 * 131072) and would undercount a total the same way if the batch ring wraps
 * on a long run. These global atomics make the processed/enqueued ratio
 * robust to either ring wrapping, independent of ring window size.
 */
extern atomic_t                 g_specasync_processed;
extern atomic_t                 g_specasync_enqueued;
extern atomic_t                 g_specasync_drops;

/*
 * Gate B9: same rationale as above, for the three fields that previously
 * lived only in specasync_batch_record/specasync_work_record (both
 * 131,072-slot drop-on-full rings, confirmed to saturate within ~3-8% of a
 * real oversubscribed run's wall-clock). See uvm_gpu_replayable_faults.c's
 * definition-site comment for the exact increment locations.
 */
extern atomic_t                 g_specasync_demand_faults;
extern atomic_t                 g_specasync_spec_hits;
extern atomic_t                 g_specasync_spec_migrations;

/*
 * Gate E0.9a-2: demand faults on a page already resident on the FAULTING
 * GPU at the time the fault is serviced. Placed in the demand-fault path
 * (uvm_gpu_replayable_faults.c's per-fault service loop), immediately after
 * the existing uvm_va_block_page_is_gpu_authorized() check has already
 * determined the fault is NOT already satisfied by an existing mapping --
 * so a true increment here means: data is on this GPU, but the mapping the
 * demand fault needs does not exist yet. This is exactly the mechanism
 * H-map (GATE_E0_9A2_REPORT.md) predicts from source: the speculative
 * worker's uvm_va_block_make_resident() (uvm_gpu_replayable_faults.c,
 * specasync_worker_fn) never calls the mapping step
 * (block_service_finish_map(), only reachable via uvm_va_block_service_
 * finish() on the demand path) -- so a successful speculative migration can
 * make this counter's condition true, never prevent it from firing at all.
 */
extern atomic_t                 g_specasync_fault_already_resident;

/*
 * Gate E0.5 (Step 3): oracle-replay-consumption-side counters, defined
 * alongside g_oracle_idx/g_oracle_trace in specasync_debugfs.c.
 *
 * g_specasync_oracle_consumes -- total specasync_oracle_next_addr_n() calls
 * this run. Compared against g_specasync_trace_pushes (specasync_telemetry.h)
 * on a replay run to check the two per-coalesced-fault loops enumerate the
 * same fault set (see that header's comment).
 *
 * g_specasync_oracle_wraps -- number of times the replay cursor crossed the
 * end of the loaded trace and wrapped back to the start (computed from the
 * raw, un-modulo'd cumulative advance vs. trace length, so it counts real
 * wraps exactly, not an approximation).
 *
 * g_specasync_oracle_correct -- number of oracle_next_addr_n() calls whose
 * PREVIOUS call's predicted address matched the fault address actually
 * being serviced now (i.e. the oracle predicted this exact next fault).
 * g_specasync_oracle_predictions -- denominator for the above (calls where
 * a comparison was possible, i.e. not the very first call in the run).
 * g_specasync_oracle_correct_decile[10] / g_specasync_oracle_total_decile[10]
 * -- the same pair, bucketed by the predicted position's decile within the
 * loaded trace (0 = prediction targeted the first tenth of the trace, 9 =
 * the last tenth), for the accuracy-by-run-progress measurement.
 */
extern atomic_t                 g_specasync_oracle_consumes;
extern atomic_t                 g_specasync_oracle_wraps;
extern atomic_t                 g_specasync_oracle_correct;
extern atomic_t                 g_specasync_oracle_predictions;
extern atomic_t                 g_specasync_oracle_correct_decile[10];
extern atomic_t                 g_specasync_oracle_total_decile[10];

/* Forward declaration — struct is defined in uvm_gpu_replayable_faults.c */
struct specasync_predict_state;
struct specasync_predict_state *specasync_predict_state_alloc(void);
void specasync_predict_state_free(struct specasync_predict_state *ps);

/* Defined in specasync_debugfs.c */
int  specasync_debugfs_init(struct dentry *parent_dentry);
void specasync_debugfs_exit(void);
u64  specasync_oracle_next_addr(void);
/*
 * Gate B fix, Gate E0.5 accuracy instrumentation: cursor-sync oracle replay
 * -- advance by faults consumed this batch (always 1, called once per
 * coalesced fault since Gate 1 -- see call site), and score the PREVIOUS
 * prediction against the fault address being serviced now.
 */
u64  specasync_oracle_next_addr_n(u64 current_fault_addr, u32 consumed);

/*
 * Gate E0.9: first-touch oracle (policy 6). Accuracy-by-construction --
 * the table is built from the same run's own first-touch order, so there
 * is no cross-run alignment question at all; only timeliness (governed by
 * specasync_ft_lookahead, L) is free to vary. See GATE_E0_9_REPORT.md.
 *
 * fault_addr must already be page-aligned (true for every fault_address
 * reaching this call today -- verified from source, see
 * tests/prepare_first_touch_table.py's docstring). Returns the predicted
 * VA address, or 0 if nothing should be predicted for this fault (unknown
 * page, held back by lookahead, or table exhausted -- see the ft_* counters
 * in specasync_telemetry.h for which).
 */
u64  specasync_ft_predict(u64 fault_addr);
extern int specasync_ft_lookahead;

/*
 * Gate E3a: speculative width W (pages). One speculative worker call makes
 * the W-aligned region containing the predicted page resident, and policy 6
 * does not enqueue a prediction whose region equals the last ENQUEUED
 * prediction's region. W is validated at insmod (power of two in
 * [1, SPECASYNC_SPEC_WIDTH_MAX]); invalid values make insmod fail. W = 1
 * (default) takes exactly the pre-E3a code paths -- every new branch is
 * guarded by specasync_spec_width > 1.
 *
 * specasync_spec_width_shift            log2(W), set by the same param setter
 * g_specasync_last_regions[8]           region IDs (va >> (PAGE_SHIFT + shift))
 * g_specasync_last_region_idx           of the last 8 ENQUEUED policy-6
 *                                       predictions, round-robin insertion
 *                                       (E3a-2 B2: the single last region
 *                                       captured < 80% of an 8-region history
 *                                       on Stencil at W = 64).
 *                                       SPECASYNC_NO_REGION = empty slot.
 *                                       Plain u64/u32 globals, written/read
 *                                       only by the fault-servicing thread
 *                                       (READ_ONCE/WRITE_ONCE), reset by
 *                                       specasync_clear; no UVM state.
 * g_specasync_ft_same_region            predictions not enqueued: same region
 * g_specasync_spec_region_invalid       worker items skipped because the region
 *                                       failed an explicit bounds/block check
 * g_specasync_spec_pages_requested      sum of region sizes (pages) passed to
 *                                       uvm_va_block_make_resident by the worker
 */
#define SPECASYNC_SPEC_WIDTH_MAX  512
#define SPECASYNC_NO_REGION       (~0ULL)
#define SPECASYNC_REGION_HISTORY  8     /* must be a power of two (index is masked) */
extern int        specasync_spec_width;
extern int        specasync_spec_width_shift;
extern u64        g_specasync_last_regions[SPECASYNC_REGION_HISTORY];
extern u32        g_specasync_last_region_idx;
extern atomic_t   g_specasync_ft_same_region;
extern atomic_t   g_specasync_spec_region_invalid;
extern atomic64_t g_specasync_spec_pages_requested;

/*
 * Gate E3a-2: cheap first-touch oracle (specasync_ft_fast, 0444, 0|1,
 * default 0). At 1, specasync_load_ft_table() builds a range index over the
 * page-sorted table (maximal runs of consecutive pages: base pfn, length,
 * offset into a u32 rank array), then looks up EVERY table page with both
 * the range index and the existing bsearch; any single rank difference
 * logs the first mismatch with pr_err, frees the index, and leaves the
 * fast path disabled for this load. specasync_ft_predict() takes the fast
 * path only when that check passed; at 0 (or on failure) it takes exactly
 * the pre-E3a-2 path. The fast path takes no lock: the table and index are
 * read-only after load, and the cursor (g_ft_next_to_predict) is advanced
 * with a bounded atomic_try_cmpxchg loop that reproduces the slow path's
 * skip / predict / held / exhausted rule and counter updates exactly.
 */
extern int specasync_ft_fast;

#endif /* SPECASYNC_INTERNAL_H */
