#!/usr/bin/env python3
"""Gate E9: extract unified-memory counts from one nsys report (.nsys-rep). Used by tests/e9_runner.py after each traced run
and by tests/e9_analyze.py --control. Needs nsys 2025.3.2 (the reports named in the brief, cuda_um_*, do not exist in this version).

Sources, per run:
  * `nsys stats --report um_total_sum --format csv` -> Total HtoD / DtoH migration size (MB, 1e6 B), Total CPU page faults,
    Total GPU page faults.  (The report prints an empty cell for 0; treated as 0.)
  * the SQLite file that `nsys stats` exports next to the report:
      CUPTI_ACTIVITY_KIND_MEMCPY  copyKind 11 = UVM HtoD, 12 = UVM DtoH, 13 = UVM DtoD; migrationCause 2 = page fault,
                                  3 = speculative prefetch, 4 = eviction (ENUM_CUDA_UNIF_MEM_MIGRATION)
      CUDA_UM_GPU_PAGE_FAULT_EVENTS  (events and the sum of numberOfPageFaults)
      CUPTI_ACTIVITY_KIND_KERNEL  the per-pass windows: pass i = [start of kernel i, start of kernel i+1); only when the run has
                                  exactly PASSES kernel launches (bench_sparse); otherwise per-pass columns stay empty.
Thrashing, throttling and remote-map events are NOT available in this nsys version (no table, no report)."""
import csv
import io
import os
import sqlite3
import subprocess

PASSES = 3
CAUSE = {2: "fault", 3: "prefetch", 4: "evict"}


def stats_total(rep):
    r = subprocess.run(["nsys", "stats", "--report", "um_total_sum", "--format", "csv", "--force-export=true", rep],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"nsys stats failed rc={r.returncode}: {r.stderr[-200:]}")
    lines = r.stdout.splitlines()
    k = next((i for i, l in enumerate(lines) if l.startswith("Total HtoD Migration Size")), None)
    if k is None or k + 1 >= len(lines):
        raise RuntimeError(f"um_total_sum header/data not found in nsys stats output: {r.stdout[-300:]}")
    row = next(csv.DictReader(io.StringIO("\n".join(lines[k:k + 2]))))
    f = lambda s: float(s) if s not in ("", None) else 0.0  # noqa: E731
    return dict(report_htod_mb=f(row["Total HtoD Migration Size (MB)"]), report_dtoh_mb=f(row["Total DtoH Migration Size (MB)"]),
                report_cpu_faults=int(f(row["Total CPU Page Faults"])), report_gpu_faults=int(f(row["Total GPU PageFaults"])))


def extract(rep, keep_sqlite=False):
    out = stats_total(rep)
    db = os.path.splitext(rep)[0] + ".sqlite"
    if not os.path.exists(db):
        raise RuntimeError(f"SQLite export not found next to {rep}")
    c = sqlite3.connect(db)
    try:
        rows = c.execute("select copyKind, migrationCause, count(*), sum(bytes) from CUPTI_ACTIVITY_KIND_MEMCPY "
                         "where copyKind in (11,12,13) group by 1,2").fetchall()
        htod = {n: 0 for n in ("fault", "prefetch", "evict", "other")}
        dtoh = {n: 0 for n in ("fault", "prefetch", "evict", "other")}
        dtod = 0
        n_mig = 0
        for kind, cause, cnt, b in rows:
            n_mig += cnt
            name = CAUSE.get(cause, "other")
            if kind == 11:
                htod[name] += b or 0
            elif kind == 12:
                dtoh[name] += b or 0
            else:
                dtod += b or 0
        ev = c.execute("select count(*), coalesce(sum(numberOfPageFaults),0) from CUDA_UM_GPU_PAGE_FAULT_EVENTS").fetchone()
        out.update(htod_bytes=sum(htod.values()), dtoh_bytes=sum(dtoh.values()), dtod_bytes=dtod, uvm_migrations=n_mig,
                   htod_fault_bytes=htod["fault"], htod_prefetch_bytes=htod["prefetch"], htod_evict_bytes=htod["evict"], htod_other_bytes=htod["other"],
                   dtoh_fault_bytes=dtoh["fault"], dtoh_prefetch_bytes=dtoh["prefetch"], dtoh_evict_bytes=dtoh["evict"], dtoh_other_bytes=dtoh["other"],
                   gpu_fault_events=ev[0], gpu_faults_sum=ev[1])
        ks = [r[0] for r in c.execute("select start from CUPTI_ACTIVITY_KIND_KERNEL order by start")]
        for i in range(1, PASSES + 1):
            out[f"pass{i}_htod_bytes"] = out[f"pass{i}_dtoh_bytes"] = ""
        if len(ks) == PASSES:
            edges = ks + [float("inf")]
            for i in range(PASSES):
                for kind, col in ((11, "htod"), (12, "dtoh")):
                    q = c.execute("select coalesce(sum(bytes),0) from CUPTI_ACTIVITY_KIND_MEMCPY where copyKind=? and start>=? and start<?",
                                  (kind, edges[i], edges[i + 1] if edges[i + 1] != float("inf") else 2 ** 62)).fetchone()[0]
                    out[f"pass{i + 1}_{col}_bytes"] = q
    finally:
        c.close()
        if not keep_sqlite:
            os.remove(db)
    return out


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(extract(sys.argv[1], keep_sqlite=True), indent=1))
