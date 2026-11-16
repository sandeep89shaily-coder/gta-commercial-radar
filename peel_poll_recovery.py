"""One bounded, non-committing retry for unstable public Peel directory pages."""
from __future__ import annotations

import time

from radar import Http, collect_source


def collect_with_safe_peel_retry(source, http, *, collect=collect_source,
                                 sleep=time.sleep, client_factory=Http, **kwargs):
    """Retry ONE unstable Peel page scan from page 1, before DB snapshot commit.

    No retry for non-Peel sources, persistent duplication, permissions, SSL
    errors, or schema changes. A retry failure is propagated and recorded.
    """
    try:
        return collect(source, http, **kwargs)
    except RuntimeError as exc:
        if (source.get("collector") != "peel_health" or
                str(exc) not in (
                    "Peel pagination repeated a facility; directory changed during scan; retry",
                    "Peel directory page count changed during scan; retry before committing",
                    "Peel server returned a different page than requested")):
            raise
        print("  !! Peel directory shifted during pagination; one clean retry "
              "from page 1 before committing data.", flush=True)
        sleep(1.0)
        return collect(source, client_factory(), **kwargs)
