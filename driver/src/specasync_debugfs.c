/* SPDX-License-Identifier: MIT */
/*
 * specasync_debugfs.c — debugfs interface for SpecAsync-UVM Phase 2 telemetry
 *
 * Exposes three files under /sys/kernel/debug/nvidia_uvm/:
 *   specasync_log         binary stream of specasync_batch_record (72 B each)
 *   specasync_worker_log  binary stream of specasync_work_record   (48 B each)
 *   specasync_clear       write any byte to reset both ring buffers
 *
 * Call specasync_debugfs_init() from the existing nvidia_uvm debugfs init
 * hook (after the parent dentry is created). Call specasync_debugfs_exit()
 * from module exit, before ring-buffer memory is freed.
 *
 * TODO[phase-b]: After `git lfs pull`, find the nvidia_uvm debugfs init/exit
 *   hooks. They are likely in uvm_debug.c or uvm_procfs.c.  Add:
 *     ret = specasync_debugfs_init(uvm_debugfs_dir());
 *   in the init path, and:
 *     specasync_debugfs_exit();
 *   in the exit path. See PHASE_B_INTEGRATION.md §1 for exact function names.
 */

#include <linux/debugfs.h>
#include <linux/module.h>
#include <linux/slab.h>
#include <linux/uaccess.h>
#include <linux/vmalloc.h>
#include <linux/log2.h>
#include "specasync_telemetry.h"
#include "specasync_internal.h"

/* ── Global ring buffer instances ────────────────────────────────────────── */

struct specasync_batch_ring  g_batch_ring;
struct specasync_work_ring   g_work_ring;
struct specasync_trace_ring  g_trace_ring;
struct specasync_decomp_ring g_decomp_ring;

/* Module parameters — defined here, declared extern in specasync_telemetry.h */
int   specasync_log_enabled       = 1;
int   specasync_policy            = 1;   /* 1 = adjacent-page */
int   specasync_offload_depth     = 0;   /* 0 = metadata-only */
int   specasync_trace_faults      = 0;   /* 0 = disabled; 1 = record demand-fault addrs */
char *specasync_oracle_trace_path = NULL;
/*
 * Gate E0.5 (Step 3): trace-ring capacity as a module parameter. Rounded up
 * to a power of two at allocation time (alloc_trace_ring()) because the
 * push path indexes with `head & mask`. 0444: read-only after load, since
 * the ring is allocated once in specasync_debugfs_init() and never resized.
 * Default unchanged from the prior compile-time constant
 * (SPECASYNC_TRACE_RING_SLOTS_DEFAULT, 1<<20) -- every existing
 * non-oversubscribed collection stays under this, so nothing that already
 * worked changes behavior.
 */
int   specasync_trace_ring_slots  = SPECASYNC_TRACE_RING_SLOTS_DEFAULT;

module_param(specasync_log_enabled,       int,  0644);
module_param(specasync_policy,            int,  0644);
module_param(specasync_offload_depth,     int,  0644);
module_param(specasync_trace_faults,      int,  0644);
module_param(specasync_oracle_trace_path, charp, 0444);
module_param(specasync_trace_ring_slots,  int,  0444);

MODULE_PARM_DESC(specasync_log_enabled,
	"Enable telemetry ring buffers (1=enabled [default], 0=disabled)");
MODULE_PARM_DESC(specasync_policy,
	"Speculation policy: 0=disabled 1=adjacent[default] 2=stride 3=markov 4=oracle 5=null(worker-no-work)");
MODULE_PARM_DESC(specasync_offload_depth,
	"Offload depth: 0=metadata-only[default] 1=residency-prep 2=stub(unsafe)");
MODULE_PARM_DESC(specasync_oracle_trace_path,
	"Path to oracle trace file (u64 array of future fault addresses); policy=4 only");
MODULE_PARM_DESC(specasync_trace_ring_slots,
	"Fault-trace ring capacity in u64 entries, rounded up to a power of two (default 1048576)");

/* ── Gate E0.5 counters (defined here, declared extern in specasync_telemetry.h / specasync_internal.h) ── */
atomic_t g_specasync_trace_pushes           = ATOMIC_INIT(0);
atomic_t g_specasync_trace_overwrites       = ATOMIC_INIT(0);
atomic_t g_specasync_oracle_consumes        = ATOMIC_INIT(0);
atomic_t g_specasync_oracle_wraps           = ATOMIC_INIT(0);
atomic_t g_specasync_oracle_correct         = ATOMIC_INIT(0);
atomic_t g_specasync_oracle_predictions     = ATOMIC_INIT(0);
atomic_t g_specasync_oracle_correct_decile[10];
atomic_t g_specasync_oracle_total_decile[10];

/*
 * Gate E0.5 accuracy instrumentation: state for scoring each oracle
 * prediction against the fault it was made for, one call in arrears (see
 * specasync_oracle_next_addr_n(), further down this file, which is the
 * only reader/writer of these three fields). g_oracle_idx's own
 * atomic_fetch_add serializes callers' *cursor* advances into a total
 * order, but these three fields are a read-modify-write as a group and
 * need their own lock -- two concurrent callers could otherwise interleave
 * a read of g_oracle_last_pred from one call with a write from another.
 * Declared here (ahead of clear_write(), which resets
 * g_oracle_last_pred_valid) rather than next to g_oracle_trace/g_oracle_idx
 * below, purely for C's top-to-bottom declaration order.
 */
static u64            g_oracle_last_pred       = 0;
static int            g_oracle_last_pred_valid = 0;
static u32            g_oracle_last_pred_pos   = 0;
static DEFINE_SPINLOCK(g_oracle_score_lock);

/* ── Static debugfs dentries ─────────────────────────────────────────────── */

static struct dentry *specasync_dir;
static struct dentry *dentry_batch_log;
static struct dentry *dentry_worker_log;
static struct dentry *dentry_clear;
static struct dentry *dentry_fault_trace;
static struct dentry *dentry_decomp_log;

/* ── Ring-buffer read helper ─────────────────────────────────────────────── */

/*
 * Generic binary read: copies all committed records from the ring to userspace.
 * Records are copied in order from tail to head.  The ring is not drained —
 * subsequent reads return the same data until specasync_clear is written.
 *
 * This is intentionally a snapshot: the consumer reads the full history,
 * then writes to specasync_clear between experiment runs.
 */
static ssize_t ring_read_binary(char __user *ubuf, size_t count, loff_t *ppos,
				void *ring_buf, u32 head, u32 tail, u32 mask,
				size_t record_size)
{
	u32 avail, first_chunk, second_chunk;
	size_t bytes_avail, to_copy, pos;
	u8 *src = (u8 *)ring_buf;

	avail = head - tail;  /* u32 unsigned wrap — no masking needed */
	/* Convert from records to bytes */
	bytes_avail = (size_t)avail * record_size;

	if (*ppos >= (loff_t)bytes_avail)
		return 0;

	/* Snap to a whole number of records — avoids ppos drift on non-aligned reads. */
	to_copy = min(count, bytes_avail - (size_t)*ppos);
	to_copy = (to_copy / record_size) * record_size;
	if (to_copy == 0)
		return 0;
	pos     = (size_t)*ppos;

	/*
	 * Ring may wrap.  Compute linear position:
	 *   slot = (tail + pos/record_size) & mask
	 * Copy in up to two contiguous segments.
	 */
	{
		u32 start_slot = (tail + (u32)(pos / record_size)) & mask;
		u32 copy_slots = (u32)(to_copy / record_size);

		first_chunk  = min(copy_slots, (mask + 1) - start_slot);
		second_chunk = copy_slots - first_chunk;

		if (copy_to_user(ubuf,
				src + start_slot * record_size,
				first_chunk * record_size))
			return -EFAULT;

		if (second_chunk > 0) {
			if (copy_to_user(ubuf + first_chunk * record_size,
					src,
					second_chunk * record_size))
				return -EFAULT;
		}
	}

	*ppos += to_copy;
	return (ssize_t)to_copy;
}

/* ── debugfs file ops: batch log ─────────────────────────────────────────── */

static ssize_t batch_log_read(struct file *filp, char __user *ubuf,
			      size_t count, loff_t *ppos)
{
	struct specasync_batch_ring *r = &g_batch_ring;
	u32 head, tail;
	unsigned long flags;

	/* Snapshot head/tail under lock; copy without lock */
	spin_lock_irqsave(&r->lock, flags);
	head = r->head;
	tail = r->tail;
	spin_unlock_irqrestore(&r->lock, flags);

	return ring_read_binary(ubuf, count, ppos,
				r->buf, head, tail, r->mask,
				sizeof(struct specasync_batch_record));
}

static const struct file_operations batch_log_fops = {
	.owner = THIS_MODULE,
	.read  = batch_log_read,
	.llseek = default_llseek,
};

/* ── debugfs file ops: worker log ────────────────────────────────────────── */

static ssize_t worker_log_read(struct file *filp, char __user *ubuf,
			       size_t count, loff_t *ppos)
{
	struct specasync_work_ring *r = &g_work_ring;
	u32 head, tail;
	unsigned long flags;

	spin_lock_irqsave(&r->lock, flags);
	head = r->head;
	tail = r->tail;
	spin_unlock_irqrestore(&r->lock, flags);

	return ring_read_binary(ubuf, count, ppos,
				r->buf, head, tail, r->mask,
				sizeof(struct specasync_work_record));
}

static const struct file_operations worker_log_fops = {
	.owner = THIS_MODULE,
	.read  = worker_log_read,
	.llseek = default_llseek,
};

/* ── debugfs file ops: decomp log (Phase C) ──────────────────────────────── */

static ssize_t decomp_log_read(struct file *filp, char __user *ubuf,
			       size_t count, loff_t *ppos)
{
	struct specasync_decomp_ring *r = &g_decomp_ring;
	u32 head, tail;
	unsigned long flags;

	spin_lock_irqsave(&r->lock, flags);
	head = r->head;
	tail = r->tail;
	spin_unlock_irqrestore(&r->lock, flags);

	return ring_read_binary(ubuf, count, ppos,
				r->buf, head, tail, r->mask,
				sizeof(struct specasync_decomp_record));
}

static const struct file_operations decomp_log_fops = {
	.owner  = THIS_MODULE,
	.read   = decomp_log_read,
	.llseek = default_llseek,
};

/* ── debugfs file ops: clear ─────────────────────────────────────────────── */

static ssize_t clear_write(struct file *filp, const char __user *ubuf,
			   size_t count, loff_t *ppos)
{
	unsigned long flags;
	void *bbuf, *wbuf;

	/*
	 * Task A1 (AWS final work block): reset the global processed/enqueued/
	 * drops atomics here too, so each harness rep's specasync_clear write
	 * gives a clean per-run total straight from the counter -- no delta
	 * arithmetic needed. g_specasync_queue_depth is deliberately NOT reset:
	 * it tracks live outstanding work, not a per-run cumulative stat.
	 */
	atomic_set(&g_specasync_processed, 0);
	atomic_set(&g_specasync_enqueued, 0);
	atomic_set(&g_specasync_drops, 0);
	/* Gate B9: same per-run-clean-total reasoning as the three above. */
	atomic_set(&g_specasync_demand_faults, 0);
	atomic_set(&g_specasync_spec_hits, 0);
	atomic_set(&g_specasync_spec_migrations, 0);

	/*
	 * Gate E0.5: same per-run-clean-total reasoning, for the recording/
	 * consumption enumeration-parity and accuracy counters. g_oracle_idx
	 * (the trace replay cursor position) is deliberately NOT reset here,
	 * unchanged from existing behavior -- only g_oracle_last_pred_valid is
	 * cleared, so the first prediction scored after a clear is never
	 * compared against a stale prediction left over from before it.
	 */
	atomic_set(&g_specasync_trace_pushes, 0);
	atomic_set(&g_specasync_trace_overwrites, 0);
	atomic_set(&g_specasync_oracle_consumes, 0);
	atomic_set(&g_specasync_oracle_wraps, 0);
	atomic_set(&g_specasync_oracle_correct, 0);
	atomic_set(&g_specasync_oracle_predictions, 0);
	{
		int _d;
		for (_d = 0; _d < 10; _d++) {
			atomic_set(&g_specasync_oracle_correct_decile[_d], 0);
			atomic_set(&g_specasync_oracle_total_decile[_d], 0);
		}
	}
	{
		unsigned long _flags;
		spin_lock_irqsave(&g_oracle_score_lock, _flags);
		g_oracle_last_pred_valid = 0;
		spin_unlock_irqrestore(&g_oracle_score_lock, _flags);
	}

	/*
	 * Reset head/tail under the lock so the ring appears empty immediately.
	 * Then zero the backing buffers outside the lock — a 9 MB memset inside
	 * a spinlock would block hardware IRQs for milliseconds.  New records
	 * written during the memset will overwrite zeros, which is harmless.
	 */
	spin_lock_irqsave(&g_batch_ring.lock, flags);
	g_batch_ring.head = g_batch_ring.tail = g_batch_ring.drops = 0;
	bbuf = g_batch_ring.buf;
	spin_unlock_irqrestore(&g_batch_ring.lock, flags);

	spin_lock_irqsave(&g_work_ring.lock, flags);
	g_work_ring.head = g_work_ring.tail = g_work_ring.drops = 0;
	wbuf = g_work_ring.buf;
	spin_unlock_irqrestore(&g_work_ring.lock, flags);

	{
		void *dbuf;
		spin_lock_irqsave(&g_decomp_ring.lock, flags);
		g_decomp_ring.head = g_decomp_ring.tail = g_decomp_ring.drops = 0;
		dbuf = g_decomp_ring.buf;
		spin_unlock_irqrestore(&g_decomp_ring.lock, flags);
		if (dbuf)
			memset(dbuf, 0,
			       SPECASYNC_DECOMP_RING_SLOTS *
			       sizeof(struct specasync_decomp_record));
	}

	if (bbuf)
		memset(bbuf, 0,
		       SPECASYNC_BATCH_RING_SLOTS * sizeof(struct specasync_batch_record));
	if (wbuf)
		memset(wbuf, 0,
		       SPECASYNC_WORK_RING_SLOTS * sizeof(struct specasync_work_record));

	return (ssize_t)count;
}

static const struct file_operations clear_fops = {
	.owner = THIS_MODULE,
	.write = clear_write,
};

/* ── Oracle trace (policy 4) ─────────────────────────────────────────────── */

static u64    *g_oracle_trace      = NULL;
static size_t  g_oracle_trace_len  = 0;
static atomic_t g_oracle_idx       = ATOMIC_INIT(0);

/*
 * Load oracle trace from specasync_oracle_trace_path at module init.
 * File must be a flat binary array of little-endian u64 VA addresses.
 *
 * TODO[phase-b]: Verify that filp_open + kernel_read works from module init
 *   context on Linux 6.14.  An alternative is to expose a sysfs write node
 *   that accepts the path at runtime.
 */
static int specasync_load_oracle_trace(void)
{
	struct file *filp;
	loff_t size;
	ssize_t ret;

	if (!specasync_oracle_trace_path || !*specasync_oracle_trace_path)
		return 0;

	filp = filp_open(specasync_oracle_trace_path, O_RDONLY, 0);
	if (IS_ERR(filp)) {
		pr_warn("specasync: cannot open oracle trace %s: %ld\n",
			specasync_oracle_trace_path, PTR_ERR(filp));
		return PTR_ERR(filp);
	}

	size = i_size_read(file_inode(filp));
	if (size <= 0 || size % sizeof(u64) != 0) {
		pr_warn("specasync: oracle trace size %lld not a multiple of 8\n",
			(long long)size);
		filp_close(filp, NULL);
		return -EINVAL;
	}

	g_oracle_trace = vmalloc(size);
	if (!g_oracle_trace) {
		filp_close(filp, NULL);
		return -ENOMEM;
	}

	ret = kernel_read(filp, g_oracle_trace, size, &(loff_t){0});
	filp_close(filp, NULL);

	if (ret != size) {
		vfree(g_oracle_trace);
		g_oracle_trace = NULL;
		pr_warn("specasync: oracle trace short read (%zd/%lld)\n",
			ret, (long long)size);
		return -EIO;
	}

	g_oracle_trace_len = (size_t)(size / sizeof(u64));
	pr_info("specasync: oracle trace loaded: %zu entries\n", g_oracle_trace_len);
	return 0;
}

/*
 * specasync_oracle_next_addr() — return next fault address from trace.
 * Wraps around.  Returns 0 if no trace is loaded.
 */
u64 specasync_oracle_next_addr(void)
{
	int idx;

	if (!g_oracle_trace || g_oracle_trace_len == 0)
		return 0;

	idx = atomic_fetch_inc(&g_oracle_idx) % (int)g_oracle_trace_len;
	return g_oracle_trace[idx];
}
EXPORT_SYMBOL_GPL(specasync_oracle_next_addr);

/*
 * specasync_oracle_next_addr_n() — Gate B cursor-sync variant, Gate E0.5
 * accuracy-scoring variant.
 *
 * Advance the trace cursor by `consumed` (the number of demand faults the
 * current service batch will handle) and return the trace entry the cursor now
 * points at — i.e. the page expected to fault *next*, after this batch.  This
 * keeps the oracle cursor in lockstep with the per-fault demand stream; the old
 * per-batch (advance-by-1) cursor desynced as soon as any batch coalesced more
 * than one fault, so every "prediction" was an already-faulted page.  Still O(1):
 * one atomic add + one array index, no scan.
 *
 * Gate E0.5 addition: `current_fault_addr` is the address of the fault being
 * serviced right now -- i.e. the fault the *previous* call's return value
 * was a prediction for. Score it before computing the new prediction:
 * matching means the oracle correctly named this exact next fault. Also
 * counts total consumes (for the enumeration-parity check against
 * g_specasync_trace_pushes) and wraps (real count from the un-modulo'd
 * cumulative advance, not inferred).
 */
u64 specasync_oracle_next_addr_n(u64 current_fault_addr, u32 consumed)
{
	int old, len;
	u64 next_addr;
	unsigned long flags;
	u32 lap_before, lap_after, pred_pos, decile;

	if (!g_oracle_trace || g_oracle_trace_len == 0)
		return 0;
	if (consumed == 0)
		consumed = 1;

	len = (int)g_oracle_trace_len;

	atomic_inc(&g_specasync_oracle_consumes);

	spin_lock_irqsave(&g_oracle_score_lock, flags);
	if (g_oracle_last_pred_valid) {
		decile = (u32)(((u64)g_oracle_last_pred_pos * 10) / (u32)len);
		if (decile > 9)
			decile = 9;
		atomic_inc(&g_specasync_oracle_predictions);
		atomic_inc(&g_specasync_oracle_total_decile[decile]);
		if (g_oracle_last_pred == current_fault_addr) {
			atomic_inc(&g_specasync_oracle_correct);
			atomic_inc(&g_specasync_oracle_correct_decile[decile]);
		}
	}
	spin_unlock_irqrestore(&g_oracle_score_lock, flags);

	/* old = cursor before this batch; cursor becomes old + consumed */
	old = atomic_fetch_add((int)consumed, &g_oracle_idx);

	lap_before = (u32)old / (u32)len;
	lap_after  = (u32)(old + (int)consumed) / (u32)len;
	if (lap_after > lap_before)
		atomic_add((int)(lap_after - lap_before), &g_specasync_oracle_wraps);

	pred_pos  = ((unsigned)(old + (int)consumed)) % (unsigned)len;
	next_addr = g_oracle_trace[pred_pos];

	spin_lock_irqsave(&g_oracle_score_lock, flags);
	g_oracle_last_pred       = next_addr;
	g_oracle_last_pred_pos   = pred_pos;
	g_oracle_last_pred_valid = 1;
	spin_unlock_irqrestore(&g_oracle_score_lock, flags);

	/* Return the first page that will fault after this batch. */
	return next_addr;
}
EXPORT_SYMBOL_GPL(specasync_oracle_next_addr_n);

/* ── Ring buffer allocation / deallocation ───────────────────────────────── */

static int alloc_batch_ring(void)
{
	g_batch_ring.buf = kvmalloc_array(SPECASYNC_BATCH_RING_SLOTS,
					  sizeof(struct specasync_batch_record),
					  GFP_KERNEL | __GFP_ZERO);
	if (!g_batch_ring.buf)
		return -ENOMEM;
	g_batch_ring.mask = SPECASYNC_BATCH_RING_SLOTS - 1;
	g_batch_ring.head = g_batch_ring.tail = g_batch_ring.drops = 0;
	spin_lock_init(&g_batch_ring.lock);
	return 0;
}

static int alloc_work_ring(void)
{
	g_work_ring.buf = kvmalloc_array(SPECASYNC_WORK_RING_SLOTS,
					 sizeof(struct specasync_work_record),
					 GFP_KERNEL | __GFP_ZERO);
	if (!g_work_ring.buf)
		return -ENOMEM;
	g_work_ring.mask = SPECASYNC_WORK_RING_SLOTS - 1;
	g_work_ring.head = g_work_ring.tail = g_work_ring.drops = 0;
	spin_lock_init(&g_work_ring.lock);
	return 0;
}

static int alloc_decomp_ring(void)
{
	g_decomp_ring.buf = kvmalloc_array(SPECASYNC_DECOMP_RING_SLOTS,
					   sizeof(struct specasync_decomp_record),
					   GFP_KERNEL | __GFP_ZERO);
	if (!g_decomp_ring.buf)
		return -ENOMEM;
	g_decomp_ring.mask = SPECASYNC_DECOMP_RING_SLOTS - 1;
	g_decomp_ring.head = g_decomp_ring.tail = g_decomp_ring.drops = 0;
	spin_lock_init(&g_decomp_ring.lock);
	return 0;
}

static int alloc_trace_ring(void)
{
	u32 slots = (u32)specasync_trace_ring_slots;

	if (slots < 2)
		slots = SPECASYNC_TRACE_RING_SLOTS_DEFAULT;
	slots = roundup_pow_of_two(slots);

	g_trace_ring.buf = kvmalloc_array(slots, sizeof(u64), GFP_KERNEL | __GFP_ZERO);
	if (!g_trace_ring.buf)
		return -ENOMEM;
	g_trace_ring.mask = slots - 1;
	g_trace_ring.head = 0;
	spin_lock_init(&g_trace_ring.lock);
	pr_info("specasync: trace ring allocated: %u slots (%zu bytes)%s\n",
		slots, (size_t)slots * sizeof(u64),
		(slots != (u32)specasync_trace_ring_slots) ?
			" (rounded up to a power of two)" : "");
	return 0;
}

/*
 * debugfs read for the fault-address trace ring (flat u64 array, no tail
 * pointer -- the whole ring is "valid" once head exceeds capacity).
 *
 * Gate E0.5 fix: once wrapped, chronological order starts at the OLDEST
 * surviving slot (head % capacity, the slot about to be overwritten next),
 * not at physical slot 0. Reading linearly from slot 0 without this
 * rotation (the prior behavior) returned the right *set* of trailing
 * entries but in an order rotated by `head % capacity` places relative to
 * true recording order -- see GATE_E0_REPORT.md Sec. 3 for the original
 * finding. Below the wrap point (head <= capacity, i.e. every non-
 * oversubscribed collection today), start_slot is 0 and behavior is
 * byte-for-byte unchanged from before.
 */
static ssize_t trace_ring_read(struct file *filp, char __user *ubuf,
			       size_t count, loff_t *ppos)
{
	struct specasync_trace_ring *r = &g_trace_ring;
	u32 head, capacity, start_slot, avail_slots;
	size_t bytes_avail, to_copy, pos;
	unsigned long flags;

	spin_lock_irqsave(&r->lock, flags);
	head = r->head;
	spin_unlock_irqrestore(&r->lock, flags);

	capacity = r->mask + 1;

	if (head > capacity) {
		start_slot  = head & r->mask;   /* oldest surviving entry */
		avail_slots = capacity;
	} else {
		start_slot  = 0;
		avail_slots = head;
	}

	bytes_avail = (size_t)avail_slots * sizeof(u64);
	if (*ppos >= (loff_t)bytes_avail)
		return 0;

	to_copy = min(count, bytes_avail - (size_t)*ppos);
	/* Snap to whole u64 entries so the slot-boundary math below stays exact. */
	to_copy = (to_copy / sizeof(u64)) * sizeof(u64);
	if (to_copy == 0)
		return 0;
	pos = (size_t)*ppos;

	{
		u32 logical_slot0 = (u32)(pos / sizeof(u64));
		u32 copy_slots    = (u32)(to_copy / sizeof(u64));
		u32 phys_slot0    = (start_slot + logical_slot0) & r->mask;
		u32 first_chunk   = min(copy_slots, capacity - phys_slot0);
		u32 second_chunk  = copy_slots - first_chunk;

		if (copy_to_user(ubuf,
				(u8 *)r->buf + (size_t)phys_slot0 * sizeof(u64),
				(size_t)first_chunk * sizeof(u64)))
			return -EFAULT;

		if (second_chunk > 0) {
			if (copy_to_user(ubuf + (size_t)first_chunk * sizeof(u64),
					(u8 *)r->buf,
					(size_t)second_chunk * sizeof(u64)))
				return -EFAULT;
		}
	}

	*ppos += to_copy;
	return (ssize_t)to_copy;
}

static const struct file_operations trace_ring_fops = {
	.owner  = THIS_MODULE,
	.read   = trace_ring_read,
	.llseek = default_llseek,
};

/* ── Public init / exit ──────────────────────────────────────────────────── */

/*
 * specasync_debugfs_init() — call from nvidia_uvm module init.
 *
 * @parent_dentry: the existing /sys/kernel/debug/nvidia_uvm dentry.
 *
 * TODO[phase-b]: After lfs pull, find where uvm creates its debugfs root
 *   dentry and pass it here.  Likely in uvm_debug.c:uvm_debug_init() or
 *   similar.  See PHASE_B_INTEGRATION.md §1.
 */
int specasync_debugfs_init(struct dentry *parent_dentry)
{
	int ret;

	ret = alloc_batch_ring();
	if (ret)
		goto err_batch;

	ret = alloc_work_ring();
	if (ret)
		goto err_work;

	ret = alloc_trace_ring();
	if (ret)
		goto err_trace;

	ret = alloc_decomp_ring();
	if (ret)
		goto err_decomp;

	specasync_dir = debugfs_create_dir("specasync", parent_dentry);
	if (IS_ERR_OR_NULL(specasync_dir)) {
		ret = specasync_dir ? PTR_ERR(specasync_dir) : -ENOMEM;
		goto err_dir;
	}

	dentry_batch_log = debugfs_create_file("specasync_log", 0444,
					       specasync_dir, NULL,
					       &batch_log_fops);
	dentry_worker_log = debugfs_create_file("specasync_worker_log", 0444,
						specasync_dir, NULL,
						&worker_log_fops);
	dentry_clear      = debugfs_create_file("specasync_clear", 0222,
						specasync_dir, NULL,
						&clear_fops);
	dentry_fault_trace = debugfs_create_file("specasync_fault_trace", 0444,
						 specasync_dir, NULL,
						 &trace_ring_fops);
	dentry_decomp_log  = debugfs_create_file("specasync_decomp_log", 0444,
						 specasync_dir, NULL,
						 &decomp_log_fops);

	if (IS_ERR_OR_NULL(dentry_batch_log) ||
	    IS_ERR_OR_NULL(dentry_worker_log) ||
	    IS_ERR_OR_NULL(dentry_clear) ||
	    IS_ERR_OR_NULL(dentry_fault_trace) ||
	    IS_ERR_OR_NULL(dentry_decomp_log)) {
		ret = -EIO;
		goto err_files;
	}

	/*
	 * Task A1: true kernel-side totals, immune to ring wraparound (unlike
	 * counting specasync_log / specasync_worker_log records). Read as
	 * plain decimal text, e.g. `cat specasync_processed`.
	 */
	debugfs_create_atomic_t("specasync_processed", 0444, specasync_dir,
				&g_specasync_processed);
	debugfs_create_atomic_t("specasync_enqueued", 0444, specasync_dir,
				&g_specasync_enqueued);
	debugfs_create_atomic_t("specasync_drops", 0444, specasync_dir,
				&g_specasync_drops);

	/*
	 * Gate B9: same rationale, for the fields specasync_log/
	 * specasync_worker_log's ring saturation made unreliable as full-run
	 * totals (ARTIFACT_CATALOG.md "Second occurrence of artifact #7").
	 */
	debugfs_create_atomic_t("specasync_demand_faults", 0444, specasync_dir,
				&g_specasync_demand_faults);
	debugfs_create_atomic_t("specasync_spec_hits", 0444, specasync_dir,
				&g_specasync_spec_hits);
	debugfs_create_atomic_t("specasync_spec_migrations", 0444, specasync_dir,
				&g_specasync_spec_migrations);

	/*
	 * Gate E0.5: enumeration-parity (trace_pushes vs. oracle_consumes),
	 * ring-health (trace_overwrites, oracle_wraps), and accuracy
	 * (oracle_correct / oracle_predictions, overall and by decile of
	 * predicted position within the trace) counters. See
	 * GATE_E0_5_REPORT.md for how each is meant to be read.
	 */
	debugfs_create_atomic_t("specasync_trace_pushes", 0444, specasync_dir,
				&g_specasync_trace_pushes);
	debugfs_create_atomic_t("specasync_trace_overwrites", 0444, specasync_dir,
				&g_specasync_trace_overwrites);
	debugfs_create_atomic_t("specasync_oracle_consumes", 0444, specasync_dir,
				&g_specasync_oracle_consumes);
	debugfs_create_atomic_t("specasync_oracle_wraps", 0444, specasync_dir,
				&g_specasync_oracle_wraps);
	debugfs_create_atomic_t("specasync_oracle_correct", 0444, specasync_dir,
				&g_specasync_oracle_correct);
	debugfs_create_atomic_t("specasync_oracle_predictions", 0444, specasync_dir,
				&g_specasync_oracle_predictions);
	{
		static char decile_names[10][40];
		int _d;
		for (_d = 0; _d < 10; _d++) {
			snprintf(decile_names[_d], sizeof(decile_names[_d]),
				 "specasync_oracle_correct_decile%d", _d);
			debugfs_create_atomic_t(decile_names[_d], 0444, specasync_dir,
						&g_specasync_oracle_correct_decile[_d]);
		}
	}
	{
		static char decile_names2[10][40];
		int _d;
		for (_d = 0; _d < 10; _d++) {
			snprintf(decile_names2[_d], sizeof(decile_names2[_d]),
				 "specasync_oracle_total_decile%d", _d);
			debugfs_create_atomic_t(decile_names2[_d], 0444, specasync_dir,
						&g_specasync_oracle_total_decile[_d]);
		}
	}

	if (specasync_policy == 4)
		specasync_load_oracle_trace();

	pr_info("specasync: init OK  log_enabled=%d policy=%d offload_depth=%d decomp=%d\n",
		specasync_log_enabled, specasync_policy, specasync_offload_depth,
		SPECASYNC_DECOMP);
	return 0;

err_files:
	debugfs_remove_recursive(specasync_dir);
err_dir:
	kvfree(g_decomp_ring.buf);
	g_decomp_ring.buf = NULL;
err_decomp:
	kvfree(g_trace_ring.buf);
	g_trace_ring.buf = NULL;
err_trace:
	kvfree(g_work_ring.buf);
	g_work_ring.buf = NULL;
err_work:
	kvfree(g_batch_ring.buf);
	g_batch_ring.buf = NULL;
err_batch:
	return ret;
}
EXPORT_SYMBOL_GPL(specasync_debugfs_init);

void specasync_debugfs_exit(void)
{
	debugfs_remove_recursive(specasync_dir);
	specasync_dir = NULL;

	kvfree(g_batch_ring.buf);
	g_batch_ring.buf = NULL;

	kvfree(g_work_ring.buf);
	g_work_ring.buf = NULL;

	kvfree(g_trace_ring.buf);
	g_trace_ring.buf = NULL;

	kvfree(g_decomp_ring.buf);
	g_decomp_ring.buf = NULL;

	if (g_oracle_trace) {
		vfree(g_oracle_trace);
		g_oracle_trace = NULL;
	}
}
EXPORT_SYMBOL_GPL(specasync_debugfs_exit);
