# C4 status

Session start 2026-10-09 16:24:02. Documentation and analysis only: no module loads, no runs. Pushes after every step.

## Open for review
- Section I draft 3: see step 2.

## Log
- 16:24 **Step 1 DONE.** Merged origin/t4-replication (41 commits; 35 files; commit 22817ec). One conflict, tests/e09b_runner.py line 35 (REPO). **Decision (DOC-class):** the PATH_FIXES version (`SPECASYNC_ROOT`, default today's value) is kept, **and `SPECASYNC_REPO` (the T4 branch's name, exported by its `e7t4_runner.py`, `e7t4_orchestrate.py` and `e7t4_chain.sh`) is accepted as a fallback**: `os.environ.get("SPECASYNC_ROOT") or os.environ.get("SPECASYNC_REPO") or "<today's path>"`. Without the fallback the PATH_FIXES line alone would not cover the T4 edit (the T4 scripts would silently use the 5070 Ti path). Checked: unset -> default; SPECASYNC_REPO only -> that value; both -> SPECASYNC_ROOT; both empty -> default. PATH_FIXES.md lists SPECASYNC_ROOT only; its table is not edited (noted here). Controls re-run with no GPU: **T4 analyzer positive control PASS** (reproduces E7 Family A, -9.57%, p 1.08e-05); **E9 extraction control PASS**. No failures.
