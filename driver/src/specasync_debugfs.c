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
#include "specasync_telemetry.h"

/* ── Global ring buffer instances ────────────────────────────────────────── */

struct specasync_batch_ring  g_batch_ring;
struct specasync_work_ring   g_work_ring;
struct specasync_trace_ring  g_trace_ring;

/* Module parameters — defined here, declared extern in specasync_telemetry.h */
int   specasync_log_enabled       = 1;
int   specasync_policy            = 1;   /* 1 = adjacent-page */
int   specasync_offload_depth     = 0;   /* 0 = metadata-only */
int   specasync_trace_faults      = 0;   /* 0 = disabled; 1 = record demand-fault addrs */
char *specasync_oracle_trace_path = NULL;

module_param(specasync_log_enabled,       int,  0644);
module_param(specasync_policy,            int,  0644);
module_param(specasync_offload_depth,     int,  0644);
module_param(specasync_trace_faults,      int,  0644);
module_param(specasync_oracle_trace_path, charp, 0444);

MODULE_PARM_DESC(specasync_log_enabled,
	"Enable telemetry ring buffers (1=enabled [default], 0=disabled)");
MODULE_PARM_DESC(specasync_policy,
	"Speculation policy: 0=disabled 1=adjacent[default] 2=stride 3=markov 4=oracle");
MODULE_PARM_DESC(specasync_offload_depth,
	"Offload depth: 0=metadata-only[default] 1=residency-prep 2=stub(unsafe)");
MODULE_PARM_DESC(specasync_oracle_trace_path,
	"Path to oracle trace file (u64 array of future fault addresses); policy=4 only");

/* ── Static debugfs dentries ─────────────────────────────────────────────── */

static struct dentry *specasync_dir;
static struct dentry *dentry_batch_log;
static struct dentry *dentry_worker_log;
static struct dentry *dentry_clear;
static struct dentry *dentry_fault_trace;

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

	to_copy = min(count, bytes_avail - (size_t)*ppos);
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

/* ── debugfs file ops: clear ─────────────────────────────────────────────── */

static ssize_t clear_write(struct file *filp, const char __user *ubuf,
			   size_t count, loff_t *ppos)
{
	unsigned long flags;
	void *bbuf, *wbuf;

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

static int alloc_trace_ring(void)
{
	g_trace_ring.buf = kvmalloc_array(SPECASYNC_TRACE_RING_SLOTS,
					  sizeof(u64), GFP_KERNEL | __GFP_ZERO);
	if (!g_trace_ring.buf)
		return -ENOMEM;
	g_trace_ring.mask = SPECASYNC_TRACE_RING_SLOTS - 1;
	g_trace_ring.head = 0;
	spin_lock_init(&g_trace_ring.lock);
	return 0;
}

/* debugfs read for the fault-address trace ring (flat u64 array, no tail ptr) */
static ssize_t trace_ring_read(struct file *filp, char __user *ubuf,
			       size_t count, loff_t *ppos)
{
	struct specasync_trace_ring *r = &g_trace_ring;
	u32 head;
	size_t bytes_avail, to_copy;
	unsigned long flags;

	spin_lock_irqsave(&r->lock, flags);
	head = r->head;
	spin_unlock_irqrestore(&r->lock, flags);

	/* Clamp to ring size; head may have wrapped beyond one revolution */
	if (head > SPECASYNC_TRACE_RING_SLOTS)
		head = SPECASYNC_TRACE_RING_SLOTS;

	bytes_avail = (size_t)head * sizeof(u64);
	if (*ppos >= (loff_t)bytes_avail)
		return 0;
	to_copy = min(count, bytes_avail - (size_t)*ppos);
	if (copy_to_user(ubuf, (u8 *)r->buf + *ppos, to_copy))
		return -EFAULT;
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

	if (IS_ERR_OR_NULL(dentry_batch_log) ||
	    IS_ERR_OR_NULL(dentry_worker_log) ||
	    IS_ERR_OR_NULL(dentry_clear) ||
	    IS_ERR_OR_NULL(dentry_fault_trace)) {
		ret = -EIO;
		goto err_files;
	}

	if (specasync_policy == 4)
		specasync_load_oracle_trace();

	pr_info("specasync: init OK  log_enabled=%d policy=%d offload_depth=%d\n",
		specasync_log_enabled, specasync_policy, specasync_offload_depth);
	return 0;

err_files:
	debugfs_remove_recursive(specasync_dir);
err_dir:
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

	if (g_oracle_trace) {
		vfree(g_oracle_trace);
		g_oracle_trace = NULL;
	}
}
EXPORT_SYMBOL_GPL(specasync_debugfs_exit);
