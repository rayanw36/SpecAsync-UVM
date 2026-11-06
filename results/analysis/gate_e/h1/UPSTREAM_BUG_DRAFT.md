# DRAFT upstream bug report for NVIDIA/open-gpu-kernel-modules (NOT POSTED; do not post without the user's review)

Prepared 2026-11-06 13:52 (C10 phase 4). Read-only work: the crash was **not** reproduced and will not be. Format follows the repository's bug-report issue form as rendered in issue #1223 (the form's own file could not be fetched). Sections marked **USER** need the user.

## Title
`nvidia_uvm` 595.91.07: NULL dereference in `free_chunk` (kernel thread "vidmem lazy free") then soft lockup of the replayable-fault bottom half in `uvm_hmm_va_block_service_locked` under HMM oversubscription (RTX 5070 Ti, malloc'd 24 GiB on 16 GB)

### NVIDIA Open GPU Kernel Modules Version
Driver 595.91.07 open (Ubuntu apt `nvidia-dkms-595-open` 595.91.07-0ubuntu0.24.04.1; source checked identical to upstream tag 595.91.07: `uvm_pmm_gpu.c` has 0 differing lines).

### Please confirm this issue does not happen with the proprietary driver (of the same version)
**USER:** not tested (this host only runs the open module). The box must stay unchecked unless the user tests it.

### Operating System and Version
Ubuntu 24.04.5 LTS

### Kernel Release
Linux LinuxPC 7.0.0-34-generic #34~24.04.1-Ubuntu SMP PREEMPT_DYNAMIC Fri Sep  4 15:38:29 UTC 2 x86_64 x86_64 x86_64 GNU/Linux

### Please confirm you are running a stable release kernel
Stable Ubuntu kernel 7.0.0-34-generic (not an -rc). **USER** to tick.

### Hardware: GPU
NVIDIA GeForce RTX 5070 Ti, 16303 MiB, PCIe, driver 595.91.07; CUDA driver 13.2 / toolkit 13.0 (`h0_caps_output.txt`). Host: ASRock B850I Lightning WiFi, 60 GiB RAM (about 51 GiB free before the run).

### Environment details
- HMM active: `nvidia-smi -q` "Addressing Mode: HMM"; `cudaDevAttrPageableMemoryAccess = 1`, `PageableMemoryAccessUsesHostPageTables = 0`.
- UVM module parameters: defaults except `uvm_perf_prefetch_threshold=0` (and `uvm_perf_prefetch_enable=1`); `uvm_disable_hmm=N`, `uvm_ats_mode=1` (no ATS on this PCIe GPU), `uvm_enable_va_space_mm=1`.
- THP: `enabled=always [madvise] never`, `defrag=... [madvise] ...`; `numa_balancing=0`; the benchmark also calls `madvise(MADV_NOHUGEPAGE)`.
- Headless (`multi-user.target`), stock module only, nothing else using the GPU.

### Describe the bug
With HMM (a plain `aligned_alloc`'d array, 24 GiB, on a 16 GB GPU, i.e. 1.5x oversubscription), the first GPU kernel that touches it triggers a NULL pointer dereference in `free_chunk+0x4d` in the "vidmem lazy free" kernel thread. That thread dies "with irqs disabled / preempt_count 1" and the UVM replayable-fault bottom half then spins on a spin lock for >25 minutes (`soft lockup - CPU#2 stuck for 1527s`) in `uvm_pmm_gpu_unpin_allocated`, called from `sync_page_and_chunk_state` <- `uvm_hmm_va_block_service_locked`. The host does not recover; it had to be power-cycled.

Faulting instruction (module built for 7.0.0-34, `objdump` of `free_chunk`): `free_chunk+0x4d` = `cmp DWORD PTR [rax],0x1` after `mov rax,[rbx+0x28]` / `mov rax,[rax+0x30]`. With `struct uvm_gpu_chunk_struct` (address 0x0, bitfields 0x8, `list` 0x10, `va_block` 0x20, `parent` 0x28, `suballoc` 0x30) this is `chunk->parent->suballoc->allocated == 1` in `chunk_is_last_allocated_child()` (inlined into `try_chunk_free()`): `chunk->parent` is non-NULL but `chunk->parent->suballoc` is NULL. **Hypothesis, not verified:** `suballoc` is cleared to NULL when a parent chunk is merged (`uvm_pmm_gpu.c:815`), so a lazily freed child (`process_lazy_free` -> `free_chunk`) still pointed at a parent that had already been merged, a race between the HMM device-private chunk free path and PMM merge/eviction. Not confirmed with a debug build.

### To Reproduce
Stock `nvidia_uvm` 595.91.07, inserted with `uvm_perf_prefetch_enable=1 uvm_perf_prefetch_threshold=0`, then (the program is a small synthetic benchmark; source available on request):
```
setarch -R ./bench_sparse 24 1 3 202610081 --alloc malloc
# 24 GiB array allocated with aligned_alloc(2 MiB) + madvise(MADV_NOHUGEPAGE), every page written by the host,
# then 3 kernels touching 1 page (K=1) of each 2 MB block; 16 GB VRAM
```
(`bench_sparse` = `benchmarks/bench_sparse.cu` of the SpecAsync-UVM repository; `--alloc malloc` is the Gate H1 flag.) The same program with 8 GiB (in memory) and `--alloc malloc` ran without incident, as did Stencil-24K; with `cudaMallocManaged` at 24 GiB the same oversubscription ran in earlier experiments (Gate E8) without a crash.

### Bug Incidence
**Once** (not retried; retrying risks another host hang). Threshold 0 was the setting at the time; whether threshold 51 or other oversubscribed cells trigger it is unknown.

### nvidia-bug-report.log.gz
**USER:** `nvidia-bug-report.sh` must be run by the user. The crash boot's kernel log is no longer the current boot; capture it with `journalctl -k -b 46abc43f535443cebe6fe28fb6efc99b` (boot id of the crash boot; its journal ends 2026-11-05 22:17:01). Attach that output as well.

### Trace excerpt (from `results/analysis/gate_e/h1/h1_lockup_excerpt.txt`)
```
BUG: kernel NULL pointer dereference, address: 0000000000000000
#PF: supervisor read access in kernel mode
#PF: error_code(0x0000) - not-present page
PGD 0 P4D 0 
Oops: Oops: 0000 [#1] SMP NOPTI
CPU: 4 UID: 0 PID: 15722 Comm: vidmem lazy fre Tainted: G           OE       7.0.0-34-generic #34~24.04.1-Ubuntu PREEMPT(lazy) 
Tainted: [O]=OOT_MODULE, [E]=UNSIGNED_MODULE
Hardware name: ASRock B850I Lightning WiFi/B850I Lightning WiFi, BIOS 3.30 06/16/2025
RIP: 0010:free_chunk+0x4d/0xd0 [nvidia_uvm]
Code: 0f b6 6e 09 44 0f b6 76 08 41 d0 ed e8 cc 37 e1 c5 48 8b 43 28 80 63 08 f7 41 83 e5 1f 41 83 e6 03 48 85 c0 74 09 48 8b 40 30 <83> 38 01 74 2e 4c 89 e7 48 89 de e
RSP: 0018:ffffcf4e852f3dc0 EFLAGS: 00010282
RAX: 0000000000000000 RBX: ffff8d3dde156620 RCX: 0000000000000000
RDX: 0000000000000000 RSI: 0000000000000000 RDI: 0000000000000000
RBP: ffffcf4e852f3de8 R08: 0000000000000000 R09: 0000000000000000
R10: 0000000000000000 R11: 0000000000000000 R12: ffff8d3d872ef9f8
R13: 000000000000000c R14: 0000000000000000 R15: ffff8d3d872efae0
FS:  0000000000000000(0000) GS:ffff8d4a937e3000(0000) knlGS:0000000000000000
CS:  0010 DS: 0000 ES: 0000 CR0: 0000000080050033
CR2: 0000000000000000 CR3: 0000000160255000 CR4: 0000000000f50ef0
PKRU: 55555554
Call Trace:
 <TASK>
 process_lazy_free+0x6f/0xb0 [nvidia_uvm]
 process_lazy_free_entry+0x8f/0xb0 [nvidia_uvm]
 _main_loop+0x9c/0x170 [nvidia_uvm]
 ? __pfx__main_loop+0x10/0x10 [nvidia_uvm]
 kthread+0xfb/0x140
 ? __pfx_kthread+0x10/0x10
 ret_from_fork+0x1f8/0x2b0
 ? __pfx_kthread+0x10/0x10
 ret_from_fork_asm+0x1a/0x30
 </TASK>
Modules linked in: nvidia_uvm(OE) ccm rfcomm snd_seq_dummy snd_hrtimer qrtr cmac algif_hash algif_skcipher af_alg bnep binfmt_misc amd_atl intel_rapl_msr ntfs3 nls_iso8
 lp parport efi_pstore nfnetlink dmi_sysfs ip_tables x_tables autofs4 hid_logitech_hidpp hid_logitech_dj hid_multitouch hid_generic nvme usbhid hid r8169 nvme_core ahci
CR2: 0000000000000000
---[ end trace 0000000000000000 ]---
RIP: 0010:free_chunk+0x4d/0xd0 [nvidia_uvm]
Code: 0f b6 6e 09 44 0f b6 76 08 41 d0 ed e8 cc 37 e1 c5 48 8b 43 28 80 63 08 f7 41 83 e5 1f 41 83 e6 03 48 85 c0 74 09 48 8b 40 30 <83> 38 01 74 2e 4c 89 e7 48 89 de e
RSP: 0018:ffffcf4e852f3dc0 EFLAGS: 00010282
RAX: 0000000000000000 RBX: ffff8d3dde156620 RCX: 0000000000000000
RDX: 0000000000000000 RSI: 0000000000000000 RDI: 0000000000000000
RBP: ffffcf4e852f3de8 R08: 0000000000000000 R09: 0000000000000000
R10: 0000000000000000 R11: 0000000000000000 R12: ffff8d3d872ef9f8
R13: 000000000000000c R14: 0000000000000000 R15: ffff8d3d872efae0
FS:  0000000000000000(0000) GS:ffff8d4a937e3000(0000) knlGS:0000000000000000
CS:  0010 DS: 0000 ES: 0000 CR0: 0000000080050033
CR2: 0000000000000000 CR3: 000000096a444000 CR4: 0000000000f50ef0
PKRU: 55555554
note: vidmem lazy fre[15722] exited with irqs disabled
note: vidmem lazy fre[15722] exited with preempt_count 1
...
watchdog: BUG: soft lockup - CPU#2 stuck for 26s! [UVM GPU1 BH:15723]
Modules linked in: nvidia_uvm(OE) ccm rfcomm snd_seq_dummy snd_hrtimer qrtr cmac algif_hash algif_skcipher af_alg bnep binfmt_misc amd_atl intel_rapl_msr ntfs3 nls_iso8
...
watchdog: BUG: soft lockup - CPU#2 stuck for 52s! [UVM GPU1 BH:15723]
Modules linked in: nvidia_uvm(OE) ccm rfcomm snd_seq_dummy snd_hrtimer qrtr cmac algif_hash algif_skcipher af_alg bnep binfmt_misc amd_atl intel_rapl_msr ntfs3 nls_iso8
 lp parport efi_pstore nfnetlink dmi_sysfs ip_tables x_tables autofs4 hid_logitech_hidpp hid_logitech_dj hid_multitouch hid_generic nvme usbhid hid r8169 nvme_core ahci
CPU: 2 UID: 0 PID: 15723 Comm: UVM GPU1 BH Tainted: G      D    OEL      7.0.0-34-generic #34~24.04.1-Ubuntu PREEMPT(lazy) 
Tainted: [D]=DIE, [O]=OOT_MODULE, [E]=UNSIGNED_MODULE, [L]=SOFTLOCKUP
Hardware name: ASRock B850I Lightning WiFi/B850I Lightning WiFi, BIOS 3.30 06/16/2025
RIP: 0010:native_queued_spin_lock_slowpath+0x81/0x320
Code: 00 00 f0 0f ba 2b 08 0f 92 c2 8b 03 0f b6 d2 c1 e2 08 30 e4 09 d0 3d ff 00 00 00 77 6c 85 c0 74 10 0f b6 03 84 c0 74 09 f3 90 <0f> b6 03 84 c0 75 f7 b8 01 00 00 0
RSP: 0018:ffffcf4e852fb898 EFLAGS: 00000202
RAX: 0000000000000001 RBX: ffff8d3d872efae0 RCX: fffff6563faa0000
RDX: 0000000000000000 RSI: 0000000000000001 RDI: ffff8d3d872efae0
RBP: ffffcf4e852fb8c0 R08: 0000000000000000 R09: 0000000000000000
R10: 0000000000000000 R11: 0000000000000000 R12: ffff8d3dde1542a0
R13: ffff8d3d872ef9f8 R14: ffff8d3dde1542a0 R15: ffff8d3de1dfb1e8
FS:  0000000000000000(0000) GS:ffff8d4a936e3000(0000) knlGS:0000000000000000
CS:  0010 DS: 0000 ES: 0000 CR0: 0000000080050033
CR2: 000002bab8a00a00 CR3: 000000096a444000 CR4: 0000000000f50ef0
PKRU: 55555554
Call Trace:
 <TASK>
 _raw_spin_lock+0x3f/0x60
 uvm_pmm_gpu_unpin_allocated+0x23/0x90 [nvidia_uvm]
 sync_page_and_chunk_state+0x1a7/0x250 [nvidia_uvm]
 uvm_hmm_va_block_service_locked+0x53f/0x650 [nvidia_uvm]
 uvm_va_block_service_locked+0x8e/0x310 [nvidia_uvm]
 service_fault_batch_block_locked+0x443/0xb40 [nvidia_uvm]
 service_fault_batch_dispatch.isra.0+0x234/0x740 [nvidia_uvm]
 ? service_fault_batch_dispatch.isra.0+0x234/0x740 [nvidia_uvm]
 uvm_parent_gpu_service_replayable_faults+0x1c4/0xe10 [nvidia_uvm]
 replayable_faults_isr_bottom_half+0x49/0x70 [nvidia_uvm]
 replayable_faults_isr_bottom_half_entry+0x8f/0xb0 [nvidia_uvm]
 _main_loop+0x9c/0x170 [nvidia_uvm]
 ? __pfx__main_loop+0x10/0x10 [nvidia_uvm]
 kthread+0xfb/0x140
 ? __pfx_kthread+0x10/0x10
 ret_from_fork+0x1f8/0x2b0
 ? __pfx_kthread+0x10/0x10
 ret_from_fork_asm+0x1a/0x30
```

### More Info
Possibly related open issues found by the search below: #1223 (HMM oversubscription, kthread spins in the chunk-eviction/merge path, RCU stall, 595.71.05, Blackwell; "Once"; no oops in the issue text; same driver generation and the same oversubscribed-HMM trigger, different reported symptom), #1387 (kernel panic LIST_POISON2 in `__rmqueue_pcplist` via nvidia_uvm: different trace).

## Duplicate search (GitHub search API on NVIDIA/open-gpu-kernel-modules, issues and pull requests, open and closed, 2026-11-06 13:52)
| query | hits |
|---|---|
| `free_chunk` | none |
| `process_lazy_free` | none |
| `vidmem lazy free` | none |
| `uvm_pmm_gpu_unpin_allocated` | none |
| `sync_page_and_chunk_state` | none |
| `HMM oversubscription` | #1223 (open, 2026-07-01) nvidia_uvm HMM fault-service eviction deadlock (595/Blackwell); #1387 (open, 2026-09-22) Kernel panic (LIST_POISON2 in __rmqueue_pcplist via nvidia_uvm) under GPU-resident CAGRA workload — ; #1333 (open, 2026-09-02) H100 NVL: WARNING at nv.c:5461 nvidia_dev_put_uuid during UVM GPU unregister leaves GPU alloc lock o; #1358 (open, 2026-09-13) GB10 (DGX Spark): silent whole-host wedge after NVRM: NV_ERR_NO_MEMORY (_memdescAllocInternal) under |
| `HMM soft lockup` | #1223 (open, 2026-07-01) nvidia_uvm HMM fault-service eviction deadlock (595/Blackwell); #968 (open, 2025-11-19) Driver Deadlock when using 2 GPUs with 2 docker containers starting in parallel; #1333 (open, 2026-09-02) H100 NVL: WARNING at nv.c:5461 nvidia_dev_put_uuid during UVM GPU unregister leaves GPU alloc lock o; #1045 (open, 2026-03-01) Intermittent desktop lockup: Xid 62/45 -> Xid 119 (GSP timeout) -> Xid 154 on RTX 5080 (Arch Linux,  |
| `uvm_hmm eviction` | none |
| `migrate_device_pages` | none |

Candidates (number, title, state, driver, same trace?):
- **#1223** "nvidia_uvm HMM fault-service eviction deadlock (595/Blackwell)", open, 595.71.05, RCU stall / soft lockup in the eviction/merge path under HMM oversubscription: **same trigger and same family of symptom, not shown to have the same trace** (the issue text has no oops; its bug report is an attachment).
- #1387 "Kernel panic (LIST_POISON2 in __rmqueue_pcplist via nvidia_uvm) under GPU-resident CAGRA workload", open: different trace.
- #1333, #1358, #968, #1045: matched on generic words (HMM, deadlock, lockup); **different** symptoms (GPU unregister warning, wedge after NV_ERR_NO_MEMORY, multi-GPU docker deadlock, Xid lockup).
- No issue matches `free_chunk`, `process_lazy_free`, `vidmem lazy free`, `uvm_pmm_gpu_unpin_allocated` or `sync_page_and_chunk_state` (the search covers titles and bodies; text inside attached log files is not searched).

## Newer releases (checked via the GitHub tags and raw sources)
Tags newer than 595.91.07 exist: 595.99.02, 595.104.02, 595.112.07 (release 2026-10-22), 610.x, 615.x and 620.70.06 (release 2026-11-05). Source diff of `uvm_pmm_gpu.c` and `uvm_hmm.c` against 595.91.07: **595.99.02, 595.104.02, 595.112.07: `uvm_pmm_gpu.c` unchanged (0 lines); `uvm_hmm.c` changed in 64 lines, identical across the three** (a `gpu->parent->devmem` guard in the GPU-unregister eviction loop, and `access_type` set for the whole region in `uvm_hmm_va_block_service_locked`); neither touches `free_chunk` or the lazy-free path. **620.70.06: large changes in both files (796 and 536 differing lines in `uvm_pmm_gpu.c` and `uvm_hmm.c`); not examined.** No release note mentioning this symptom was found in the release metadata read. Whether a newer driver fixes the crash is **unknown**; it was not tested.

## Read-only note: which pointer `free_chunk+0x4d` dereferences (hypothesis, not verified)
`free_chunk` (`uvm_pmm_gpu.c:2402`) calls `try_chunk_free()` (`:2307`), which takes `pmm->list_lock` and calls `chunk_is_last_allocated_child()` (`:2253-2261`) = `chunk->parent->suballoc->allocated == 1`. The disassembly (`objdump -d --disassemble=free_chunk` on the stock `nvidia-uvm.ko`, offset `0x815dd`) is `mov rax,[rbx+0x28]` (chunk->parent), `mov rax,[rax+0x30]` (parent->suballoc), `cmp DWORD PTR [rax],1` (`->allocated`); the registers at the oops show RAX = 0, so `parent->suballoc` was NULL. `suballoc` is set to NULL at `uvm_pmm_gpu.c:815` when a chunk is merged. The caller is `process_lazy_free` (`:3547`), which pops chunks from `va_block_lazy_free` (added at `:3059`) and frees them without holding the PMM mutex.
