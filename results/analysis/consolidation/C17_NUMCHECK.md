# C17 number check (section 9, abstract, figure captions; same rules as C15)

Rule as C14: a token is MATCH if it equals a number in `paper/support/RESULTS_FACTS.md` as a string or after rounding to its printed digits (fraction x100 for percentages). Integers below 20 without a unit are `small` (counts, section numbers; matches are ambiguous). `also in extract` = found in `EVIDENCE_EXTRACT.md` when not in RESULTS_FACTS. Cite keys, labels, refs and `\texttt` evidence ids are removed first.

## section9_discussion.tex

16 tokens.

| line | number | status | context |
|---|---|---|---|
| 18 | 99.95\% | MATCH (string) | staged 99.95\% of pages ahead of demand, and the copies it made shortened the |
| 32 | 24 | MATCH (string) | measurements bound what it could gain only indirectly, since Stencil-24K |
| 33 | 9.57\% | MATCH (string) | already runs 9.57\% faster when the prefetcher simply maps more on each fault. |
| 42 | 64 | MATCH (string) | between 8 and 64 pages per 2\,MB block. The second is memory pressure: on managed memory |
| 53 | 23\% | MATCH (string) | six times less often while initialising the array; on dense cells 17--23\% of |
| 66 | 50 | MATCH (string) | MI250X \cite{cooper2024svm}. Whether a density-aware prefetch policy would help |
| 73 | 24 | MATCH (string) | The oracle is near-perfect only for Stencil-24K, whose first-touch order varies |
| 74 | 23 | MATCH (string) | by about a hundred ranks between runs; for GraphBFS-23 it is a weakened oracle. |
| 82 | 5070 | MATCH (string) | come from the RTX~5070~Ti alone, from one synthetic benchmark with one fixed |
| 110 | 3.4 | MATCH (string) | shipped driver it helps, by 3.4--5.3\% on a regular workload, only by raising |
| 110 | 5.3\% | MATCH (string) | shipped driver it helps, by 3.4--5.3\% on a regular workload, only by raising |

Not matched in RESULTS_FACTS: 0 (of which NOT FOUND anywhere: 0).

## abstract_title.tex

16 tokens.

| line | number | status | context |
|---|---|---|---|
| 24 | 99.95\% | MATCH (string) | installs GPU mappings, so with the driver's prefetcher off, staging 99.95\% of |
| 25 | 2.92\times | MATCH (string) | pages ahead of demand left the run $2.92\times$ slower than the shipped driver. |
| 26 | 3.4 | MATCH (string) | With the prefetcher on, staging beats the shipped driver by 3.4--5.3\% on a |
| 26 | 5.3\% | MATCH (string) | With the prefetcher on, staging beats the shipped driver by 3.4--5.3\% on a |
| 29 | 51 | MATCH (string) | confirms the mechanism. Lowering that threshold from 51 to 0, without |
| 30 | 9.57\% | MATCH (string) | speculation, is faster still: 9.57\% on an RTX~5070~Ti and 5.1\% on a Tesla~T4, |
| 30 | 5070 | MATCH (string) | speculation, is faster still: 9.57\% on an RTX~5070~Ti and 5.1\% on a Tesla~T4, |
| 30 | 5.1\% | MATCH (string) | speculation, is faster still: 9.57\% on an RTX~5070~Ti and 5.1\% on a Tesla~T4, |
| 31 | 2.8\% | MATCH (string) | and at matched thresholds speculation adds at most 2.8\%. The threshold cuts |
| 33 | 41 | MATCH (string) | 41--85\% slower, moving up to $32.8\times$ more data, and on system-allocated |
| 33 | 85\% | MATCH (string) | 41--85\% slower, moving up to $32.8\times$ more data, and on system-allocated |
| 33 | 32.8\times | MATCH (string) | 41--85\% slower, moving up to $32.8\times$ more data, and on system-allocated |
| 34 | 204\% | MATCH (string) | (HMM) memory, which the driver migrates in 4\,KB units, sparse access is 204\% |
| 36 | 31 | MATCH (string) | the threshold trade-off. We also catalog 31 measurement artifacts met in this |

Not matched in RESULTS_FACTS: 0 (of which NOT FOUND anywhere: 0).

## c17_captions.txt

102 tokens.

| line | number | status | context |
|---|---|---|---|
| 1 | 5070 | MATCH (string) | RTX 5070 Ti, driver 595.91.07, stock prefetcher on: wall-clock change of the staging arms relative t |
| 1 | 595.91 | MATCH (string) | RTX 5070 Ti, driver 595.91.07, stock prefetcher on: wall-clock change of the staging arms relative t |
| 1 | 24 | MATCH (string) | RTX 5070 Ti, driver 595.91.07, stock prefetcher on: wall-clock change of the staging arms relative t |
| 1 | 23 | MATCH (string) | RTX 5070 Ti, driver 595.91.07, stock prefetcher on: wall-clock change of the staging arms relative t |
| 1 | 512 | MATCH (string) | RTX 5070 Ti, driver 595.91.07, stock prefetcher on: wall-clock change of the staging arms relative t |
| 1 | 24 | MATCH (string) | RTX 5070 Ti, driver 595.91.07, stock prefetcher on: wall-clock change of the staging arms relative t |
| 1 | 4.93 | MATCH (string) | RTX 5070 Ti, driver 595.91.07, stock prefetcher on: wall-clock change of the staging arms relative t |
| 2 | 5070 | MATCH (string) | RTX 5070 Ti, stock prefetcher, Stencil-24K: D(t) = 1 - (median demand faults of C7W512) / (median of |
| 2 | 24 | MATCH (string) | RTX 5070 Ti, stock prefetcher, Stencil-24K: D(t) = 1 - (median demand faults of C7W512) / (median of |
| 2 | 0.4009 | MATCH (string) | RTX 5070 Ti, stock prefetcher, Stencil-24K: D(t) = 1 - (median demand faults of C7W512) / (median of |
| 2 | 51 | MATCH (string) | RTX 5070 Ti, stock prefetcher, Stencil-24K: D(t) = 1 - (median demand faults of C7W512) / (median of |
| 2 | 0.5337 | MATCH (string) | RTX 5070 Ti, stock prefetcher, Stencil-24K: D(t) = 1 - (median demand faults of C7W512) / (median of |
| 2 | 75 | MATCH (string) | RTX 5070 Ti, stock prefetcher, Stencil-24K: D(t) = 1 - (median demand faults of C7W512) / (median of |
| 2 | 0.0215 | MATCH (string) | RTX 5070 Ti, stock prefetcher, Stencil-24K: D(t) = 1 - (median demand faults of C7W512) / (median of |
| 2 | 100 | MATCH (string) | RTX 5070 Ti, stock prefetcher, Stencil-24K: D(t) = 1 - (median demand faults of C7W512) / (median of |
| 3 | 5070 | MATCH (string) | RTX 5070 Ti, E3a-2 module, Stencil-24K, prefetcher on: process wall-clock and demand faults of C0 (s |
| 3 | 24 | MATCH (string) | RTX 5070 Ti, E3a-2 module, Stencil-24K, prefetcher on: process wall-clock and demand faults of C0 (s |
| 3 | 512 | MATCH (string) | RTX 5070 Ti, E3a-2 module, Stencil-24K, prefetcher on: process wall-clock and demand faults of C0 (s |
| 3 | 1.0262 | MATCH (string) | RTX 5070 Ti, E3a-2 module, Stencil-24K, prefetcher on: process wall-clock and demand faults of C0 (s |
| 3 | 1.1298 | MATCH (string) | RTX 5070 Ti, E3a-2 module, Stencil-24K, prefetcher on: process wall-clock and demand faults of C0 (s |
| 3 | 51 | MATCH (string) | RTX 5070 Ti, E3a-2 module, Stencil-24K, prefetcher on: process wall-clock and demand faults of C0 (s |
| 3 | 51 | MATCH (string) | RTX 5070 Ti, E3a-2 module, Stencil-24K, prefetcher on: process wall-clock and demand faults of C0 (s |
| 3 | 1.0918 | MATCH (string) | RTX 5070 Ti, E3a-2 module, Stencil-24K, prefetcher on: process wall-clock and demand faults of C0 (s |
| 4 | 595.91 | MATCH (string) | Stock driver 595.91.07, prefetcher on, no speculation: wall-clock change of threshold 0 and 25 again |
| 4 | 25 | MATCH (string) | Stock driver 595.91.07, prefetcher on, no speculation: wall-clock change of threshold 0 and 25 again |
| 4 | 51 | MATCH (string) | Stock driver 595.91.07, prefetcher on, no speculation: wall-clock change of threshold 0 and 25 again |
| 4 | 5070 | MATCH (string) | Stock driver 595.91.07, prefetcher on, no speculation: wall-clock change of threshold 0 and 25 again |
| 4 | 24 | MATCH (string) | Stock driver 595.91.07, prefetcher on, no speculation: wall-clock change of threshold 0 and 25 again |
| 4 | 24 | MATCH (string) | Stock driver 595.91.07, prefetcher on, no speculation: wall-clock change of threshold 0 and 25 again |
| 4 | 9.57 | MATCH (string) | Stock driver 595.91.07, prefetcher on, no speculation: wall-clock change of threshold 0 and 25 again |
| 5 | 5070 | MATCH (string) | RTX 5070 Ti, stock driver, synthetic sparse-access benchmark: wall-clock change of threshold 0 and 2 |
| 5 | 25 | MATCH (string) | RTX 5070 Ti, stock driver, synthetic sparse-access benchmark: wall-clock change of threshold 0 and 2 |
| 5 | 51 | MATCH (string) | RTX 5070 Ti, stock driver, synthetic sparse-access benchmark: wall-clock change of threshold 0 and 2 |
| 5 | 1.5x | MATCH (rounded) | RTX 5070 Ti, stock driver, synthetic sparse-access benchmark: wall-clock change of threshold 0 and 2 |
| 5 | 3.95 | MATCH (string) | RTX 5070 Ti, stock driver, synthetic sparse-access benchmark: wall-clock change of threshold 0 and 2 |
| 6 | 5070 | MATCH (string) | RTX 5070 Ti, stock driver, nsys-traced runs: unified-memory bytes migrated host to device and device |
| 6 | 51 | MATCH (string) | RTX 5070 Ti, stock driver, nsys-traced runs: unified-memory bytes migrated host to device and device |
| 6 | 24 | MATCH (string) | RTX 5070 Ti, stock driver, nsys-traced runs: unified-memory bytes migrated host to device and device |
| 6 | 129.8 | MATCH (rounded) | RTX 5070 Ti, stock driver, nsys-traced runs: unified-memory bytes migrated host to device and device |
| 6 | 114.6 | MATCH (rounded) | RTX 5070 Ti, stock driver, nsys-traced runs: unified-memory bytes migrated host to device and device |
| 6 | 4.0 | MATCH (rounded) | RTX 5070 Ti, stock driver, nsys-traced runs: unified-memory bytes migrated host to device and device |
| 6 | 3.5 | MATCH (rounded) | RTX 5070 Ti, stock driver, nsys-traced runs: unified-memory bytes migrated host to device and device |
| 6 | 51 | MATCH (string) | RTX 5070 Ti, stock driver, nsys-traced runs: unified-memory bytes migrated host to device and device |
| 7 | 5070 | MATCH (string) | RTX 5070 Ti, Stencil-24K, prefetcher off, E1 Part B: median time per run spent in each phase of the  |
| 7 | 24 | MATCH (string) | RTX 5070 Ti, Stencil-24K, prefetcher off, E1 Part B: median time per run spent in each phase of the  |
| 7 | 1.595 | MATCH (rounded) | RTX 5070 Ti, Stencil-24K, prefetcher off, E1 Part B: median time per run spent in each phase of the  |
| 7 | 0.914 | MATCH (rounded) | RTX 5070 Ti, Stencil-24K, prefetcher off, E1 Part B: median time per run spent in each phase of the  |
| 7 | 4096 | MATCH (string) | RTX 5070 Ti, Stencil-24K, prefetcher off, E1 Part B: median time per run spent in each phase of the  |
| 8 | 5070 | MATCH (string) | RTX 5070 Ti, stock driver, 8 GiB array in memory. (a) Wall-clock change of threshold 0 against 51 on |
| 8 | 51 | MATCH (string) | RTX 5070 Ti, stock driver, 8 GiB array in memory. (a) Wall-clock change of threshold 0 against 51 on |
| 8 | 20 | MATCH (string) | RTX 5070 Ti, stock driver, 8 GiB array in memory. (a) Wall-clock change of threshold 0 against 51 on |
| 9 | 5070 | MATCH (string) | RTX 5070 Ti, stock driver, 8 GiB array in memory: wall-clock change of threshold 0 against 51 on man |
| 9 | 51 | MATCH (string) | RTX 5070 Ti, stock driver, 8 GiB array in memory: wall-clock change of threshold 0 against 51 on man |
| 9 | 20 | MATCH (string) | RTX 5070 Ti, stock driver, 8 GiB array in memory: wall-clock change of threshold 0 against 51 on man |
| 10 | 5070 | MATCH (string) | RTX 5070 Ti, stock driver, 8 GiB array in memory: fraction of the array made resident (panel (b) of  |
| 10 | 512 | MATCH (string) | RTX 5070 Ti, stock driver, 8 GiB array in memory: fraction of the array made resident (panel (b) of  |
| 10 | 31 | MATCH (string) | RTX 5070 Ti, stock driver, 8 GiB array in memory: fraction of the array made resident (panel (b) of  |
| 11 | 5070 | MATCH (string) | RTX 5070 Ti, stock driver, system-allocated (HMM, malloc) memory, H1 Amendment 1: wall-clock of thre |
| 11 | 51 | MATCH (string) | RTX 5070 Ti, stock driver, system-allocated (HMM, malloc) memory, H1 Amendment 1: wall-clock of thre |
| 11 | 24 | MATCH (string) | RTX 5070 Ti, stock driver, system-allocated (HMM, malloc) memory, H1 Amendment 1: wall-clock of thre |
| 11 | 512 | MATCH (string) | RTX 5070 Ti, stock driver, system-allocated (HMM, malloc) memory, H1 Amendment 1: wall-clock of thre |
| 11 | 200.52 | MATCH (string) | RTX 5070 Ti, stock driver, system-allocated (HMM, malloc) memory, H1 Amendment 1: wall-clock of thre |

Not matched in RESULTS_FACTS: 0 (of which NOT FOUND anywhere: 0).

