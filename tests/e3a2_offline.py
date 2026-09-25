#!/usr/bin/env python3
"""Gate E3a-2 offline analysis (no runs, no module).

B2: region sharing in first-touch table order. For W in {16, 64}:
  consecutive  = fraction of entries i >= 1 whose region equals entry i-1's
  lastK[K]     = fraction of entries whose region is in a FIFO of the last K
                 distinct regions *inserted* (a region is inserted only when it
                 misses, exactly as the round-robin array design would insert
                 only on enqueue). K = 1 is the current single-region design.
  region ID = page_addr >> (PAGE_SHIFT + log2 W), PAGE_SHIFT = 12.
C: range index for the fast oracle -- maximal runs of consecutive pages in
  the SORTED page set; count, longest run, and index memory
  (per range: u64 base + u32 len + u32 offset = 16 B, plus one u32 rank per
  page).
Usage: e3a2_offline.py TABLE_DIR [TABLE_DIR ...]
"""
import struct
import sys
from collections import deque

MAGIC = 0x3145545454465350
PAGE_SHIFT = 12


def load(path):
    data = open(path, "rb").read()
    magic, n = struct.unpack_from("<QQ", data, 0)
    assert magic == MAGIC, hex(magic)
    pages = struct.unpack_from(f"<{n}Q", data, 16)
    assert len(set(pages)) == n
    return pages


def sharing(pages, W, Ks=(1, 2, 4, 8)):
    sh = PAGE_SHIFT + W.bit_length() - 1
    rid = [p >> sh for p in pages]
    consec = sum(1 for i in range(1, len(rid)) if rid[i] == rid[i - 1]) / (len(rid) - 1)
    out = {}
    for K in Ks:
        buf, s, hits = deque(maxlen=K), set(), 0
        for r in rid:
            if r in s:
                hits += 1
            else:
                if len(buf) == K:
                    s.discard(buf[0])
                buf.append(r)
                s.add(r)
        out[K] = hits / len(rid)
    return consec, out


def ranges(pages):
    sp = sorted(p >> PAGE_SHIFT for p in pages)
    runs, start, longest = 0, 0, 0
    for i in range(1, len(sp) + 1):
        if i == len(sp) or sp[i] != sp[i - 1] + 1:
            runs += 1
            longest = max(longest, i - start)
            start = i
    return runs, longest, runs * 16 + len(sp) * 4


def main():
    for d in sys.argv[1:]:
        for wl in ("stencil", "graphbfs"):
            pages = load(f"{d}/{wl}_ft_table.bin")
            print(f"== {d} {wl}: {len(pages)} distinct pages")
            for W in (16, 64):
                c, k = sharing(pages, W)
                ratio = k[1] / k[8] if k[8] else float("nan")
                print(f"  W={W:3d} consecutive={c:.4f} " + " ".join(f"K{K}={v:.4f}" for K, v in k.items())
                      + f"  K1/K8={ratio:.4f}")
            r, lo, mem = ranges(pages)
            print(f"  ranges={r} longest_run={lo} pages; index bytes={mem} ({mem/1e6:.2f} MB)"
                  f" vs existing sorted table {len(pages)*16} B + table {len(pages)*8} B")


if __name__ == "__main__":
    main()
