"""CLI: `python -m local_leads` - run the LOCAL_LEAD_DISCOVERY worker until SIGTERM/SIGINT.

Configuration comes from the environment (README §Environment). `--once` claims at most one task and
exits (useful for cron-style runs and smoke tests); `--check-config` validates settings and exits.
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading

from .config import DEFAULT_CRAWLER_INFO_URL, Settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="local_leads", description="Agent 2 - Local Business Lead Finder worker")
    parser.add_argument("--once", action="store_true", help="claim and process at most one task, then exit")
    parser.add_argument("--check-config", action="store_true", help="validate configuration and exit")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("local_leads")

    settings = Settings.from_env()
    problems = []
    if not settings.platform_api_url:
        problems.append("PLATFORM_API_URL is not set")
    if not settings.platform_agent_token:
        problems.append("PLATFORM_AGENT_TOKEN is not set")
    if settings.discovery_provider == "google_places" and not settings.google_places_api_key:
        problems.append("GOOGLE_PLACES_API_KEY is required for DISCOVERY_PROVIDER=google_places")
    if problems:
        for p in problems:
            log.error(p)
        return 2
    if settings.crawler.info_url == DEFAULT_CRAWLER_INFO_URL:
        log.warning("CRAWLER_INFO_URL is not set: set it to a public page describing the crawler "
                    "(it is sent in the User-Agent so site owners can identify and contact you)")

    from . import LocalLeadsAgent, build_worker

    agent = LocalLeadsAgent(settings)
    log.info("discovery=%s llm=%s user-agent=%r", agent.discovery.name,
             agent.llm.describe() if agent.llm else "template", settings.crawler.user_agent)
    if args.check_config:
        agent.close()
        return 0
    worker = build_worker(settings, agent=agent)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    try:
        if args.once:
            worker.run_once()
        else:
            worker.run_forever(stop)
    finally:
        agent.close()
        worker.client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
