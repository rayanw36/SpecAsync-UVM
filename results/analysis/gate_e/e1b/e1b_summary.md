| workload | arm | n | enqueue_overhead total (s) | per prediction (ns) | per enqueued (ns) | pre-lock segment (s) | outside-lock svc − D3 − D4 (s) | post-lock remainder (s) | ft_predictions | enqueued | demand faults |
|---|---|---|---|---|---|---|---|---|---|---|---|
| stencil | C1 | 3 | 0.0000 | nan | nan | 0.0070 | 0.0117 | 0.0048 | 0 | 0 | 2931773 |
| stencil | C64096 | 3 | 0.0606 | 54 | 66 | 0.4847 | 0.4898 | 0.0051 | 1124999 | 916440 | 2990841 |
| stencil | C0 | 3 | 0.0000 | nan | nan | 0.0007 | 0.0011 | 0.0004 | 0 | 0 | 335489 |
| stencil | C74096 | 3 | 0.0249 | 75 | 75 | 0.0811 | 0.0815 | 0.0004 | 334330 | 334330 | 334330 |
| graphbfs | C1 | 2 | 0.0000 | nan | nan | 0.0014 | 0.0030 | 0.0015 | 0 | 0 | 490265 |
| graphbfs | C64096 | 2 | 0.0088 | 114 | 115 | 0.0913 | 0.0929 | 0.0017 | 77180 | 76895 | 485028 |

| pair | Δ outside-lock (s) | Δ enqueue_overhead (s) | enqueue ÷ Δ outside | Δ pre-lock (s) | pre-lock ÷ Δ outside | Δ pre-lock − Δ enqueue = predict/lookup (s) | per demand fault in speculative arm (ns) | Δ post-lock (s) |
|---|---|---|---|---|---|---|---|---|
| stencil C64096 − C1 | +0.4780 | +0.0606 | 12.7% | +0.4777 | 99.9% | +0.4171 | 139 | +0.0003 |
| stencil C74096 − C0 | +0.0805 | +0.0249 | 31.0% | +0.0804 | 100.0% | +0.0555 | 166 | +0.0000 |
| graphbfs C64096 − C1 | +0.0900 | +0.0088 | 9.8% | +0.0898 | 99.9% | +0.0810 | 167 | +0.0001 |
