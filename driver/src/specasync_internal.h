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
