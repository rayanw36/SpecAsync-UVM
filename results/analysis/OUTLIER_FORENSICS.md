# Outlier and run-order forensics (Task B1)

Source: `results/phaseB2/gate3/gate3_times.csv` (same primary record as `STATISTICS.md`). No new data source introduced.

## 1. Run-order and timestamp availability

`gate3_times.csv` has columns `config,bench,run,wall_s`. There is **no wall-clock timestamp column** anywhere in this file or in `GATE3_report.md`. The only ordering signal is the integer `run` field, which restarts at 1 for each (config, bench) pair -- a per-config repetition index, not a global sequence number. This limits the analysis: we can determine each config's own internal run order and, from `GATE3_report.md`'s own prose plus CSV row order, the coarse block/interleave structure across configs -- but not wall-clock gaps, time of day, or drift in real seconds (only in run-index units).

**Ordering structure, per `GATE3_report.md` ("Configuration definitions" section, verbatim):** "C1/C2 are interleaved (runtime param switch per run, no reload) to control for drift. C0 and C3 are separate reloads." Corroborated by CSV row order: all 15 C0-stencil rows, then all 15 C0-bfs rows, then C1/C2-stencil alternating row by row (C1 run1, C2 run1, C1 run2, C2 run2, ...), then C1/C2-bfs alternating the same way, then all 15 C3-stencil rows, then all 15 C3-bfs rows.

**Answering Task B1 Q3: Gate 3 used a mixed design, not one uniform scheme.** C0 and C3 are each a single blocked run (15 reps back-to-back, own driver reload). C1 and C2 are interleaved *with each other* (drift control between exactly those two), but that [C1,C2] pair is itself a separate block from C0 and from C3. So: C0 blocked, [C1,C2] interleaved-pair-block, C3 blocked -- none of C0, [C1,C2], C3 are interleaved with each other. This matters directly for the six comparisons: C3-vs-C1, C3-vs-C0, and C2-vs-C1 (wait -- C2 and C1 ARE in the same interleaved block) -- so of the three comparison pairs used throughout this project, **only C2-vs-C1 has drift control between the two arms being compared**; C3-vs-C1 and C3-vs-C0 compare across separate blocks/reloads with no drift control. This is a real limitation on how much weight the C3-vs-C1 and C3-vs-C0 comparisons (the abstract's headline pair) can carry, independent of anything found below.

## 2. Outlier scan, all eight cells (Tukey fence: Q1-1.5*IQR .. Q3+1.5*IQR)

| Config | Benchmark | n | fence low | fence high | flagged (run#=value) | position pattern |
|---|---|---|---|---|---|---|
| C0 | Stencil-24K | 15 | 4.2275 | 4.2875 | run1=4.34 | position 1 of 15 (start of block) |
| C1 | Stencil-24K | 15 | 15.0000 | 15.6400 | none | none flagged |
| C2 | Stencil-24K | 15 | 15.8825 | 17.7025 | run4=17.73 | position 4 of 15 (start of block) |
| C3 | Stencil-24K | 15 | 12.4400 | 20.0800 | none | none flagged |
| C0 | GraphBFS-23 | 15 | 55.2775 | 55.7375 | run14=61.51, run15=59.78 | positions [14, 15] of 15 (clustered near the end) |
| C1 | GraphBFS-23 | 15 | 58.3625 | 58.8625 | run3=59.02, run8=58.96, run13=59.03 | positions [3, 8, 13] of 15 (spread across the block (start to end)) |
| C2 | GraphBFS-23 | 15 | 58.0825 | 58.9025 | run5=58.96, run15=59.07 | positions [5, 15] of 15 (clustered near the end) |
| C3 | GraphBFS-23 | 15 | 57.8175 | 59.7975 | none | none flagged |

### 2a. C3/Stencil-24K -- position detail (as requested)

Full sequence in run order: run1=15.59, run2=15.22, run3=17.30, run4=17.29, run5=17.30, run6=15.68, run7=17.23, run8=15.81, run9=15.22, run10=17.20, run11=15.73, run12=15.14, run13=15.39, run14=15.18, run15=15.48

**The Tukey fence flags zero points here** -- this is itself a finding, not an absence of one. `STATISTICS.md` correctly describes this distribution as bimodal (two of fifteen was the task's own estimate; the actual split by eye at a 16.5s threshold is **5 of fifteen high** (run3=17.30, run4=17.29, run5=17.30, run7=17.23, run10=17.20) vs **10 of fifteen low** (run1=15.59, run2=15.22, run6=15.68, run8=15.81, run9=15.22, run11=15.73, run12=15.14, run13=15.39, run14=15.18, run15=15.48)). A classical Tukey fence is built from Q1/Q3/IQR of the *whole* sample, so when ~1/3 of the sample sits in a separate cluster, that cluster inflates Q3 and the IQR enough that the fence widens to include it -- the textbook "masking" failure mode of single-pass outlier tests on multimodal data. **This changes the diagnosis, not just the label**: a masked/undetected classical outlier pattern would suggest isolated noise; a genuine bimodal split that a fence can't even flag suggests two stable, reproducible operating states (e.g. two different scheduling/cache/TLB regimes), which is a materially different (and arguably more concerning, since it may recur every run rather than being a one-off) explanation than host noise.

**Position pattern of the high cluster:** positions [3, 4, 5, 7, 10] of 15 (clustered near the start). Positions [3, 4, 5, 7, 10] include a run of three consecutive positions (3,4,5) plus two more nearby (7,10); all of positions 11-15 (the last third of the block) are low. This is neither a pure warm-up pattern (would front-load at 1-2) nor a pure cool-down pattern (would back-load at 14-15) -- it is concentrated in the early-to-middle part of the block, which is most consistent with a transient noise episode (e.g. a neighboring EC2 tenant or a periodic system task active during roughly a third of the run) superimposed on an otherwise consistent ~15.3s baseline, rather than a strictly alternating or evenly-spread mechanism.

### 2b. All other flagged cells -- position detail

**C0/Stencil-24K:** run1=4.34, run2=4.26, run3=4.23, run4=4.25, run5=4.26, run6=4.26, run7=4.25, run8=4.27, run9=4.28, run10=4.25, run11=4.24, run12=4.27, run13=4.25, run14=4.23, run15=4.25

Flagged: position 1 of 15 (start of block) -- ['run1=4.34'].

**C2/Stencil-24K:** run1=17.69, run2=17.00, run3=17.63, run4=17.73, run5=16.75, run6=16.80, run7=16.63, run8=16.63, run9=16.40, run10=16.76, run11=16.43, run12=16.50, run13=17.04, run14=16.65, run15=16.48

Flagged: position 4 of 15 (start of block) -- ['run4=17.73'].

**C0/GraphBFS-23:** run1=55.67, run2=55.55, run3=55.48, run4=55.48, run5=55.49, run6=55.46, run7=55.54, run8=55.48, run9=55.41, run10=55.42, run11=55.44, run12=55.58, run13=55.28, run14=61.51, run15=59.78

Flagged: positions [14, 15] of 15 (clustered near the end) -- ['run14=61.51', 'run15=59.78'].
Already noted in `GATE3_report.md`'s own "C0 GraphBFS anomaly detail" section as "likely EC2 scheduling noise", there without a formal outlier test; this confirms that attribution with a Tukey fence and gives the exact positions (last two of the block).

**C1/GraphBFS-23:** run1=58.68, run2=58.53, run3=59.02, run4=58.62, run5=58.67, run6=58.58, run7=58.55, run8=58.96, run9=58.56, run10=58.47, run11=58.55, run12=58.61, run13=59.03, run14=58.55, run15=58.49

Flagged: positions [3, 8, 13] of 15 (spread across the block (start to end)) -- ['run3=59.02', 'run8=58.96', 'run13=59.03'].

**C2/GraphBFS-23:** run1=58.39, run2=58.52, run3=58.43, run4=58.50, run5=58.96, run6=58.41, run7=58.63, run8=58.43, run9=58.33, run10=58.85, run11=58.39, run12=58.56, run13=58.38, run14=58.27, run15=59.07

Flagged: positions [5, 15] of 15 (clustered near the end) -- ['run5=58.96', 'run15=59.07'].

**Cross-cell summary:** the flagged/notable points across cells sit at different temporal positions -- start of block (C2/Stencil partially), end of block (C0/GraphBFS), scattered mid-block (C1/GraphBFS, C2/GraphBFS), and an un-fenced bimodal split that is itself concentrated early-to-mid-block (C3/Stencil). There is no single shared position pattern across cells, which argues against one continuous session-wide drift and is more consistent with **independent, episodic host-noise events** recurring at different points across the several separate blocks/reloads that make up Gate 3 -- the working hypothesis this task asked us to test, not assume, and which the position data supports better than a single-mechanism story.

## 3. Six comparisons, with and without flagged outliers

"Without" removes exactly the Tukey-flagged points from section 2 from whichever side(s) of each comparison have any (C3/Stencil has none flagged by the fence itself -- see 2a's masking note -- so its comparisons are unchanged by this step even though its distribution is visibly bimodal).

| Comparison | Benchmark | n (with -> without) | Welch p (with) | Welch p (without) | MWU p (with) | MWU p (without) | d (with) | d (without) | Verdict changes? |
|---|---|---|---|---|---|---|---|---|---|
| C3 vs C1 | Stencil-24K | 15v15 -> 15v15 | 0.009693 | 0.009693 | 0.0361 | 0.0361 | 1.084 | 1.084 | **no** |
| C2 vs C1 | Stencil-24K | 15v15 -> 14v15 | 7.271e-10 | 7.388e-10 | 3.366e-06 | 5.056e-06 | 4.504 | 4.877 | **no** |
| C3 vs C0 | Stencil-24K | 15v15 -> 15v14 | 3.201e-17 | 3.275e-17 | 3.161e-06 | 4.727e-06 | 18.304 | 17.989 | **no** |
| C3 vs C1 | GraphBFS-23 | 15v15 -> 15v12 | 0.1623 | 0.01872 | 0.2367 | 0.06339 | 0.528 | 0.915 | **YES** |
| C2 vs C1 | GraphBFS-23 | 15v15 -> 13v12 | 0.1481 | 0.03691 | 0.03087 | 0.01425 | -0.544 | -0.883 | **no** |
| C3 vs C0 | GraphBFS-23 | 15v15 -> 15v13 | 7.258e-05 | 1.686e-17 | 0.0006663 | 7.771e-06 | 1.980 | 13.370 | **no** |

**Verdict flips under outlier removal (by the OR-of-two-tests rule, i.e. significant if either Welch or MWU is <0.05):** C3 vs C1 (GraphBFS-23). Both the with- and without-outlier numbers are reported in the table above per the task's instruction; neither is chosen as authoritative. Any manuscript sentence resting on a flipped comparison must either report both or explicitly justify which sample it uses.

**Caveat on the one flip found (C3 vs C1, GraphBFS-23):** `STATISTICS.md` established that normality is rejected for this pair, making Mann-Whitney the authoritative test, not Welch. Without outliers, Welch drops to p=0.0187 (significant) but MWU only drops to p=0.0634 (still not significant at alpha=0.05). By the authoritative-test rule alone (MWU only), this comparison does **not** flip -- it is the OR-of-both-tests rule that flips it. Reported both ways; the MWU-only reading is more consistent with this project's own stated methodology.

## 4. Time-correlated drift check (Spearman rank correlation, value vs run-index, per cell)

| Config | Benchmark | Spearman rho | p-value | Verdict |
|---|---|---|---|---|
| C0 | Stencil-24K | -0.316 | 0.2506 | no significant trend |
| C1 | Stencil-24K | -0.844 | 7.512e-05 | significant monotonic trend |
| C2 | Stencil-24K | -0.624 | 0.01296 | significant monotonic trend |
| C3 | Stencil-24K | -0.467 | 0.07932 | no significant trend |
| C0 | GraphBFS-23 | -0.022 | 0.9394 | no significant trend |
| C1 | GraphBFS-23 | -0.312 | 0.2579 | no significant trend |
| C2 | GraphBFS-23 | -0.070 | 0.8049 | no significant trend |
| C3 | GraphBFS-23 | 0.004 | 0.9899 | no significant trend |

**Cells with a significant monotonic run-index trend:** C1/Stencil-24K (rho=-0.844, p=7.512e-05); C2/Stencil-24K (rho=-0.624, p=0.01296). Both flagged cells are on Stencil-24K (C1 and C2), both with **negative** rho -- times trend *down* across the run sequence, i.e. runs get slightly faster later in the block (consistent with e.g. GPU clock/thermal ramp-up or a caching effect settling in, not with accumulating noise). Note this is a monotonic-trend test and is a different phenomenon from the positional clustering in section 2 (which is step-like, not monotonic) -- C1/Stencil has no Tukey-flagged points at all (section 2) but still shows a significant monotonic drift here, showing the two checks catch different things.

## 5. Gate B1 summary

- **Run ordering:** no timestamps exist, only per-config ordinal run index. Cross-config structure recovered from `GATE3_report.md` prose + CSV row order: C0 blocked, [C1,C2] interleaved-with-each-other block, C3 blocked. Of the three comparison pairs used throughout the project, only C2-vs-C1 has drift control between its two arms; C3-vs-C1 and C3-vs-C0 (the abstract's headline pair) do not.
- **Outlier positions:** C3/Stencil's bimodal 5-high/10-low split is NOT flagged by a Tukey fence at all (masking effect of the bimodal spread on the fence itself) and clusters early-to-mid-block (not start or end). C0/GraphBFS's two outliers sit at the tail (positions 14-15, matching the report's own noted anomaly). Other cells show scattered, smaller flagged points. No single temporal signature is shared across cells.
- **With/without-outlier sensitivity:** see section 3's table for which of the six verdicts flip.
- **Drift:** C1/Stencil and C2/Stencil show a significant monotonic downward (faster-over-time) trend; no other cell does. See section 4.
