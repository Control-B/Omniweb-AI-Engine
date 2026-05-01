"""Scheduler process entrypoint.

Usage:
  python -m app.scheduler          # long-running scheduler loop
  python -m app.scheduler --once   # one maintenance pass
"""
from __future__ import annotations

import argparse
import asyncio

from app.services.maintenance_scheduler import run_once, run_scheduler_loop


def main() -> None:
    parser = argparse.ArgumentParser(description="Omniweb maintenance scheduler")
    parser.add_argument("--once", action="store_true", help="run one maintenance cycle and exit")
    args = parser.parse_args()

    if args.once:
        asyncio.run(run_once())
    else:
        asyncio.run(run_scheduler_loop())


if __name__ == "__main__":
    main()
