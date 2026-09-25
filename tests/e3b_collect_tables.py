#!/usr/bin/env python3
"""Gate E3b: run the unchanged E0.9b table collector (verified module, prefetch
off, distinct-page assertions 1,125,000 / 287,956) with E3b's extended stop
pattern and timestamp-based dmesg diff patched in."""
import os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
import e09b_runner as R  # noqa: E402
import e3b_dmesg  # noqa: E402
R.check_after = e3b_dmesg.check_after
R.BAD = re.compile(r"BUG|Oops|WARNING|general protection|NULL pointer|exited with irqs disabled|"
                   r"soft lockup|hung_task|RCU stall")
import e09b_collect_tables as C  # noqa: E402
sys.exit(C.main())
