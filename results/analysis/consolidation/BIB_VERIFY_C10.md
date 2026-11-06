# bastem2017tiles DOI check (Gate C10 phase 1)

Crossref (`api.crossref.org/works/<doi>`), fetched 2026-11-06 13:46:

| DOI | title | authors (family) | container | pages |
|---|---|---|---|---|
| 10.1109/ICPP.2017.24 | MPI-GDS: High Performance MPI Designs with GPUDirect-aSync for CPU-GPU Control Flow Decoupling | Venkatesh, Hamidouche, Potluri, Rosetti, Chu, Panda | 2017 46th International Conference on Parallel Processing (ICPP) | 151-160 |
| 10.1109/ICPP.2017.26 | Overlapping Data Transfers with Computation on GPU with Tiles | Bastem, Unat, Zhang, Almgren, Shalf | 2017 46th International Conference on Parallel Processing (ICPP) | 171-180 |

**Result:** exactly one DOI matches the title "Overlapping Data Transfers with Computation on GPU with Tiles" (Bastem, Unat, Zhang, Almgren, Shalf, ICPP 2017): **10.1109/ICPP.2017.26**, pages 171-180. `10.1109/ICPP.2017.24` is a different paper (MPI-GDS, Venkatesh et al.), so the earlier DOI in `ref.bib` was wrong. `ref.bib` now has `doi = {10.1109/ICPP.2017.26}` (upper case) and `pages = {171--180}`. The C9 open item is closed.
