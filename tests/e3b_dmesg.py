"""Gate E3b: timestamp-based dmesg diff. The kernel log buffer on this host
is now full and rotating (the oldest line is no longer at 0.0 s), so
e09b_runner's line-count slice is wrong: its prefix check fails and it
falls back to the last 200 lines. That fallback is safe for detecting stop
patterns but misreports new-line counts. This helper returns exactly the
lines whose timestamp is later than the last line seen before."""
import re
import shutil
import e09b_runner as R

_TS = re.compile(r"^\[\s*(\d+\.\d+)\]")


def last_ts(lines):
    for l in reversed(lines):
        m = _TS.match(l)
        if m:
            return float(m.group(1))
    return -1.0


def new_since(before_lines, after_lines=None):
    t = last_ts(before_lines)
    after = after_lines if after_lines is not None else R.dmesg_lines()
    out, started = [], False
    for l in after:
        m = _TS.match(l)
        if m:
            started = float(m.group(1)) > t
        if started:
            out.append(l)
    return out


def check_after(before_lines, out_dir, label):
    """Drop-in replacement for e09b_runner.check_after (same stops, same return)."""
    new = new_since(before_lines)
    bad = [l for l in new if R.BAD.search(l)]
    if bad:
        raise R.Stop(f"dmesg ({label}): new lines matched: " + " | ".join(bad[:10]))
    mem = R.mem_available_kb()
    if mem < R.MEM_FLOOR_KB:
        raise R.Stop(f"MemAvailable ({label}): {mem} kB < 6 GiB")
    free = shutil.disk_usage(out_dir).free
    if free < R.DISK_FLOOR_BYTES:
        raise R.Stop(f"free disk ({label}): {free} B < 10 GiB")
    return len(new), mem, free
