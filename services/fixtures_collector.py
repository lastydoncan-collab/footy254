import logging
from typing import Any

from services.synchronization_service import (
    SynchronizationService,
)

logger = logging.getLogger(__name__)

# ==========================================================
# SINGLE SERVICE INSTANCE
# ==========================================================

_sync_service = SynchronizationService()

# ==========================================================
# COLLECT & SYNCHRONIZE FIXTURES
# ==========================================================

def collect_fixtures(
    days_ahead: int = 7,
) -> dict[str, Any]:
    """
    Synchronize upcoming real-world fixtures from football-data.org,
    store them in PostgreSQL and generate predictions for any fixtures
    that require them.

    Returns a synchronization summary.
    """

    logger.info(
        "Starting fixture collection (%d days ahead)...",
        days_ahead,
    )

    result = _sync_service.synchronize(days_ahead)

    logger.info(
        "Fixture synchronization completed."
    )

    return result


# ==========================================================
# MANUAL ENTRY POINT
# ==========================================================

if __name__ == "__main__":

    summary = collect_fixtures()

    print(summary)