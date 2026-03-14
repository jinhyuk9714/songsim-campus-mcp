from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import repo
from .db import connection, init_db

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _load_json(filename: str) -> list[dict]:
    return json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))


def seed_demo(force: bool = False) -> None:
    init_db()
    with connection() as conn:
        if not force and repo.count_rows(conn, "places") > 0:
            return
        repo.replace_places(conn, _load_json("sample_places.json"))
        repo.replace_courses(conn, _load_json("sample_courses.json"))
        repo.replace_restaurants(conn, _load_json("sample_restaurants.json"))
        repo.replace_notices(conn, _load_json("sample_notices.json"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo Songsim campus data")
    parser.add_argument("--force", action="store_true", help="Overwrite existing data")
    args = parser.parse_args()
    seed_demo(force=args.force)
    print("Demo data seeded.")


if __name__ == "__main__":
    main()
