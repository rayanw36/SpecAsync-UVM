#!/usr/bin/env python3
"""Gate E8 Phase 1: correctness validation of benchmarks/bench_sparse (timings are NOT recorded or reported:
per-pass kernel_ms lines are dropped before logging). Writes results/analysis/gate_e/e8/bench_validation.log."""
import re, subprocess, sys, os
B = os.path.join(os.path.dirname(__file__), "..", "benchmarks", "bench_sparse")
LOG = os.path.join(os.path.dirname(__file__), "..", "results", "analysis", "gate_e", "e8", "bench_validation.log")
out, fails = [], []
def run(gib, k, passes, seed, env=None):
    e = dict(os.environ); e.update(env or {})
    r = subprocess.run([B, str(gib), str(k), str(passes), str(seed)], capture_output=True, text=True, env=e, timeout=300)
    txt = "\n".join(l for l in r.stdout.splitlines() if "kernel_ms" not in l)
    f = lambda pat: re.search(pat, r.stdout).group(1) if re.search(pat, r.stdout) else None
    d = dict(rc=r.returncode, txt=txt, hash=f(r"page_list_hash=(\w+)"), touched=f(r"pages_touched=(\d+)"),
             blocks=f(r"blocks=(\d+)"), distinct=f(r"distinct_pages=(\d+)"), total=f(r"total_pages=(\d+)"),
             ck=f(r"checksum=(\w+) "), ex=f(r"expected_checksum=(\w+)"))
    return d
def check(name, ok, detail=""):
    out.append(f"{'PASS' if ok else 'FAIL'}  {name} {detail}")
    if not ok: fails.append(name)
for gib, label in ((0.0625, "64MiB"), (1, "1GiB")):
    for K in (1, 8, 64, 512):
        d = run(gib, K, 3, 202610081)
        tag = f"{label} K={K}"
        check(f"(a) checksum == host reference [{tag}]", d["rc"] == 0 and d["ck"] == d["ex"], f"checksum={d['ck']}")
        check(f"(b) pages_touched = K x blocks [{tag}]", d["touched"] and int(d["touched"]) == K * int(d["blocks"]), f"{d['touched']} = {K} x {d['blocks']}")
        if K == 512:
            check(f"(d) K=512 touches every page exactly once per pass [{tag}]",
                  d["distinct"] == d["total"] == d["touched"], f"distinct={d['distinct']} total={d['total']} touched={d['touched']}")
    a, b = run(gib, 8, 3, 202610081), run(gib, 8, 3, 202610081)
    c = run(gib, 8, 3, 202610082)
    check(f"(c) same seed -> same page_list_hash [{label}]", a["hash"] == b["hash"] and a["hash"], a["hash"])
    check(f"(c) different seed -> different page_list_hash [{label}]", a["hash"] != c["hash"], f"{a['hash']} vs {c['hash']}")
    w = run(gib, 8, 3, 202610081, {"SPARSE_TEST_REF_OFFSET": "1"})
    check(f"(e) off-by-one host reference is detected [{label}]", w["rc"] == 1 and "CHECKSUM MISMATCH" in w["txt"] and w["ck"] != w["ex"],
          f"rc={w['rc']} checksum={w['ck']} expected={w['ex']}")
out.append("OVERALL: " + ("PASS" if not fails else "FAIL: " + "; ".join(fails)))
os.makedirs(os.path.dirname(LOG), exist_ok=True)
open(LOG, "w").write("\n".join(out) + "\n")
print("\n".join(out))
sys.exit(1 if fails else 0)
