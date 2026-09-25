#!/usr/bin/env bash
# Gate E3a-2 self-check (no module load): extract the ACTUAL fast-oracle and
# slow-oracle C functions from driver/src-e3a/specasync_debugfs.c by name,
# compile them in userspace against thin shims for kernel primitives, and
# replay recorded fault traces through both paths, comparing every counter
# and the full prediction stream. Also runs the load-time equivalence check
# (specasync_ft_fast_build_and_verify) itself on the real tables, and a
# forced-mismatch run to confirm the check disables the fast path.
#
# Usage: tests/e3a2_userspace_check.sh TABLE_DIR   (holds <wl>_ft_table.bin and <wl>_trace.bin)
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO/driver/src-e3a/specasync_debugfs.c"
TD="${1:?table dir}"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

extract() {  # extract a top-level definition starting at the line matching $1 through the next ^}
    awk -v pat="$1" 'found==0 && $0 ~ pat {found=1} found==1 {print} found==1 && /^}/ {exit}' "$SRC"
}
{
cat <<'EOF'
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <time.h>
typedef uint64_t u64; typedef uint32_t u32; typedef int64_t s64;
#define PAGE_SHIFT 12
#define PAGE_SIZE (1UL << PAGE_SHIFT)
typedef struct { int counter; } atomic_t;
static inline int  atomic_read(atomic_t *a) { return __atomic_load_n(&a->counter, __ATOMIC_SEQ_CST); }
static inline void atomic_set(atomic_t *a, int v) { __atomic_store_n(&a->counter, v, __ATOMIC_SEQ_CST); }
static inline void atomic_inc(atomic_t *a) { __atomic_add_fetch(&a->counter, 1, __ATOMIC_SEQ_CST); }
static inline void atomic_add(int v, atomic_t *a) { __atomic_add_fetch(&a->counter, v, __ATOMIC_SEQ_CST); }
static inline int  atomic_fetch_inc(atomic_t *a) { return __atomic_fetch_add(&a->counter, 1, __ATOMIC_SEQ_CST); }
static inline bool atomic_try_cmpxchg(atomic_t *a, int *old, int nw) {
    return __atomic_compare_exchange_n(&a->counter, old, nw, false, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST); }
#define ATOMIC_INIT(x) { (x) }
#define READ_ONCE(x) (*(volatile __typeof__(x) *)&(x))
#define WRITE_ONCE(x, v) (*(volatile __typeof__(x) *)&(x) = (v))
#define smp_store_release(p, v) __atomic_store_n((p), (v), __ATOMIC_RELEASE)
#define smp_load_acquire(p) __atomic_load_n((p), __ATOMIC_ACQUIRE)
typedef int spinlock_t;
#define DEFINE_SPINLOCK(x) static spinlock_t x = 0
#define spin_lock_irqsave(l, f) do { (void)(l); (f) = 0; } while (0)
#define spin_unlock_irqrestore(l, f) do { (void)(l); (void)(f); } while (0)
#define vmalloc malloc
#define vfree free
#define pr_err(...) printf("pr_err: " __VA_ARGS__)
#define pr_info(...) printf("pr_info: " __VA_ARGS__)
static u64 ktime_get_ns(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return (u64)t.tv_sec * 1000000000ULL + t.tv_nsec; }
#define EXPORT_SYMBOL_GPL(x)
/* shims for the two diagnostic ring pushes (off in every sweep config): count them */
static u64 g_replay_pushes, g_ftlog_pushes, g_ftlog_sum;
static inline void specasync_replay_order_push(u64 va) { (void)va; g_replay_pushes++; }
static inline void specasync_ft_log_push(u32 seq, u32 rank) { g_ftlog_pushes++; g_ftlog_sum += (u64)seq * 1000003ULL + rank; }
/* state the extracted functions reference (same names/types as the module) */
static int specasync_ft_lookahead = 1;
static atomic_t g_specasync_ft_predictions, g_specasync_ft_skipped, g_specasync_ft_held,
                g_specasync_ft_unknown_page, g_specasync_ft_exhausted,
                g_specasync_ft_fast_verified, g_specasync_ft_fast_cas_giveup;
static u64 g_specasync_ft_fast_verify_ns;
static u32 g_specasync_ft_fast_nranges;
EOF
extract '^struct specasync_ft_sorted_entry \{'
echo 'struct specasync_ft_sorted_entry;'
cat <<'EOF'
static u64 *g_ft_table = NULL;
static u32 g_ft_table_len = 0;
static struct specasync_ft_sorted_entry *g_ft_sorted = NULL;
static atomic_t g_ft_next_to_predict = ATOMIC_INIT(0);
static atomic_t g_ft_seq = ATOMIC_INIT(0);
DEFINE_SPINLOCK(g_ft_cursor_lock);
EOF
extract '^struct specasync_ft_range \{'
cat <<'EOF'
static struct specasync_ft_range *g_ft_ranges = NULL;
static u32 *g_ft_range_ranks = NULL;
static bool g_ft_fast_active = false;
#define SPECASYNC_FT_FAST_LINEAR_MAX   16
#define SPECASYNC_FT_FAST_MAX_TRIES    64
EOF
extract '^static int cmp_ft_sorted_entry\('
extract '^static int cmp_ft_bsearch_key\('
extract '^static void specasync_ft_fast_free\('
extract '^static bool specasync_ft_fast_rank\('
extract '^static void specasync_ft_fast_build_and_verify\('
extract '^static u64 specasync_ft_predict_fast\('
extract '^u64 specasync_ft_predict\(u64 fault_addr\)'
cat <<'EOF'
static u64 *read_u64s(const char *p, size_t skip, size_t *n) {
    FILE *f = fopen(p, "rb"); if (!f) { perror(p); exit(2); }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, (long)skip, SEEK_SET);
    *n = (size_t)(sz - (long)skip) / 8; u64 *b = malloc(*n * 8);
    if (fread(b, 8, *n, f) != *n) { perror("fread"); exit(2); } fclose(f); return b; }
static void reset(void) {
    atomic_set(&g_ft_next_to_predict, 0); atomic_set(&g_ft_seq, 0);
    atomic_set(&g_specasync_ft_predictions, 0); atomic_set(&g_specasync_ft_skipped, 0);
    atomic_set(&g_specasync_ft_held, 0); atomic_set(&g_specasync_ft_unknown_page, 0);
    atomic_set(&g_specasync_ft_exhausted, 0); atomic_set(&g_specasync_ft_fast_cas_giveup, 0);
    g_replay_pushes = g_ftlog_pushes = g_ftlog_sum = 0; }
struct res { int pred, skip, held, unk, exh, seq, giveup; u64 cursor, replay, ftlog, ftlog_sum, pred_hash; };
static struct res run(u64 *tr, size_t n, bool fast) {
    struct res r; u64 h = 1469598103934665603ULL; size_t i;
    reset(); g_ft_fast_active = fast;
    for (i = 0; i < n; i++) { u64 p = specasync_ft_predict(tr[i] & ~(PAGE_SIZE - 1));
        h = (h ^ p) * 1099511628211ULL; }
    r.pred = atomic_read(&g_specasync_ft_predictions); r.skip = atomic_read(&g_specasync_ft_skipped);
    r.held = atomic_read(&g_specasync_ft_held); r.unk = atomic_read(&g_specasync_ft_unknown_page);
    r.exh = atomic_read(&g_specasync_ft_exhausted); r.seq = atomic_read(&g_ft_seq);
    r.giveup = atomic_read(&g_specasync_ft_fast_cas_giveup); r.cursor = (u64)atomic_read(&g_ft_next_to_predict);
    r.replay = g_replay_pushes; r.ftlog = g_ftlog_pushes; r.ftlog_sum = g_ftlog_sum; r.pred_hash = h; return r; }
int main(int argc, char **argv) {
    size_t tn, n; u32 i; int L, Ls[] = {1, 16, 256, 4096}, bad = 0;
    u64 *tab = read_u64s(argv[1], 16, &tn), *tr = read_u64s(argv[2], 0, &n);
    g_ft_table = tab; g_ft_table_len = (u32)tn;
    g_ft_sorted = malloc(tn * sizeof(*g_ft_sorted));
    for (i = 0; i < tn; i++) { g_ft_sorted[i].page = tab[i]; g_ft_sorted[i].rank = i; g_ft_sorted[i]._pad = 0; }
    qsort(g_ft_sorted, tn, sizeof(*g_ft_sorted), cmp_ft_sorted_entry);
    specasync_ft_fast_build_and_verify();
    printf("table %zu pages, trace %zu faults, nranges %u, verified %d, verify_ns %llu\n", tn, n,
           g_specasync_ft_fast_nranges, atomic_read(&g_specasync_ft_fast_verified),
           (unsigned long long)g_specasync_ft_fast_verify_ns);
    if (atomic_read(&g_specasync_ft_fast_verified) != 1) return 1;
    for (int li = 0; li < 4; li++) {
        L = Ls[li]; specasync_ft_lookahead = L;
        u64 t0 = ktime_get_ns(); struct res s = run(tr, n, false); u64 t1 = ktime_get_ns();
        struct res f = run(tr, n, true); u64 t2 = ktime_get_ns();
        int same = !memcmp(&s, &f, sizeof(s));
        printf("L=%-5d slow: pred %d skip %d held %d unk %d exh %d seq %d cursor %llu ftlog %llu | fast: identical=%s giveup %d | userspace ns/call slow %.1f fast %.1f\n",
               L, s.pred, s.skip, s.held, s.unk, s.exh, s.seq, (unsigned long long)s.cursor,
               (unsigned long long)s.ftlog, same ? "YES" : "NO", f.giveup,
               (double)(t1 - t0) / n, (double)(t2 - t1) / n);
        bad |= !same;
    }
    /* Disable-path tests: an unaligned page and a duplicate page in the table must each
       make build_and_verify disable the fast path (verified 0, active false, index freed).
       The rank-mismatch branch shares this disable path; it cannot be reached without an
       inconsistent index, since both lookups derive from the same sorted copy. */
    {
        u64 keep = g_ft_sorted[5].page; int ok1, ok2;
        g_ft_sorted[5].page = keep | 0x8;                     /* unaligned */
        specasync_ft_fast_build_and_verify();
        ok1 = atomic_read(&g_specasync_ft_fast_verified) == 0 && !g_ft_fast_active && !g_ft_ranges && !g_ft_range_ranks;
        g_ft_sorted[5].page = keep;
        g_ft_sorted[6].page = g_ft_sorted[5].page;            /* duplicate (keeps sort order) */
        specasync_ft_fast_build_and_verify();
        ok2 = atomic_read(&g_specasync_ft_fast_verified) == 0 && !g_ft_fast_active && !g_ft_ranges && !g_ft_range_ranks;
        printf("disable-path: unaligned page -> disabled %s; duplicate page -> disabled %s\n",
               ok1 ? "YES" : "NO", ok2 ? "YES" : "NO");
        bad |= !(ok1 && ok2);
    }
    printf("RESULT: %s\n", bad ? "MISMATCH" : "slow and fast paths identical on every counter and the full prediction stream, all L");
    return bad;
}
EOF
} > "$OUT/check.c"
gcc -O2 -Wall -Wno-unused-function -o "$OUT/check" "$OUT/check.c"
for wl in stencil graphbfs; do
    echo "== $wl"
    "$OUT/check" "$TD/${wl}_ft_table.bin" "$TD/${wl}_trace.bin"
done
