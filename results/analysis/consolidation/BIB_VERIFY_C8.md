# Bibliography verification against the Crossref registry (Gate C8 phase 7)

`paper/ref.bib` was **not edited**. Each UNVERIFIED entry was looked up by DOI (if it has one) or by title; a record counts only if its title matches (ratio >= 0.9, or the registry title is a prefix of the bib title; two entries were queried under their full/expanded titles, see `ALT` in the script). Nothing was guessed. Registry = `api.crossref.org`, plain GET requests, no credentials or email sent.

| key | field | bib value | registry value | proposed fix |
|---|---|---|---|---|
| allen2024finegrain | pages | (absent) | 1-24 | add `pages = {1-24}` |
| allen2024finegrain | doi | (absent) | 10.1145/3632953 | add `doi = {10.1145/3632953}` |
| allen2024finegrain | authors | Allen and Cooper and Ge | Allen, Tyler; Cooper, Bennett; Ge, Rong | replace with the registry list if it is complete |
| bastemTilesTR | year | n.d. | 2017 | replace `year = {2017}` |
| bastemTilesTR | pages | (absent) | 171-180 | add `pages = {171-180}` |
| bastemTilesTR | venue | (absent) | 2017 46th International Conference on Parallel Processing (ICPP) | add `venue = {2017 46th International Conference on Parallel Processing (ICPP)}` |
| bastemTilesTR | doi | (absent) | 10.1109/icpp.2017.26 | add `doi = {10.1109/icpp.2017.26}` |
| bastemTilesTR | authors | Bastem and Unat and Zhang and Almgren and Shalf | Bastem, Burak; Unat, Didem; Zhang, Weiqun; Almgren, Ann; Shalf, John | replace with the registry list if it is complete |
| wahlgren2025mi300a | pages | (absent) | 368-380 | add `pages = {368-380}` |
| wahlgren2025mi300a | doi | (absent) | 10.1109/iiswc66894.2025.00038 | add `doi = {10.1109/iiswc66894.2025.00038}` |
| wahlgren2025mi300a | authors | Wahlgren, Jacob and others | Wahlgren, Jacob; Schieffer, Gabin; Shi, Ruimin; León, Edgar A.; Pearce, Roger; Gokhale, Maya; Peng, Ivy | replace with the registry list if it is complete |
| cooper2024svm | pages | 26--37 | 26-37 | replace `pages = {26-37}` |
| cooper2024svm | authors | Cooper, Bennett and Scogland, Thomas R. W. and Ge, Rong | Cooper, Bennett; Scogland, Thomas RW; Ge, Rong | replace with the registry list if it is complete |
| guo2025ghost | pages | (absent) | 899-914 | add `pages = {899-914}` |
| guo2025ghost | doi | (absent) | 10.1145/3725843.3756106 | add `doi = {10.1145/3725843.3756106}` |
| guo2025ghost | authors | Guo, Yuxin and others | Guo, Yuxin; Bhosale, Akshay; Bora, Utpal; Chadwick, Alexandra W.; Erdős, Márton; Gabrielli, Giacomo; Jones, Timothy M. | replace with the registry list if it is complete |
| han2026agio | pages | (absent) | 208-222 | add `pages = {208-222}` |
| han2026agio | doi | (absent) | 10.1145/3779212.3790130 | add `doi = {10.1145/3779212.3790130}` |
| han2026agio | authors | Han, Jihoon and others | Han, Jihoon; Sivasubramaniam, Anand; Chang, Chia-Hao; Mailthody, Vikram Sharma; Qureshi, Zaid; Hwu, Wen-Mei | replace with the registry list if it is complete |
| wang2025rmax | volume | (absent) | 24 | add `volume = {24}` |
| wang2025rmax | number | (absent) | 2 | add `number = {2}` |
| wang2025rmax | pages | (absent) | 293-296 | add `pages = {293-296}` |
| wang2025rmax | doi | (absent) | 10.1109/lca.2025.3611316 | add `doi = {10.1109/lca.2025.3611316}` |
| wang2025rmax | authors | Wang, Lei and others | Wang, Lei; Lee, Chia-Hang; Merrell, Maccoy; Chacon, Gino; Jiménez, Daniel A.; Gratz, Paul V. | replace with the registry list if it is complete |
| vanderkouwe2019sok | pages | (absent) | 310-325 | add `pages = {310-325}` |
| vanderkouwe2019sok | doi | (absent) | 10.1109/eurosp.2019.00031 | add `doi = {10.1109/eurosp.2019.00031}` |
| vanderkouwe2019sok | authors | van der Kouwe, Erik and Heiser, Gernot and Andriesse, Dennis and Bos, Herbert and Giuffrida, Cristiano | van der Kouwe, Erik; Heiser, Gernot; Andriesse, Dennis; Bos, Herbert; Giuffrida, Cristiano | replace with the registry list if it is complete |
| papadopoulos2019principles | year | 2019 | 2021 | replace `year = {2021}` |
| papadopoulos2019principles | volume | (absent) | 47 | add `volume = {47}` |
| papadopoulos2019principles | number | (absent) | 8 | add `number = {8}` |
| papadopoulos2019principles | pages | (absent) | 1528-1543 | add `pages = {1528-1543}` |
| papadopoulos2019principles | doi | (absent) | 10.1109/tse.2019.2927908 | add `doi = {10.1109/tse.2019.2927908}` |
| papadopoulos2019principles | authors | Papadopoulos, Alessandro V. and others | Papadopoulos, Alessandro Vittorio; Versluis, Laurens; Bauer, Andre; Herbst, Nikolas; Kistowski, Joakim von; Ali-Eldin, Ahmed; Abad, Cristina L.; Amaral, Jose Nelson; Tuma, Petr; Iosup, Alexandru | replace with the registry list if it is complete |
| raasveldt2018fair | pages | (absent) | 1-6 | add `pages = {1-6}` |
| raasveldt2018fair | doi | (absent) | 10.1145/3209950.3209955 | add `doi = {10.1145/3209950.3209955}` |
| raasveldt2018fair | authors | Raasveldt, Mark and Holanda, Pedro and Gubner, Tim and M\"uhleisen, Hannes | Raasveldt, Mark; Holanda, Pedro; Gubner, Tim; Mühleisen, Hannes | replace with the registry list if it is complete |
| li2025pipelining | pages | 1--26 | 1-26 | replace `pages = {1-26}` |
| li2025pipelining | authors | Li, Ruihao and Hanindhito, Bagus and Yadav, Shalini and Wu, Qijun and Kavi, Krishna and Mehta, Gayatri and Yadwadkar, Neeraja and John, Lizy | Li, Ruihao; Hanindhito, Bagus; Yadav, Sanjana; Wu, Qinzhe; Kavi, Krishna; Mehta, Gayatri; Yadwadkar, Neeraja J.; John, Lizy K. | replace with the registry list if it is complete |

## allen2024finegrain

The registry gives **year 2024** (venue `ACM Transactions on Architecture and Code Optimization`, volume 21, issue 1, DOI 10.1145/3632953); ref.bib has year 2024 (key `allen2024finegrain`).

## Notes for the reviewer
- **Outcome:** the registry was reachable (no block); all 10 entries with an UNVERIFIED note, and `allen2024finegrain`, matched a Crossref record (two only under an expanded or subtitle-free query title, see `ALT` in `tests/c8_bib_verify.py`). The registry lists **complete author lists** for every entry that has "and others"; the table lists them, nothing was applied.
- **`allen2024finegrain`:** registry year equals the bib year (2024; issued 2024-01-18, TACO volume 21 issue 1). The 2023 date that the bib comment attributes to another index is not what the registry gives.
- **`papadopoulos2019principles`:** the bib year (2019) is the first-online year; the registry record's year is the issue year of the journal volume. Choose one convention for all entries; the DOI is unambiguous.
- **`bastemTilesTR`:** the bib type is a technical report with no year; the registry record is the conference paper of the same title at ICPP. Confirm that the paper cites the conference version before adding its fields.
- **`raasveldt2018fair`:** the registry title omits the subtitle ("Common Pitfalls in DBMS Performance Testing"); keep the bib subtitle if that is the printed title.
- Fields marked "replace `pages = {26-37}`" for `cooper2024svm` and `li2025pipelining` differ only in the dash style (`--` vs `-`), not in value.
