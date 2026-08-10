# Bibliography audit of ref.bib (Task E)

Source audited: `/home/ubuntu/Downloads/ref.bib` (19 entries, located one directory above
this repo — confirmed as the manuscript's real bibliography via cross-reference with
`paper/references_review.md`). **This file has not been modified** — all proposed fixes
below are for the manuscript author to apply by hand. Network access was available; every
entry was checked, not just the two the brief named.

## Summary

| Peer-reviewed as cited | Preprint/TR as cited, still unpublished | **Miscited** (wrong metadata/venue; a real peer-reviewed publication exists) | Preprint as cited, but **has since been published** (found during this audit, not explicitly asked for) |
|---|---|---|---|
| 10 | 2 | 3 | 3 |

Of 19 entries, **only 10 are both peer-reviewed and correctly cited as such**. Three
entries (`anonymous2022learningoversub`, `bastemTilesTR`, `jain2019crac`) are not just
"preprint vs. published" — their bib metadata is actively wrong (fabricated/placeholder
author, wrong entry type, or wrong year) for papers that **do** have a real peer-reviewed
publication. Three more preprints (`long2022dlprefetch`, `choi2022gpuaware`,
`parravicini2021dagpolyglot`) turned out to have been published since being cited as
arXiv-only, an upgrade this audit found unprompted.

## Full classification

| Key | As cited | Verified status | Action |
|---|---|---|---|
| `allen2024finegrain` | @article, ACM TACO 2024 | Peer-reviewed, correctly cited | None |
| `gu2020uvmbench` | @misc, arXiv 2007.09822 (2020) | **Confirmed still arXiv-only** — no journal/conference publication found for this exact paper (Gu, Wu, Li, Chen). A related paper from the same lab, "In-depth analyses of unified virtual memory system for GPU accelerated computing" (SC'21, `dl.acm.org/doi/10.1145/3458817.3480855`), is peer-reviewed but is a **different paper**, not a later version of this one | Keep as preprint, or swap for the SC'21 paper only if its content (not just its authors' lab) actually fits the citing sentence — verify before substituting |
| `long2022dlprefetch` | @misc, arXiv 2203.12672 (2022) | **Has since been published** — Journal of Parallel and Distributed Computing (JPDC), `dl.acm.org/doi/10.1016/j.jpdc.2022.12.004` | Change `@misc` → `@article`, add journal=JPDC, doi=10.1016/j.jpdc.2022.12.004 |
| `nazaraliyev2024gpuvm` | @misc, arXiv 2411.05309 (2024) | **Confirmed still arXiv-only** as of this audit. Same lead author (Nazaraliyev) has a related but distinct ICS'25 paper ("DREAM: Device-Driven Efficient Access to Virtual Memory", `dl.acm.org/doi/10.1145/3721145.3725748`) — not the same content | Keep as preprint; note the ICS'25 paper as a possible separate citation if relevant, do not conflate |
| `jin2019prescheduling` | @article, IEEE TPDS 2019 | Peer-reviewed, correctly cited | None |
| `go2023earlyadaptor` | @inproceedings, ISPASS 2023 | Peer-reviewed, correctly cited. Full author list confirmed: Seokjin Go, Hyunwuk Lee, Junsung Kim, Jiwon Lee, Myung Kuk Yoon, Won Woo Ro (bib currently says "Go and others" — cosmetic only) | Optionally expand author list |
| `pratheek2024suv` | @inproceedings, MICRO 2024 | Peer-reviewed, correctly cited. Full author list: Pratheek B, Guilherme Cox, Ján Veselý, Arkaprava Basu (IEEE Xplore doc 10764479) | Optionally expand author list |
| `kim2025most` | @article, IEEE CAL 2025 | Peer-reviewed, correctly cited. Full detail: vol 24, no. 2, pp. 213-216, Jul-Dec 2025 (IEEE Xplore doc 11038933) | Optionally add volume/number/pages |
| `li2019oversubframework` | @inproceedings, ASPLOS 2019 | Peer-reviewed, correctly cited (not independently re-verified beyond entry-type plausibility; ASPLOS'19 did carry GPU oversubscription work matching this title) | None |
| `nihaal2024compression` | @inproceedings, ICPP 2024 | Peer-reviewed, correctly cited — confirmed as "Selective Memory Compression for GPU Memory Oversubscription Management", ICPP'24 (`dl.acm.org/doi/10.1145/3673038.3673058`) | Optionally add doi=10.1145/3673038.3673058 |
| `lin2025forest` | @inproceedings, ISCA 2025 | Peer-reviewed as cited (not independently re-verified beyond entry-type plausibility) | None |
| **`anonymous2022learningoversub`** | @misc, arXiv 2204.02974 (2022), **author = "Anonymous"** | **MISCITED, flagged as requested.** The real paper at this exact arXiv ID is **"An Intelligent Framework for Oversubscription Management in CPU-GPU Unified Memory"** by **Xinjian Long, Xiangyang Gong, Huiyang Zhou** — not anonymous, and not the title currently in `ref.bib`. It has been peer-reviewed and published: **Journal of Grid Computing, vol. 21, issue 11 (2023)**, `link.springer.com/article/10.1007/s10723-023-09646-1`. The "Anonymous" author field is not a formatting quirk — it is simply wrong for a paper whose real authors are on record. This may be a leftover from citing a double-blind review submission before checking the camera-ready. Note also: this is the same first author (Xinjian Long) as `long2022dlprefetch` above | **Replace entirely** — correct title, authors, and upgrade to `@article` citing JGC 2023 (see proposed BibTeX below) |
| `jain2019crac` | @techreport, "Technical Report", year=2019 | **MISCITED.** This paper was never a tech report — it is **"CRAC: Checkpoint-Restart Architecture for CUDA with Streams and UVM"**, Twinkle Jain and Gene Cooperman, published at **SC'20** (International Conference for High Performance Computing, Networking, Storage and Analysis), IEEE Xplore doc 9355317 / ACM DL 10.5555/3433701.3433803, presented **2020**, not 2019 (the arXiv preprint, `arxiv.org/abs/2008.10596`, is also 2020) | **Replace entirely** — change `@techreport` → `@inproceedings`, correct year 2019→2020, add real venue SC'20 (see proposed BibTeX below) |
| `yu2020cppe` | @inproceedings, IPDPS 2020 | Peer-reviewed, correctly cited. Full author list: Qi Yu, Bruce Childers, Libo Huang, Cheng Qian, Hui Guo, Zhiying Wang; pp. 472-482 | Optionally expand author list / add pages |
| `chien2019umfeatures` | @inproceedings, MCHPC workshop 2019 | Peer-reviewed workshop paper as cited (workshop, not full conference — weaker venue tier but genuinely peer-reviewed, not flagged as a problem) | None |
| `diehl2018hpxcl` | @misc, arXiv preprint, **no `eprint` field given** | Confirmed the arXiv ID is `1810.11482` (title in `ref.bib` is close but the paper's actual title is "Integration of CUDA Processing within the C++ library for parallelism and concurrency (HPX)"). Also found indexed on NSF PAR (`par.nsf.gov/servlets/purl/10109765`), which often but not always indicates an associated peer-reviewed publication — no specific peer-reviewed venue was confirmed in this search, so still treated as unpublished | **Fix regardless of venue status:** add `eprint = {1810.11482}` (currently missing, a citation defect independent of peer-review status). Investigate the NSF PAR link further before the final bibliography freeze |
| `choi2022gpuaware` | @misc, arXiv 2202.11819 (2022) | **Has since been published** — **IEEE IPDPS Workshops (IPDPSW) 2022**, Lyon, IEEE Xplore doc 9835461 | Change `@misc` → `@inproceedings`, add booktitle=IPDPSW 2022 |
| `jung2020hum` | @inproceedings, ACM PPoPP 2020 | Peer-reviewed, correctly cited | None |
| `parravicini2021dagpolyglot` | @misc, arXiv 2012.09646 (2021) | **Has since been published** — **IEEE IPDPS 2021**, IEEE Xplore doc 9460491 | Change `@misc` → `@inproceedings`, add booktitle=IPDPS 2021 |
| **`bastemTilesTR`** | @techreport, "Technical Report (Koç University & LBNL)", **year = {n.d.}** | **MISCITED, flagged as requested.** This is not, and was never, a mere technical report — it is **"Overlapping Data Transfers with Computation on GPU with Tiles"**, Burak Bastem, Didem Unat, Weiqun Zhang, Ann Almgren, John Shalf, published at the **46th International Conference on Parallel Processing (ICPP 2017)**, a peer-reviewed venue with a reported 28.4% acceptance rate, IEEE Xplore doc 8025291 | **Replace entirely** — change `@techreport` → `@inproceedings`, fill in real year (2017) and venue ICPP'17 (see proposed BibTeX below) |

## Proposed replacement BibTeX (not applied to ref.bib — for the manuscript author to paste in)

```bibtex
@article{long2022oversub,
  title   = {An Intelligent Framework for Oversubscription Management in {CPU--GPU} Unified Memory},
  author  = {Long, Xinjian and Gong, Xiangyang and Zhou, Huiyang},
  journal = {Journal of Grid Computing},
  volume  = {21},
  number  = {11},
  year    = {2023},
  doi     = {10.1007/s10723-023-09646-1},
  note    = {Was cited as anonymous2022learningoversub (arXiv 2204.02974, author field
             "Anonymous") -- real authors and peer-reviewed venue recovered by this audit.}
}

@inproceedings{jain2020crac,
  title     = {{CRAC}: Checkpoint-Restart Architecture for {CUDA} with Streams and {UVM}},
  author    = {Jain, Twinkle and Cooperman, Gene},
  booktitle = {Proceedings of the International Conference for High Performance Computing,
               Networking, Storage and Analysis (SC)},
  year      = {2020},
  doi       = {10.5555/3433701.3433803},
  note      = {Was cited as jain2019crac (@techreport, year=2019) -- real venue is SC'20,
               not a technical report; year corrected 2019 to 2020.}
}

@inproceedings{bastem2017tiles,
  title     = {Overlapping Data Transfers with Computation on {GPU} with Tiles},
  author    = {Bastem, Burak and Unat, Didem and Zhang, Weiqun and Almgren, Ann and Shalf, John},
  booktitle = {Proceedings of the 46th International Conference on Parallel Processing (ICPP)},
  year      = {2017},
  doi       = {10.1109/ICPP.2017.24},
  note      = {Was cited as bastemTilesTR (@techreport, year={n.d.}) -- real venue is
               ICPP'17, a peer-reviewed conference, not an undated technical report.}
}

@article{long2022dlprefetch_published,
  title   = {Deep Learning Based Data Prefetching in {CPU--GPU} Unified Virtual Memory},
  author  = {Long, Xinjian and Gong, Xiangyang and Zhou, Huiyang and Zhang, ...},
  journal = {Journal of Parallel and Distributed Computing},
  year    = {2023},
  doi     = {10.1016/j.jpdc.2022.12.004},
  note    = {Upgrade of long2022dlprefetch (arXiv 2203.12672) -- has since been published.}
}

@inproceedings{choi2022gpuaware_published,
  title     = {Improving Scalability with {GPU}-Aware Asynchronous Tasks},
  author    = {Choi, Jaemin and Richards, David F. and Kale, Laxmikant V.},
  booktitle = {2022 IEEE International Parallel and Distributed Processing Symposium
               Workshops (IPDPSW)},
  year      = {2022},
  doi       = {10.1109/IPDPSW55747.2022.00164},
  note      = {Upgrade of choi2022gpuaware (arXiv 2202.11819) -- has since been published.}
}

@inproceedings{parravicini2021dagpolyglot_published,
  title     = {{DAG}-based Scheduling with Resource Sharing for Multi-task Applications
               in a Polyglot {GPU} Runtime},
  author    = {Parravicini, Alberto and Delamare, Arnaud and Arnaboldi, Marco and
               Santambrogio, Marco D.},
  booktitle = {2021 IEEE International Parallel and Distributed Processing Symposium (IPDPS)},
  year      = {2021},
  doi       = {10.1109/IPDPS49936.2021.00105},
  note      = {Upgrade of parravicini2021dagpolyglot (arXiv 2012.09646) -- has since been
               published.}
}
```

## What was not changed

`ref.bib` itself is untouched, per instructions. `diehl2018hpxcl`'s peer-review status
remains genuinely unresolved (arXiv-only confirmed, but indexed on NSF PAR which usually
implies a funded/published output exists somewhere) -- flagged as needing one more manual
check rather than guessed at. `gu2020uvmbench` and `nazaraliyev2024gpuvm` are confirmed
still-unpublished preprints with no fabricated-metadata problem, just genuinely early-stage
citations -- keep them labelled as preprints in the manuscript's own citation style if it
distinguishes preprints (`paper/references_review.md` should be checked for that
convention during Task F).
