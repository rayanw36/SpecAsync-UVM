# Pre-migration notes (Part 3)

Generated before any files move to the T4 instance. `MANIFEST.sha256` (repo root, 631
entries) covers `results/`, `tools/`, `tests/`, `benchmarks/`, `paper/` — verify byte-for-
byte on arrival with `sha256sum -c MANIFEST.sha256` from the repo root.

## 1. Working-tree / branch state

**The working tree is NOT clean, and this predates this session — do not "fix" it without
explicit instruction.**

```
 M driver/patches/specasync_selective_apply.patch
 M driver/patches/specasync_uvm_v580.95.05.patch
 M driver/patches/specasync_uvm_v595.71.05.patch
?? manuscript_assets.tar.gz
?? manuscript_assets/
```

**Root cause (confirmed, not new):** these three `.patch` files are Git-LFS-tracked
(`.gitattributes`: `*.patch filter=lfs diff=lfs merge=lfs -text`), but `git-lfs` is not
installed on this machine (`git lfs status` → "'lfs' is not a git command"; every commit
in this session has also printed "This repository is configured for Git LFS but 'git-lfs'
was not found on your path" from the post-commit hook). The git index holds LFS pointer
stubs (a ~100-byte `oid`/`size` text blob); the working tree holds the real expanded patch
content (up to 2.96M lines for the v580.95.05 patch, since per `driver/PORTING_NOTES_595.md`
it embeds an entire source tree). This is why `git diff --stat` on these three files shows
millions of changed lines — it is comparing a pointer to real content, not two real
diffs. **This was already independently diagnosed by an earlier session** (see
`manuscript_assets/MANIFEST.md` §0, generated before this work block) — consistent,
stable, not something that changed during this session's commits.

**Do not `git add`/commit these three files without git-lfs installed first.** Committing
the raw content directly (bypassing LFS) would silently convert them from
LFS-pointer-tracked to a multi-megabyte regular blob in git history — a one-way, hard-to-
reverse change to how the repo is tracked. **Recommended fix path on the T4 instance (or
wherever this repo is committed from next):** install `git-lfs`, run `git lfs install`,
then `git checkout -- driver/patches/` to re-smudge the working tree from the LFS-backed
blobs already in history (do **not** run this checkout here — it was not run in this
session precisely because git-lfs isn't available to do it safely).

**`manuscript_assets/` and `manuscript_assets.tar.gz` are untracked**, produced by a prior
session's read-only discovery/staging pass (see `manuscript_assets/MANIFEST.md` for full
provenance — branch topology, an R1-R12 evidence coverage table, and a gap list). Left
untouched; not part of this session's scope. Recommend the manuscript author decide
whether to commit this bundle, exclude it via `.gitignore`, or discard it once its content
has been cross-checked against the `results/analysis/*.md` files this session produced
(there is some overlap in intent — both this session and that prior pass independently
catalogue the same 5 measurement artifacts, for example).

**Branches** (`git branch -a`): `main`, `phaseB-v595-port`, `phaseB1-pipeline-fix`,
`phaseB2-decisive`, `phaseC-decomp`, `figures-phase2`, **`manuscript-prep` (current, all
of this session's work)**. History is linear (`main` → ... → `phaseC-decomp` →
`figures-phase2` → `manuscript-prep`), confirmed via the ancestor chain already documented
in `manuscript_assets/MANIFEST.md` §1 for the branches up to `phaseC-decomp`; the two
newest branches (`figures-phase2`, `manuscript-prep`) simply extend that same linear chain
with commit-per-gate work, verified by this session's own `git log --oneline` at every
gate. **All of this session's work is committed** on `manuscript-prep` — no uncommitted
changes from this session's own tasks exist; the three modified `.patch` files and the two
untracked `manuscript_assets*` paths are the *only* non-clean items, and both predate this
session.

## 2. The two blocked GPU tasks (exact specs, restated for continuity)

Neither was attempted, simulated, or estimated in this work block, per its explicit
charter. Both require the T4 instance with the correct driver.

- **Task 2a — prefetch-off hit-rate rerun.** Needed to fill the real-benchmark
  prefetch-OFF hit-rate gap documented in `tools/figures/make_fig_the_squeeze.py`'s stdout
  and Figure 3 (`the_squeeze`) of `paper/main.tex`. No estimate exists anywhere for this;
  the figure explicitly shows "NOT FOUND," not a placeholder number.
- **Task 2b — cuFFT interleaved T4 rerun.** Needed to give the abstract's cuFFT "4.4%"
  figure a second-platform data point. See `results/analysis/COMPLETENESS_LEDGER.md`'s
  "cuFFT-hedge decision point" section for the three ways the manuscript could handle this
  in the meantime.

A third, newly-surfaced (not yet authorized) candidate task from this block's Task G:

- **Task 2c (proposed, not yet approved) — paired wall-clock timing for 6 of 7 Phase C
  workloads.** Needed to compute an end-to-end pipelining ceiling beyond the single
  Stencil-24K data point currently computable (see `results/analysis/PIPELINING_CEILING.md`).
  Flagged for the author's sign-off, not attempted.

**Driver version that MUST be verified before any run on the T4 instance:** `595.71.05`.

```bash
ls /usr/src/ | grep nvidia
nvidia-smi --query-gpu=driver_version --format=csv
```

If either command does not show `595.71.05` (or the corresponding dkms/module version),
**stop and report rather than running anything** — per this session's standing module-
safety rules (back up the stock `nvidia-uvm.ko`, only swap `nvidia_uvm`, verify
`srcversion`, rollback on oops). Run on this machine for documentation purposes only (no
GPU present here, as expected):

```
$ ls /usr/src/ | grep nvidia          # (no output -- no nvidia src tree on this machine)
$ nvidia-smi --query-gpu=driver_version --format=csv
bash: nvidia-smi: command not found   # (expected -- no GPU on this machine)
```

## 3. Transfer size and exclusion recommendations

| Path | Size | Recommendation |
|---|---|---|
| `results/` | 860M | **Selectively exclude the raw per-work-item/per-batch ring dumps** — see below |
| `driver/build/` | 217M | **Exclude** — compiled `.ko` build artifacts, fully reconstructible from `driver/src/` + `driver/patches/` via the documented build scripts; no reason to transfer binaries when the target machine will rebuild from source anyway |
| `.git/` | 273M | Transfer (it's the repository) |
| `tools/`, `tests/`, `benchmarks/`, `paper/` | 180K + 2.5M + 5.2M + 296K = ~8M | Transfer in full — small, all load-bearing |
| **Total working tree** | **~1.6G** | |

**Within `results/` (860M), the large-file concentration is already characterized by
the prior session's bundling pass** (`manuscript_assets/MANIFEST.md` §3): the bulk is
`work_records.csv` (per-work-item speculative-worker telemetry, ~163MB untracked +
individually up to 12MB/file for the oversubscription benchmarks) and `batch_records.csv`
(~85MB, git-tracked). Every headline number derived from these raw ring dumps is already
restated in a `.md`/`.txt` report or a small aggregate CSV (`timing_raw.csv`,
`phaseB_timing.csv`, `gate3_times.csv`, `decomp_*.csv`, etc.) — none of which are large.
**Recommendation: exclude `**/work_records.csv` and `**/batch_records.csv` from the T4
transfer** (they are also not needed there — the T4 instance will generate its own fresh
versions of these files if/when Tasks 2a/2b/2c run) **but do not delete them from this
machine** — they remain the only raw evidence for several already-published numbers (see
`manuscript_assets/MANIFEST.md` §4's R1/R9/R10 rows) and, per that same manifest §6, a
meaningful subset of them are gitignored and exist *only* on this machine's disk. Losing
this machine's copy without a separate backup would make those specific raw-evidence files
unrecoverable.

**Build-artifact exclusions**, consistent with the repo's own `.gitignore` conventions:
`*.o`, `*.ko`, `*.mod`, `*.mod.c`, `driver/build/*.ko`, `__pycache__/`, LaTeX build
artifacts (`paper/*.aux`, `.bbl`, `.blg`, `.log`, `.pdf` — reproducible via `pdflatex` +
`bibtex`, see `paper/main.tex`'s own build-verification note).

## 4. What this session added since the prior manuscript_assets pass

For continuity: this session's commits (`figures-phase2` → `manuscript-prep`) added
5 figures (`results/figures/*.pdf`/`.png`), the exclusion manifest, a cuFFT provenance
audit, and 12 new `results/analysis/*.md` files (statistics, outlier forensics, multiple-
comparison correction, GraphBFS anomaly, pipelining ceiling, statistic-of-record, D5
characterization, artifact catalog v2, claim scope, bibliography audit, completeness
ledger) plus `paper/main.tex` + `paper/ref.bib`. None of this overlaps destructively with
`manuscript_assets/`'s earlier bundle — that bundle is a raw-evidence staging area; this
session's output is derived analysis and manuscript scaffolding built from (and citing)
that same underlying `results/` tree.
