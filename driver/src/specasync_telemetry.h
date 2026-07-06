/* SPDX-License-Identifier: MIT */
/*
 * specasync_telemetry.h — SpecAsync-UVM Phase 2 telemetry structs + ring buffers
 *
 * Drop-in header for uvm_gpu_replayable_faults.c and specasync_debugfs.c.
 * All structs are hand-padded to natural alignment so the Python parser can
 * read them with struct.unpack('<6Q6I') and struct.unpack('<4Q4I') directly.
 *
 * TODO[phase-b]: After `git lfs pull` and applying the patch, verify that
 *   including this header from uvm_gpu_replayable_faults.c compiles cleanly
 *   in the nvidia-open kernel module build tree (Kbuild flags, include paths).
 */

/*
 * SPECASYNC_DECOMP — Phase C dispatch-window decomposition instrumentation.
 * Set to 0 to compile out all decomp timestamps for overhead measurement (Gate G3).
 * Default 1 (enabled).  Override via ccflags-y += -DSPECASYNC_DECOMP=0 in Kbuild.
 */
#ifndef SPECASYNC_DECOMP
#define SPECASYNC_DECOMP 1
#endif

#ifndef SPECASYNC_TELEMETRY_H
#define SPECASYNC_TELEMETRY_H

#include <linux/types.h>
#include <linux/spinlock.h>
#include <linux/atomic.h>

/* ── Per-batch latency record (72 bytes, fmt '<6Q6I') ──────────────────────
 *
 * Byte layout (no implicit padding — verified by BUILD_BUG_ON below):
 *   0    u64  batch_id
 *   8    u64  t0_ns            batch entry (after fault-buffer drain)
 *  16    u64  t1_ns            after VA-space lock acquired
 *  24    u64  t2_ns            after metadata discovery for all faults
 *  32    u64  t3_ns            after residency decision / migration issued
 *  40    u64  t4_ns            batch exit (before return)
 *  48    u32  num_faults
 *  52    u32  spec_enqueues
 *  56    u32  spec_drops
 *  60    u32  spec_hits
 *  64    u32  enqueue_overhead_ns
 *  68    u32  _pad             explicit padding for userspace alignment
 */
struct specasync_batch_record {
	u64 batch_id;
	u64 t0_ns;
	u64 t1_ns;
	u64 t2_ns;
	u64 t3_ns;
	u64 t4_ns;
	u32 num_faults;
	u32 spec_enqueues;
	u32 spec_drops;
	u32 spec_hits;
	u32 enqueue_overhead_ns;
	u32 _pad;
};

/* ── Per-work-item record (48 bytes, fmt '<4Q4I') ──────────────────────────
 *
 * Byte layout:
 *   0    u64  enqueue_ts_ns
 *   8    u64  dequeue_ts_ns
 *  16    u64  completion_ts_ns
 *  24    u64  va_addr
 *  32    u32  result    (0=null 1=miss 2=hit 3=migration_done 4=throttled)
 *  36    u32  policy_used
 *  40    u32  _pad[0]
 *  44    u32  _pad[1]
 */
struct specasync_work_record {
	u64 enqueue_ts_ns;
	u64 dequeue_ts_ns;
	u64 completion_ts_ns;
	u64 va_addr;
	u32 result;
	u32 policy_used;
	u32 _pad[2];
};

#define SPECASYNC_RESULT_NULL           0
#define SPECASYNC_RESULT_MISS           1
#define SPECASYNC_RESULT_HIT            2
#define SPECASYNC_RESULT_MIGRATION_DONE 3
#define SPECASYNC_RESULT_THROTTLED      4

/* Speculation policy values for the specasync_policy module param. */
#define SPECASYNC_POLICY_DISABLED 0
#define SPECASYNC_POLICY_ADJACENT 1
#define SPECASYNC_POLICY_STRIDE   2
#define SPECASYNC_POLICY_MARKOV   3
#define SPECASYNC_POLICY_ORACLE   4
#define SPECASYNC_POLICY_NULL     5   /* Gate C: worker wakes/dequeues, no lookup */

/* ── Phase C dispatch-window decomposition record (112 bytes, '<12Q4I') ─────
 *
 * One record per top-level batch iteration in
 * uvm_parent_gpu_service_replayable_faults().  Sub-phases:
 *
 *   D1 = d1_end   - d1_start    fault-buffer drain (fetch_fault_buffer_entries)
 *   D2 = d2_end   - d2_start    preprocessing / sort / dedup (preprocess_fault_batch)
 *   D3 = d3_wait_ns (cumul)     VA-space lock WAIT (retain_lock + down_read)
 *   D4 = d4_hold_ns (cumul)     VA-space lock HOLD (down_read → up_read), includes D5
 *   D5 = d5_serv_ns (cumul)     service_fault_batch_dispatch() CPU time inside hold
 *   D6 = d6_end   - d6_start    replay push (0 if no explicit top-level replay)
 *   svc = svc_end - svc_start   full service_fault_batch() call (D3+D4+overhead)
 *
 * Accounting closure (Gate G1): D1+D2+svc+D6+D7 = total window,
 *   where D7 = (svc_start - d2_end) + (d6_start - svc_end) + other residual.
 *   D3+D4 must be ≤ svc, and D5 ≤ D4, per batch.
 *
 * Byte layout (verified by static_assert in uvm_gpu_replayable_faults.c):
 *    0   u64  batch_id
 *    8   u64  d1_start
 *   16   u64  d1_end
 *   24   u64  d2_start
 *   32   u64  d2_end
 *   40   u64  svc_start
 *   48   u64  svc_end
 *   56   u64  d6_start    (0 if no top-level replay this iteration)
 *   64   u64  d6_end      (0 if no top-level replay this iteration)
 *   72   u64  d3_wait_ns  accumulated lock-wait time across all va_space acquisitions
 *   80   u64  d4_hold_ns  accumulated lock-hold time (includes D5)
 *   88   u64  d5_serv_ns  accumulated dispatch time inside hold
 *   96   u32  num_faults
 *  100   u32  num_va_spaces   distinct va_space lock acquisitions
 *  104   u32  num_blocks      calls to service_fault_batch_dispatch
 *  108   u32  _pad
 */
struct specasync_decomp_record {
	u64 batch_id;
	u64 d1_start;
	u64 d1_end;
	u64 d2_start;
	u64 d2_end;
	u64 svc_start;
	u64 svc_end;
	u64 d6_start;
	u64 d6_end;
	u64 d3_wait_ns;
	u64 d4_hold_ns;
	u64 d5_serv_ns;
	u32 num_faults;
	u32 num_va_spaces;
	u32 num_blocks;
	u32 _pad;
};

#define SPECASYNC_DECOMP_RING_SLOTS  (1U << 17)   /* 131072 × 112 B ≈ 14.7 MB */

struct specasync_decomp_ring {
	struct specasync_decomp_record *buf;
	u32                             head;
	u32                             tail;
	u32                             mask;
	u32                             drops;
	spinlock_t                      lock;
};

/* ── Ring buffer (single-producer / single-consumer via spinlock fallback) ─
 *
 * Sized for 100k records each.  Lock-free SPSC would be cleaner but the
 * consumer (debugfs read) and producer (interrupt context) have different
 * scheduling constraints; a spinlock is the safe default.
 *
 * TODO[phase-b]: If profiling shows the spinlock is a bottleneck on the
 *   fault hot path, replace with a proper SPSC ring (kfifo or hand-rolled).
 *   The struct layout must not change — the ring is write-only from the
 *   kernel side; userspace reads the whole buffer in one shot.
 */
#define SPECASYNC_BATCH_RING_SLOTS   (1U << 17)   /* 131072 × 72 B  ≈  9.4 MB */
#define SPECASYNC_WORK_RING_SLOTS    (1U << 17)   /* 131072 × 48 B  ≈  6.3 MB */

struct specasync_batch_ring {
	struct specasync_batch_record *buf;   /* kvmalloc'd at init */
	u32                           head;   /* producer write cursor */
	u32                           tail;   /* consumer read cursor */
	u32                           mask;   /* RING_SLOTS - 1 */
	u32                           drops;  /* slots dropped when full */
	spinlock_t                    lock;
};

struct specasync_work_ring {
	struct specasync_work_record  *buf;
	u32                            head;
	u32                            tail;
	u32                            mask;
	u32                            drops;
	spinlock_t                     lock;
};

/* ── Module parameter declarations (defined in uvm_gpu_replayable_faults.c) ─ */
extern int specasync_log_enabled;
extern int specasync_policy;
extern int specasync_offload_depth;
extern char *specasync_oracle_trace_path;

/* ── Global ring buffer instances (defined in specasync_debugfs.c) ─────────── */
extern struct specasync_batch_ring  g_batch_ring;
extern struct specasync_work_ring   g_work_ring;
extern struct specasync_decomp_ring g_decomp_ring;

/* ── Ring buffer API ────────────────────────────────────────────────────────── */

/*
 * specasync_batch_ring_push() — called from service_fault_batch(), IRQ context.
 * Drops silently if ring is full (increments drops counter).
 */
static inline void specasync_batch_ring_push(const struct specasync_batch_record *rec)
{
	struct specasync_batch_ring *r = &g_batch_ring;
	unsigned long flags;

	if (!specasync_log_enabled || !r->buf)
		return;

	spin_lock_irqsave(&r->lock, flags);
	if (((r->head - r->tail) & r->mask) == r->mask) {
		r->drops++;
	} else {
		r->buf[r->head & r->mask] = *rec;
		/* Ensure record is visible before advancing head */
		smp_wmb();
		r->head++;
	}
	spin_unlock_irqrestore(&r->lock, flags);
}

static inline void specasync_work_ring_push(const struct specasync_work_record *rec)
{
	struct specasync_work_ring *r = &g_work_ring;
	unsigned long flags;

	if (!specasync_log_enabled || !r->buf)
		return;

	spin_lock_irqsave(&r->lock, flags);
	if (((r->head - r->tail) & r->mask) == r->mask) {
		r->drops++;
	} else {
		r->buf[r->head & r->mask] = *rec;
		smp_wmb();
		r->head++;
	}
	spin_unlock_irqrestore(&r->lock, flags);
}

/* Phase C decomp ring push — noinline forces a real call, keeping _dec stack slots stable */
static noinline void specasync_decomp_ring_push(const struct specasync_decomp_record *rec)
{
	struct specasync_decomp_ring *r = &g_decomp_ring;
	unsigned long flags;

	if (!specasync_log_enabled || !r->buf)
		return;

	spin_lock_irqsave(&r->lock, flags);
	if (((r->head - r->tail) & r->mask) == r->mask) {
		r->drops++;
	} else {
		u32 slot_idx = r->head & r->mask;
		struct specasync_decomp_record *dst = &r->buf[slot_idx];
		*dst = *rec;
		smp_wmb();
		r->head++;
	}
	spin_unlock_irqrestore(&r->lock, flags);
}

/* ── Hit-tag hash table (for spec_hits tracking) ────────────────────────────
 *
 * Small open-addressed table: key = VA page number, value = (ts_ns, va_addr).
 * Stored per uvm_va_space; lifetime matches the va_space.
 *
 * TODO[phase-b]: This struct is embedded in uvm_va_space (or attached to it).
 *   After lfs pull, find uvm_va_space_t in uvm_va_space.h and add a field:
 *     struct specasync_hit_table *specasync_hits;
 *   Initialise in uvm_va_space_create(), free in uvm_va_space_destroy().
 */
#define SPECASYNC_HIT_TABLE_SLOTS  256   /* power-of-2 for mask trick */

struct specasync_hit_entry {
	u64 va_addr;      /* 0 = empty slot */
	u64 ts_ns;        /* ktime_get_ns() when worker completed lookup */
};

struct specasync_hit_table {
	struct specasync_hit_entry slots[SPECASYNC_HIT_TABLE_SLOTS];
	spinlock_t                  lock;
};

#define SPECASYNC_HIT_MAX_AGE_NS  (10ULL * 1000 * 1000)   /* 10 ms */

static inline u32 _hit_hash(u64 va_addr)
{
	/* Page-number hash, low bits zero from PAGE_SHIFT alignment */
	u64 page = va_addr >> 12;
	/* Fibonacci hashing — spreads page numbers well */
	return (u32)((page * 0x9e3779b97f4a7c15ULL) >> (64 - 8));
}

/* Insert or update a hit-table entry for va_addr. Called by the worker. */
static inline void specasync_hit_table_insert(struct specasync_hit_table *ht,
					      u64 va_addr, u64 ts_ns)
{
	u32 idx;
	unsigned long flags;

	spin_lock_irqsave(&ht->lock, flags);
	idx = _hit_hash(va_addr) & (SPECASYNC_HIT_TABLE_SLOTS - 1);
	/* Linear probe — tolerate a single collision; table is tiny */
	if (ht->slots[idx].va_addr != 0 && ht->slots[idx].va_addr != va_addr)
		idx = (idx + 1) & (SPECASYNC_HIT_TABLE_SLOTS - 1);
	ht->slots[idx].va_addr = va_addr;
	ht->slots[idx].ts_ns   = ts_ns;
	spin_unlock_irqrestore(&ht->lock, flags);
}

/*
 * specasync_hit_table_consume() — called on demand-fault metadata discovery.
 * Returns 1 if va_addr was pre-located by the worker within max-age window,
 * clears the entry, and increments spec_hits via the out-param.
 */
static inline int specasync_hit_table_consume(struct specasync_hit_table *ht,
					      u64 va_addr, u64 now_ns)
{
	u32 idx, orig_idx;
	int found = 0;
	unsigned long flags;

	spin_lock_irqsave(&ht->lock, flags);
	orig_idx = _hit_hash(va_addr) & (SPECASYNC_HIT_TABLE_SLOTS - 1);
	idx = orig_idx;

	/* Check primary and one-step probe */
	if (ht->slots[idx].va_addr == va_addr) {
		found = 1;
	} else {
		idx = (idx + 1) & (SPECASYNC_HIT_TABLE_SLOTS - 1);
		if (ht->slots[idx].va_addr == va_addr)
			found = 1;
	}

	if (found) {
		u64 age = now_ns - ht->slots[idx].ts_ns;
		if (age <= SPECASYNC_HIT_MAX_AGE_NS) {
			ht->slots[idx].va_addr = 0;  /* clear entry */
		} else {
			found = 0;  /* stale — do not count as hit */
			ht->slots[idx].va_addr = 0;  /* evict stale entry */
		}
	}
	spin_unlock_irqrestore(&ht->lock, flags);
	return found;
}

/* ── Demand-fault address trace ring (for oracle policy) ───────────────────
 *
 * Captures demand-fault addresses in service order for oracle trace files.
 * Enable with module param specasync_trace_faults=1.
 * 1M slots × 8 B = 8 MB; ring wraps (old data overwritten).
 */
#define SPECASYNC_TRACE_RING_SLOTS  (1U << 20)

struct specasync_trace_ring {
	u64        *buf;   /* kvmalloc'd at init */
	u32         head;
	u32         mask;
	spinlock_t  lock;
};

extern struct specasync_trace_ring g_trace_ring;
extern int specasync_trace_faults;

static inline void specasync_trace_push(u64 va_addr)
{
	struct specasync_trace_ring *r = &g_trace_ring;
	unsigned long flags;

	if (!specasync_trace_faults || !r->buf)
		return;
	spin_lock_irqsave(&r->lock, flags);
	r->buf[r->head & r->mask] = va_addr;
	r->head++;
	spin_unlock_irqrestore(&r->lock, flags);
}

#endif /* SPECASYNC_TELEMETRY_H */
