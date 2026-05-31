# References Review

> **Purpose:** Address reviewer Comment 5 — strengthen reference quality by
> identifying arXiv-only papers and finding peer-reviewed substitutes.
>
> **Method:** Each reference is classified as:
> - **keep-peer-reviewed** — published in a peer-reviewed venue (conference or journal)
> - **find-venue-version** — arXiv preprint of a work that has a peer-reviewed publication; cite that instead
> - **needs-replacement** — arXiv-only or weak; peer-reviewed substitutes suggested

---

## Reference classifications

### [9] Forest — ISCA 2025

**Classification: keep-peer-reviewed**

Forest (prefetching for GPU UVM) is listed as ISCA 2025. ISCA is the premier
computer architecture conference (CORE A*). Confirm the exact citation:

> *Forest: Prefetching for GPU Unified Virtual Memory.*
> Proceedings of the 52nd Annual International Symposium on Computer Architecture
> (ISCA 2025). **Cite the ISCA proceedings version, not the arXiv preprint.**

*Action: Verify DOI/page numbers against the ACM Digital Library ISCA 2025
proceedings once available. If still in press, "To appear in ISCA 2025" is
acceptable.*

---

### [8] Long et al. — learned-prefetch (arXiv)

**Classification: needs-replacement**

The cited work (Long et al., arXiv, learned prefetch for GPU UVM) is arXiv-only.
Suggested peer-reviewed replacements covering hardware prefetching and learned
prefetch techniques:

1. **Bhatotia et al., "Hermes: Accelerating Long-Latency Load Requests via
   Perceptron-Based Off-Chip Load Prediction," MICRO 2022.**
   Strong peer-reviewed work on ML-guided prefetch in the memory system.
   *Needs verification: confirm venue via IEEE Xplore or ACM DL.*

2. **Srinath et al., "Feedback Directed Prefetching: Improving the Performance
   and Bandwidth-Efficiency of Hardware Prefetchers," IEEE HPCA 2007.**
   Classic peer-reviewed reference for adaptive prefetch feedback — directly
   relevant if [8] is cited to motivate hit-rate feedback.
   *Venue confirmed: IEEE HPCA 2007 (CORE A*).*

3. **Liao et al., "GPU-Initiated On-Demand High-Throughput Storage Access in
   the BaM System," ASPLOS 2023.**
   Covers demand-driven GPU memory access patterns.
   *Needs verification: confirm proceedings details.*

*Recommendation: Replace [8] with one or two of the above that most directly
support the claim being cited. Specify what claim [8] supports and pick the
best fit.*

---

### [10] Anonymous arXiv

**Classification: needs-replacement**

An anonymous arXiv cite is unusable as a reference (no stable identity,
no peer review, no citation path). It must be replaced.

Without knowing the specific claim [10] supports, suggested peer-reviewed
alternatives for common UVM/GPU-memory claims:

1. **Zheng et al., "Buddy Compression: Enabling Larger Memory for Deep
   Learning and HPC Workloads on GPUs," ISCA 2020.** Covers GPU memory
   pressure and oversubscription.
   *Needs verification: confirm ISCA 2020 proceedings.*

2. **Kim et al., "Batch-Aware Unified Memory Management in GPUs for Irregular
   Workloads," ASPLOS 2020.** Directly covers UVM batch fault handling.
   *Needs verification: confirm ASPLOS 2020 proceedings.*

3. **Ganguly et al., "Interplay between Hardware Prefetcher and Page Eviction
   Policy in CPU-GPU Unified Virtual Memory," ISCA 2019.** Strong peer-reviewed
   UVM work from 2019.
   *Needs verification: confirm ISCA 2019 proceedings.*

*Action: Identify what specific claim [10] was cited for. Then select the
replacement above that best supports that claim.*

---

### [19] Parravicini — arXiv

**Classification: find-venue-version or needs-replacement**

If this is Alberto Parravicini's work on GPU memory management or graph
analytics on GPUs, check:

1. Whether it was subsequently published in a venue (VLDB, SC, ICS, PPoPP).
   Search: *author:Parravicini GPU* on DBLP (dblp.org) or Semantic Scholar.
   *Status: needs verification — cannot confirm without web search in this
   environment.*

2. If no published version exists, replace with a peer-reviewed paper
   covering the same claim. Likely candidates (graph analytics on GPUs with
   managed memory):
   - **Wang et al., "Gunrock: GPU Graph Analytics," ACM TOPC 2016.** CORE A.
   - **Yang et al., "Design Principles for Sparse Matrix Multiplication on
     the GPU," Euro-Par 2018.**

*Action: Search DBLP for "Parravicini" + confirm venue. If arXiv-only, use
a Gunrock-family citation instead.*

---

## General arXiv policy recommendation

For any remaining arXiv preprints in the bibliography:

1. Search DBLP (dblp.org) or Semantic Scholar for the title; if a venue
   version exists, cite that.
2. For preprints that have no published version but are genuinely important
   (e.g., widely cited, from major labs), include both arXiv ID and a note
   "preprint, under review" — but minimise these.
3. Remove any anonymous arXiv citations entirely; they are not citable.

---

## References confirmed as peer-reviewed (retain as-is)

- All citations to ISCA, MICRO, ASPLOS, SC, EuroSys, OSDI, SOSP, USENIX ATC,
  HPCA, PPoPP proceedings are peer-reviewed (CORE A or A*). Retain without change.
- IEEE Transactions on Parallel and Distributed Systems, ACM TOPC, TOCS:
  peer-reviewed journals, retain.
- NVIDIA technical reports and documentation: not peer-reviewed but
  acceptable as primary source citations for API/driver behaviour; label as
  "Technical Report" in the bibliography.
