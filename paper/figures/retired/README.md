# Retired figures (Gate C8 phase 5; copies, originals untouched)

Per `paper/figures/EXISTING_FIGURES_ASSESSMENT.md` and `results/analysis/consolidation/SUPERSEDED_VALUES.md`. These are **copies**: the originals stay in `results/figures/` because `paper/main.tex` still references `oversub_collapse` (via `\graphicspath{{../results/figures/}}`) and the repository manifest lists them; moving them would break `main.tex`. Nothing here is referenced by `main_v2.tex`.

- `oversub_collapse.{pdf,png}` (F4): the oracle hit-rate collapse under oversubscription rests on the State-1 misaligned oracle and on `spec_hits` hit rates, both superseded (SV `main.tex:158-165`; catalog #1, #13, #20). Its role is taken by the E8 and E9 figures (`paper/figures/fig_e8_*`, `fig_e9_*`).
- `hitrate_vs_speedup.{pdf,png}` (F11): the x-axis is the `spec_hits` coincidence rate, which is not a measure of prediction success (catalog #20; CS2-N7). The "no relationship" point is made better by the demand-fault reduction D(t) in `fig_e5_threshold_dose_response`.
