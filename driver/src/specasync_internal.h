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

/* Forward declaration — struct is defined in uvm_gpu_replayable_faults.c */
struct specasync_predict_state;
struct specasync_predict_state *specasync_predict_state_alloc(void);
void specasync_predict_state_free(struct specasync_predict_state *ps);

/* Defined in specasync_debugfs.c */
int  specasync_debugfs_init(struct dentry *parent_dentry);
void specasync_debugfs_exit(void);
u64  specasync_oracle_next_addr(void);
/* Gate B: cursor-sync oracle replay — advance by faults consumed this batch. */
u64  specasync_oracle_next_addr_n(u32 consumed);

#endif /* SPECASYNC_INTERNAL_H */
