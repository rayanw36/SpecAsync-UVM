# Gate E5 — Does speculation help by feeding the prefetcher?

## Headline

**H-feed: SUPPORTED** (pre-registered, applied mechanically).

The fault reduction behind E4's result **depends entirely on the prefetcher's
density rule**:
- **D(51) = +0.401.** C7W512 has 40% fewer demand faults than C0 at the
  default threshold (Holm-significant).
- **D(T_off) = −0.022.** With the density rule disabled, the reduction is
  gone. C7W512 has 2.1% *more* faults than C0-toff (Holm-significant).
- D(T_off)/D(51) = −0.054, below the pre-registered 0.25.
- The dose-response held: **D(75) = +0.534 ≥ D(51)**.

Speculation still never maps. The prefetcher maps regions pushed over its
density threshold by residency that speculation created.

**A pre-registered secondary prediction failed, and it is reported plainly.**
H-feed predicted that the *wall-clock* gain would shrink or vanish at T_off
along with the fault reduction. **It did not.** C7W512 is faster than C0 at
every threshold:
- **−5.26%** at 51;
- **−10.12%** at 75;
- **−21.04%** at T_off.

At T_off, no faults are prevented. There the gain coincides instead with the
under-lock servicing phase D5 falling from 1.732 s to 0.619 s. That is the
separate pre-staging mechanism E0.9b and E1 Part B identified: copy work
removed from the servicing thread.

**H-feed explains the fault reduction, not all of the wall-clock gain.** How
the default-threshold gain splits between the two mechanisms was not
pre-registered and is not separable from these data (Exploratory item 1).

Platform: RTX 5070 Ti, driver 595.91.07, kernel 7.0.0-34-generic, Stencil-24K
only. Module `nvidia-uvm-specasync-NEW-e3a2-width-ftfast.ko` (srcversion
`33FD42E6E16B0A6658E2BEB`) in every arm.
- Pre-registration: `E5_PREREGISTRATION.md`, commit `9834517`, before the
  first run.
- Source check: `E5_MECHANISM.md`, commit `48e7a78`.
- Status: `E5_STATUS.md`.

## Step 1 — Source answers (summary; full citations in `E5_MECHANISM.md`)

1. **Resident pages count.**
   - The density bitmap is `resident_mask | faulted_pages`
     (`uvm_perf_prefetch.c:227`).
   - `resident_mask` is the **destination processor's** resident mask
     (`:396-397`).
   - Residency is the only input; mapping state does not enter. So a page the
     speculative worker made resident but did not map counts.
   - `grow_fault_granularity` also fills 64 KB big-page regions around
     faulted pages in that bitmap (`:160`).
2. **Already-resident prefetched pages are mapped in the same service
   step.**
   - The prefetch mask is ORed into `new_residency_mask`
     (`uvm_va_block.c:11532`).
   - `did_not_migrate_mask` is computed but not removed (`:11947`).
   - The protection loop covers every page in `new_residency_mask`
     (`:11961`), and `block_service_finish_map()` maps them (`:11981`).
3. **Threshold.**
   - `counter*100 > subregion_pages*threshold`, strict, in percent (`:118`).
   - Accepted range 0–100; values above 100 **silently fall back to 51**
     (`:552-561`).
   - `uint`, `S_IRUGO`, so it can be set at `insmod` and read back (`:60`).
   - **T_off = 100** can never fire, because `counter ≤ subregion_pages`
     (`:117`).
4. **What survives at T_off for Stencil: no prefetch pages at all.**
   - Big-page growth only feeds the density count.
   - First-touch whole-block population (`:404-407`) needs the GPU to be the
     preferred location, and Stencil sets none.
   - PTE merging cannot absorb unmapped pages (contract at
     `uvm_va_block.c:7329`).
   - H-feed was therefore not refuted from source, and the test proceeded.

## Run integrity

```
rows 60 / 60
order adherence: 60 / 60 in sequence; mismatches []
srcversions ['33FD42E6E16B0A6658E2BEB']; exit codes ['0']
dmesg new lines total 0; runs with any []
MemAvailable kB before 61231176-61474896 after 61029180-61230656
ring coverage 100% on 60 / 60; max records 74963
Identity 1 holds 30 / 30 (fails []); Identity 2 holds 30 / 30 (fails [])
ft_fast_verified = 1 on 30 / 30; cas_giveup max 0; region_invalid max 0
```

- 60/60 runs, no stop condition, no interruption, no re-run.
- `uvm_perf_prefetch_threshold` was set at `insmod` and verified by
  read-back on every run (51 / 75 / 100).

## Primary — fault reduction D(t) and the H-feed verdict

| threshold | median demand faults C0 | median demand faults C7W512 | D(t) | MWU p (demand faults) | Holm thr | Holm-sig |
|---|---|---|---|---|---|---|
| 51 | 339,386 | 203,331 | **+0.4009** | 1.08e-05 | 0.0167 | True |
| 75 | 469,506 | 218,928 | **+0.5337** | 1.08e-05 | 0.0250 | True |
| 100 (T_off) | 2,932,890 | 2,995,898 | **-0.0215** | 1.08e-05 | 0.0500 | True |

D(T_off) / D(51) = -0.0536  ->  H-feed verdict (pre-registered, mechanical): **SUPPORTED**
Dose-response (secondary): D(75) = +0.5337 vs D(51) = +0.4009 -> D(75) >= D(51): True

The pre-registered rule is:
- **Supported:** D(51) > 0 and Holm-significant, and
  D(T_off) < 0.25 × D(51).
- **Refuted:** D(T_off) ≥ 0.75 × D(51).
- **Partial:** anything between.

Here D(51) = +0.401, Holm-significant, and D(T_off) = −0.022 < 0.25 × 0.401.
The verdict is **SUPPORTED**.

**Dose-response (secondary):** D(75) = +0.534 ≥ D(51) = +0.401, so the
prediction held. A stricter threshold weakens the stock prefetcher (C0-t75
has 469,506 faults against 339,386 at t51). Speculation's residency then
pushes more regions over the line: C7W512-t75 has 218,928 faults.

## Secondary — wall-clock (one Holm family of 3)

| threshold | comparison | median C0 (s) | median C7W512 (s) | Δ (s) | Δ % | MWU p | Holm thr | verdict | Cohen's d | MDE (s) | MDE α/3 (s) | without outliers: Δ / p / Holm-sig (n) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 51 | C7W512-t51 vs C0-t51 | 1.1265 | 1.0673 | -0.0592 | -5.26% | 1.08e-05 | 0.0167 | **C7W512 faster** | -2.45 | 0.0351 | 0.0405 | -0.0565 / 2.2e-05 / yes (9/10) |
| 75 | C7W512-t75 vs C0-t75 | 1.2593 | 1.1319 | -0.1275 | -10.12% | 1.08e-05 | 0.0250 | **C7W512 faster** | -8.15 | 0.0204 | 0.0236 | -0.1275 / 1.1e-05 / yes (10/10) |
| 100 | C7W512-toff vs C0-toff | 4.6600 | 3.6797 | -0.9803 | -21.04% | 1.08e-05 | 0.0500 | **C7W512 faster** | -51.56 | 0.0238 | 0.0275 | -0.9803 / 1.1e-05 / yes (10/10) |

Each is within a threshold. C0-t75 and C0-toff are **not** the shipped
driver. The H-feed prediction ("the gain shrinks or vanishes at T_off") **did
not hold**: the gain is largest at T_off (see Headline and Exploratory
item 1).

## Mechanism metrics (per-cell medians)

| threshold | arm | demand faults | fault_already_resident (fraction of distinct pages) | predictions | same-region skips | enqueued | drops | spec_pages_requested | D5 (s) | pre-lock svc−D3−D4 (s) | enqueue_overhead (s) | wall median (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 51 | C0 | 339,386 | 0 (0.0000) | 0 | 0 | 0 | 0 | 0 | 0.1052 | 0.0013 | 0.0000 | 1.1265 |
| 51 | C7W512 | 203,331 | 23,297 (0.0207) | 203,331 | 201,133 | 2,198 | 0 | 838,792 | 0.0561 | 0.0058 | 0.0008 | 1.0673 |
| 75 | C0 | 469,506 | 0 (0.0000) | 0 | 0 | 0 | 0 | 0 | 0.1721 | 0.0021 | 0.0000 | 1.2593 |
| 75 | C7W512 | 218,928 | 22,220 (0.0198) | 218,928 | 216,730 | 2,198 | 0 | 871,560 | 0.0694 | 0.0062 | 0.0008 | 1.1319 |
| 100 | C0 | 2,932,890 | 0 (0.0000) | 0 | 0 | 0 | 0 | 0 | 1.7318 | 0.0140 | 0.0000 | 4.6600 |
| 100 | C7W512 | 2,995,898 | 1,124,488 (0.9995) | 1,124,998 | 1,122,799 | 2,199 | 0 | 1,125,000 | 0.6188 | 0.0574 | 0.0011 | 3.6797 |

`spec_hits` is not used here; it is a 10 ms staleness-window counter, not a
win counter.

## Figure

`e5_threshold.png` / `.pdf` plots demand faults and wall-clock against the
threshold, with C0 and C7W512 as two series and individual runs as points.

## Exploratory — not confirmatory

1. **Two mechanisms, not one.**
   - **At T_off:**
     - Speculation prevents no faults: 2,995,898 against 2,932,890, even
       with 99.95% of distinct pages staged ahead of their fault.
     - Yet C7W512-toff is 0.98 s (21%) faster than C0-toff.
     - D5 falls by 1.113 s (1.732 → 0.619 s) while pre-lock servicing rises
       by 0.043 s.
     - The gain there tracks **copy work removed from the servicing thread**
       (the D5 mechanism in `E1_PARTB_CEILING_RECONCILIATION.md`), not fault
       prevention.
   - **At t51:**
     - Faults fall 40% (H-feed) and D5 falls 0.049 s (0.105 → 0.056).
     - The wall-clock gain is 0.059 s.
     - How it splits between the two mechanisms is **not separable** from
       these data, and nothing is attributed.
2. **C0-toff (4.66 s) is slower than a true prefetch-off run.** E4's C1 was
   4.30 s (cross-session, not a test). This is consistent with the stated
   limitation: at T_off the prefetch hint is still computed on every fault
   but yields nothing.
3. **C7W512-toff (3.68 s) against E4's C6-W512 with prefetch off (3.30 s).**
   This is cross-session and not a test. It is the same staging with a
   useless prefetch hint computed per fault, so it is also consistent with
   item 2.
4. **The stock prefetcher's own threshold sensitivity.** Raising the
   threshold from 51 to 75 costs the shipped configuration +38% faults and
   +11.8% wall-clock (C0-t75 vs C0-t51). The default 51 is better for Stencil
   than 75.
5. **Staging without mapping raises faults slightly.**
   - D(T_off) is −2.1% and Holm-significant.
   - E4's C6-W512 against C1 was +1.3% (cross-session).
   - The cause is not investigated.

## Existing claims these results bear on (flagged, not edited)

**E4 Exploratory item 4** (the untested mechanism hypothesis):
- Now **supported by a pre-registered test for the fault reduction.** The
  40% fault drop exists only while the prefetcher's density rule can fire.
- **Corrected in scope:** the fault reduction is not the only source of
  C7W512's wall-clock advantage. Copy-offload (D5) contributes
  independently, and at T_off it is the whole gain.

**The paper's central claim:** E4's falsification (Stencil C7-W512 beats C0
by 4.93%) stands, and E5 **replicates it**: C7W512-t51 vs C0-t51 is −5.26%,
Holm-significant, in a new session. The mechanism for a restatement is:
- **Off-path speculation cannot prevent faults by itself** (H-map; E5 at
  T_off).
- With the in-path density prefetcher on, **residency created by
  speculation lets the prefetcher map whole regions early**, preventing
  about 40% of Stencil's faults (H-feed).
- **Independently, pre-staging removes copy work from the servicing
  thread.**
- Both are shown with a **perfect** first-touch oracle, on one workload and
  one platform.

**H-map** (speculation never maps): **stands**. At T_off, 99.95% of pages
are staged and no fault is prevented.

**Claim 8** (turning the prefetcher off costs more than the oracle can
recover): **consistent.** C7W512-toff (3.68 s) is still 3.27× C0-t51
(1.13 s).

**Claim 15** (the pipelining ceiling bounds D1+D2 overlap): the E1 Part B
scope flag stands. The gains here come through fault prevention and D5, not
D1+D2.

**Claims 5, 7 and 10:** no change beyond E4's flags.

## Stated limitations

- Single workload (Stencil-24K), single platform (RTX 5070 Ti, driver
  595.91.07, kernel 7.0.0-34).
- `uvm_perf_prefetch_threshold` changes the prefetcher for C0 too.
  C0-t75 and C0-toff are **not** the shipped driver; every comparison is
  within a threshold.
- The oracle is a **perfect** first-touch table. This gate explains the
  mechanism, not what a practical predictor achieves.
- At T_off the prefetch hint is still computed and costs time.
