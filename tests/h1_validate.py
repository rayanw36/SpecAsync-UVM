#!/usr/bin/env python3
"""Gate H1 phase 3b: correctness validation of the --alloc flag (timings are NOT recorded: kernel_ms and [RESULT] time lines are dropped before logging).
 1. managed mode unchanged: the committed-source binary (built from git HEAD before the change) and the new binary give identical output (timing lines masked)
    for bench_sparse (64 MiB and 1 GiB, K in {1,8,64,512}) and bench_stencil (N = 2048), with and without an explicit `--alloc managed`.
 2. malloc mode, bench_sparse: E8 checks (a)-(e) at 64 MiB and 1 GiB.
 3. malloc mode, bench_stencil: the 64-bit checksum of the final grid equals the managed-mode checksum and the CPU reference (N = 2048 and 4096).
 4. GPU residency in malloc mode (no UVM fault counter exists on the stock module: /proc/driver/nvidia-uvm has no per-GPU stats): nvidia-smi memory.used
    rises by about the array size while a 2 GiB malloc-mode run executes (device-private pages are allocated only by faults/migration on this configuration).
usage: h1_validate.py ORIG_DIR NEW_DIR   (ORIG_DIR holds bench_sparse_orig and bench_stencil_orig; NEW_DIR holds bench_sparse_new and bench_stencil_new)"""
import os, re, subprocess, sys, threading, time
ORIG, NEW = sys.argv[1], sys.argv[2]
LOG = "results/analysis/gate_e/h1/h1_validation.log"
out, fails = [], []
def run(cmd, env=None, timeout=300):
    e = dict(os.environ); e.update(env or {})
    r = subprocess.run(cmd, capture_output=True, text=True, env=e, timeout=timeout)
    return r.returncode, r.stdout, r.stderr
def mask(txt):
    return "\n".join(re.sub(r"[-+]?\d+\.\d+", "<num>", l) if ("kernel_ms" in l or "[RESULT] Time" in l or "Bandwidth" in l) else re.sub(r"0x[0-9a-f]+|\b[0-9a-f]{12}\b", "<ptr>", l)
                     for l in txt.splitlines())
def check(name, ok, detail=""):
    out.append(f"{'PASS' if ok else 'FAIL'}  {name} {detail}"); 
    if not ok: fails.append(name)
SP = lambda w: os.path.join(ORIG if w == "orig" else NEW, "bench_sparse_" + w)
ST = lambda w: os.path.join(ORIG if w == "orig" else NEW, "bench_stencil_" + w)
ORIGB, NEWB = "orig", "new"
for gib, label in ((0.0625, "64MiB"), (1, "1GiB")):
    for K in (1, 8, 64, 512):
        a = run([SP('orig'), str(gib), str(K), "3", "202610081"]); b = run([SP('new'), str(gib), str(K), "3", "202610081"]); c = run([SP('new'), str(gib), str(K), "3", "202610081", "--alloc", "managed"])
        check(f"managed unchanged [bench_sparse {label} K={K}]", a[0] == b[0] == c[0] == 0 and mask(a[1]) == mask(b[1]) == mask(c[1]) and mask(a[2]) == mask(b[2]), f"rc={a[0]},{b[0]},{c[0]}")
a = run([ST('orig'), "2048"]); b = run([ST('new'), "2048"]); c = run([ST('new'), "2048", "--alloc", "managed"])
check("managed unchanged [bench_stencil N=2048] (stdout and stderr, timing and pointers masked)", a[0] == b[0] == c[0] == 0 and mask(a[1]) == mask(b[1]) == mask(c[1]) and mask(a[2]) == mask(b[2]) == mask(c[2]))
def sp(gib, k, passes, seed, env=None):
    rc, o, e = run([SP('new'), str(gib), str(k), str(passes), str(seed), "--alloc", "malloc"], env)
    f = lambda pat: (re.search(pat, o).group(1) if re.search(pat, o) else None)
    return dict(rc=rc, txt=o, hash=f(r"page_list_hash=(\w+)"), touched=f(r"pages_touched=(\d+)"), blocks=f(r"blocks=(\d+)"), distinct=f(r"distinct_pages=(\d+)"),
                total=f(r"total_pages=(\d+)"), ck=f(r"checksum=(\w+) "), ex=f(r"expected_checksum=(\w+)"))
for gib, label in ((0.0625, "64MiB"), (1, "1GiB")):
    for K in (1, 8, 64, 512):
        d = sp(gib, K, 3, 202610081); tag = f"malloc {label} K={K}"
        check(f"(a) checksum == host reference [{tag}]", d["rc"] == 0 and d["ck"] == d["ex"], f"checksum={d['ck']}")
        check(f"(b) pages_touched = K x blocks [{tag}]", d["touched"] and int(d["touched"]) == K * int(d["blocks"]), f"{d['touched']} = {K} x {d['blocks']}")
        if K == 512: check(f"(d) K=512 touches every page exactly once per pass [{tag}]", d["distinct"] == d["total"] == d["touched"])
    a, b, c = sp(gib, 8, 3, 202610081), sp(gib, 8, 3, 202610081), sp(gib, 8, 3, 202610082)
    check(f"(c) same seed -> same page_list_hash [malloc {label}]", a["hash"] == b["hash"] and a["hash"], a["hash"])
    check(f"(c) different seed -> different page_list_hash [malloc {label}]", a["hash"] != c["hash"])
    w = sp(gib, 8, 3, 202610081, {"SPARSE_TEST_REF_OFFSET": "1"})
    check(f"(e) off-by-one host reference is detected [malloc {label}]", w["rc"] == 1 and "CHECKSUM MISMATCH" in w["txt"])
    m = run([SP('new'), str(gib), "8", "3", "202610081", "--alloc", "managed"])[1]
    mk = re.search(r"checksum=(\w+) ", m).group(1)
    check(f"malloc checksum equals managed checksum [{label} K=8]", a["ck"] == mk, f"{a['ck']} vs {mk}")
for N in (2048, 4096):
    got = {}
    for mode in ("managed", "malloc"):
        rc, o, e = run([ST('new'), str(N), "--alloc", mode], {"STENCIL_CHECKSUM": "1"})
        got[mode] = (rc, re.search(r"\[CHECKSUM\] (\w+)", o).group(1), re.search(r"\[CHECKSUM_REF\] (\w+)", o).group(1))
    check(f"bench_stencil checksum: malloc == managed == CPU reference [N={N}]", got["managed"][0] == got["malloc"][0] == 0 and got["managed"][1] == got["malloc"][1] == got["managed"][2] == got["malloc"][2], str(got))
# GPU residency: sample nvidia-smi memory.used during a 2 GiB malloc-mode run
def used():
    return int(subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip())
base = used(); peak = [base]; stop = threading.Event()
def sample():
    while not stop.is_set(): peak[0] = max(peak[0], used()); time.sleep(0.05)
t = threading.Thread(target=sample); t.start()
d = sp(2, 512, 3, 202610081); stop.set(); t.join()
check("GPU residency in malloc mode: memory.used rose during a 2 GiB K=512 run", d["rc"] == 0 and peak[0] - base >= 1500, f"baseline {base} MiB, peak {peak[0]} MiB, rise {peak[0] - base} MiB (array 2048 MiB)")
out.append("NOTE  no UVM fault counter exists on the stock module (/proc/driver/nvidia-uvm has no per-GPU statistics); GPU residency above is the evidence that faults/migration occur in malloc mode.")
out.append("OVERALL: " + ("PASS" if not fails else "FAIL: " + "; ".join(fails)))
open(LOG, "w").write("\n".join(out) + "\n"); print("\n".join(out)); sys.exit(1 if fails else 0)
