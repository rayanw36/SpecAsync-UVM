# C25: replacements and caption changes in the supplement (for review)

## S3 table replacements (entry, field, old -> new)

- #1 how caught: `independent re-investigation (Gate B)` -> `independent re-investigation (an earlier gate)`
- #2 how caught: `independent re-investigation (Gate B)` -> `independent re-investigation (an earlier gate)`
- #5 how caught: `same-session accounting-closure check` -> `same-run accounting-closure check`
- #6 how caught: `reproduction (Task T2)` -> `reproduction`
- #10 how caught: `pre-registered test (A2b)` -> `pre-registered test`
- #13 how caught: `independent source audit (E0)` -> `independent source audit (an earlier gate)`
- #15 how caught: `independent pass (E0.5)` -> `independent pass (an earlier gate)`
- #16 how caught: `independent pass (E0.5)` -> `independent pass (an earlier gate)`
- #17 how caught: `independent analysis-only pass (E0.8)` -> `independent analysis-only pass (an earlier gate)`
- #19 how caught: `independent source audit (E0)` -> `independent source audit (an earlier gate)`
- #23 false conclusion: `Older-driver and Gate-E results are one platform; the platform table is current.` -> `Results from an earlier driver release and from the later gates were read as one platform; the platform table was assumed current.`
- #29 how caught: `the session ended` -> `the run ended`

## S1/S2 caption changes

### S1 t_e4
- before: E4, RTX 5070 Ti, E3a-2 module: wall-clock of each speculation arm against C0 (the shipped driver) on Stencil-24K and GraphBFS-23, family F1 (prefetcher on) and the F4 row (perfect staging, prefetcher off). Two-sided Mann-Whitney U, one Holm family of 18, n = 10 per cell. The MDE is at the family alpha, alpha/18.
- after: E4, RTX 5070 Ti, our modified module: wall-clock of each speculation arm against C0 (the shipped driver) on Stencil-24K and GraphBFS-23, family F1 (prefetcher on) and the F4 row (perfect staging, prefetcher off). Two-sided Mann-Whitney U, one Holm family of 18, n = 10 per cell. The MDE is at the family alpha, alpha/18.

### S1 t_e6
- before: E6, Stencil-24K, RTX 5070 Ti: C7W512 at the shipped threshold against C0 at thresholds 0, 10, 25 and 51 (Holm family of 4), and C7W512 against C0 at the same threshold on wall-clock and on demand faults (two Holm families of 3). n = 10 per cell. MDEs are at the family alpha, rescaled from the achieved-n value because the CSV column is the 0.05/16 constant.
- after: E6, Stencil-24K, RTX 5070 Ti: C7W512 at the shipped threshold against C0 at thresholds 0, 10, 25 and 51 (Holm family of 4), and C7W512 against C0 at the same threshold on wall-clock and on demand faults (two Holm families of 3). n = 10 per cell. MDEs are computed at each family's own corrected level.

### S1 t_e9b
- before: Second fragment of T-E9: for the untraced E8 runs, the threshold-0 change in wall-clock, in time outside the kernels and in kernel time, and the share of the wall-clock change that lies outside the kernels (a negative share means the slowdown is entirely in the kernels).
- after: Companion to the preceding table: for the untraced E8 runs, the threshold-0 change in wall-clock, in time outside the kernels and in kernel time, and the share of the wall-clock change that lies outside the kernels (a negative share means the slowdown is entirely in the kernels).
