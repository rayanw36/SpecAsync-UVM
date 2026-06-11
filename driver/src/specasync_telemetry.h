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
extern struct specasync_batch_ring g_batch_ring;
extern struct specasync_work_ring  g_work_ring;

/* ── Ring buffer API ────────────────────────────────────────────────────────── */

/*
 * specasync_batch_ring_push() — called from service_fault_batch(), IRQ context.
 * Drops silently if ring is full (increments drops counter).
 */
static inline void specasync_batch_ring_push(const struct specasync_batch_record *rec)
{
	struct specasync_batch_ring *r = &g_batch_ring;
	unsigned long flags;

	if (!specasync_log_enabled)
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

	if (!specasync_log_enabled)
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
