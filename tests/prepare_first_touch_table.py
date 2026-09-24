#!/usr/bin/env python3
"""Gate E0.9a — build a first-touch prediction table from a collected fault
trace, for the policy-6 ("first-touch oracle") kernel module.

Usage: prepare_first_touch_table.py <trace.bin> <out_table.bin> [expected_distinct_pages]

Input: a raw fault trace as collected since Gate E0.5 (flat u64 array of
page-aligned fault addresses, one entry per coalesced fault, in service
order) -- e.g. results/phaseB1/gate_e07_check1/stencil24k_trace.bin.

Steps (all userspace, nothing here runs in the kernel):
  1. Mask every address to page granularity. Verified from source
     (driver/src/uvm_gpu_replayable_faults.c, preprocess_fault_batch()'s own
     comment: "GPU already reports 4K-aligned address", plus the earlier
     `current_entry->fault_address = UVM_PAGE_ALIGN_DOWN(...)` in
     fetch_fault_buffer_entries()) that fault_address is already page-aligned
     by the time it reaches the trace -- this mask is a defensive no-op on
     every trace this project has ever collected, not a required step. Done
     anyway, unconditionally, per instruction.
  2. Reduce to first-touch order: each distinct page once, in the order it
     first appears.
  3. Assert the distinct-page count against the given expected value (E0.8's
     1,125,000 for Stencil-24K / 287,956 for GraphBFS-23). If it does not
     match, STOP and report -- do not write a table.
  4. Write the table: a flat file the kernel module reads directly.

Output file format (all little-endian):
    u64 magic   = 0x3145545454465350  ("PSFTTTE1" packed LE, arbitrary)
    u64 count   = N (distinct pages)
    u64 first_touch[N]   -- rank -> page, in first-touch order

The kernel builds its OWN sorted (page, rank) lookup structure from
first_touch[] at load time via the kernel's sort(), rather than this script
writing a second, redundant copy of the same information pre-sorted --
avoids two independently-derived copies going out of sync.
"""
import sys
import struct

PAGE_SIZE = 4096
PAGE_MASK = ~(PAGE_SIZE - 1) & 0xFFFFFFFFFFFFFFFF
MAGIC = 0x3145545454465350


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    trace_path = sys.argv[1]
    out_path = sys.argv[2]
    expected = int(sys.argv[3]) if len(sys.argv) > 3 else None

    with open(trace_path, "rb") as f:
        raw = f.read()
    if len(raw) % 8 != 0:
        print(f"ERROR: {trace_path} size {len(raw)} is not a multiple of 8", file=sys.stderr)
        sys.exit(1)
    n_entries = len(raw) // 8
    addrs = struct.unpack(f"<{n_entries}Q", raw)

    masked_count = sum(1 for a in addrs if (a & ~PAGE_MASK) != 0)
    print(f"[prepare_ft_table] {trace_path}: {n_entries} entries; "
          f"{masked_count} were NOT already page-aligned before masking "
          f"(expected 0, per source: fault_address is page-aligned by the "
          f"driver before it ever reaches the trace)")

    seen = set()
    first_touch = []
    for a in addrs:
        p = a & PAGE_MASK
        if p not in seen:
            seen.add(p)
            first_touch.append(p)

    distinct = len(first_touch)
    print(f"[prepare_ft_table] distinct pages (first-touch order): {distinct}")

    if expected is not None and distinct != expected:
        print(f"STOP: distinct-page count {distinct} != expected {expected}. "
              f"Collection has changed since E0.8 -- every comparison to "
              f"E0.7/E0.8 would be invalid. Table NOT written.", file=sys.stderr)
        sys.exit(2)

    with open(out_path, "wb") as f:
        f.write(struct.pack("<QQ", MAGIC, distinct))
        f.write(struct.pack(f"<{distinct}Q", *first_touch))

    print(f"[prepare_ft_table] wrote {out_path}: magic={MAGIC:#x} count={distinct} "
          f"({16 + 8*distinct} bytes)")


if __name__ == "__main__":
    main()
