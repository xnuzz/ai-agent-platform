"""CLI: `python -m saas_research [--once] [--log-level INFO] [--check-config]`.

Reads all configuration from the environment (see README.md). Exit codes: 0 ok, 2 configuration error.
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading

from .config import Settings
from .errors import ConfigurationError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="saas_research", description="Agent 1 — SaaS Opportunity Research worker")
    parser.add_argument("--once", action="store_true", help="claim and process at most one task, then exit")
    parser.add_argument("--check-config", action="store_true", help="validate configuration and exit")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("saas_research")

    try:
        settings = Settings.from_env()
        from .worker import build_worker

        worker = build_worker(settings)
    except ConfigurationError as exc:
        log.error("configuration error: %s", exc)
        return 2
    model = settings.llm_model if settings.llm_provider != "fake" else "mock"
    log.info("agent SAAS_RESEARCH ready: llm=%s:%s search=%s fetcher=%s", settings.llm_provider, model,
             settings.search_provider, settings.fetcher)
    if args.check_config:
        return 0
    if args.once:
        worked = worker.run_once()
        log.info("processed a task" if worked else "no task available")
        return 0

    stop = threading.Event()

    def _stop(signum, _frame):
        log.info("signal %s received, finishing current task then stopping", signum)
        stop.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    worker.run_forever(stop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
