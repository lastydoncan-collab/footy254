import os
import time
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from data_pipeline.data_fetcher import fetch_competition_matches
from services.normalizers.fixture_normalizer import normalize_fixture
from services.collectors.store_fixtures import store_fixtures


# ========================================
# COMPETITIONS TO LOAD
# ========================================

COMPETITIONS = [
    "PL",
    "PD",
    "BL1",
    "SA",
    "FL1",
    "CL",
    "ELC",
    "WC",
]


# ========================================
# SEASONS TO LOAD
# ========================================

SEASONS = [
    2015,
    2016,
    2017,
    2018,
    2019,
    2020,
    2021,
    2022,
    2023,
    2024,
    2025,
]


# ========================================
# LOAD HISTORICAL DATA
# ========================================

def load_all_historical():

    total = 0

    for code in COMPETITIONS:
        for season in SEASONS:

            print(f"Loading {code} season {season}...")

            raw_matches = fetch_competition_matches(
                code,
                status="FINISHED",
                season=season,
            )

            if not raw_matches:
                print(f"  No data for {code} {season}")
                continue

            normalized = [
                normalize_fixture(match)
                for match in raw_matches
            ]

            count = store_fixtures(normalized)
            total += count

            print(f"  Stored {count} matches for {code} {season}")

            time.sleep(7)

    print(f"\nTotal matches loaded: {total}")


if __name__ == "__main__":
    load_all_historical()