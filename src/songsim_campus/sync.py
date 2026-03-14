from __future__ import annotations

import argparse
import json

from .db import connection, init_db
from .services import sync_official_snapshot
from .settings import get_settings


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Sync official Songsim campus data into PostgreSQL/PostGIS"
    )
    parser.add_argument("--campus", default=settings.official_campus_id, help="Official campus id")
    parser.add_argument("--year", type=int, default=settings.official_course_year)
    parser.add_argument(
        "--semester",
        type=int,
        choices=[1, 2],
        default=settings.official_course_semester,
    )
    parser.add_argument(
        "--notice-pages",
        type=int,
        default=settings.official_notice_pages,
        help="How many notice list pages to ingest",
    )
    args = parser.parse_args()

    init_db()
    with connection() as conn:
        summary = sync_official_snapshot(
            conn,
            campus=args.campus,
            year=args.year,
            semester=args.semester,
            notice_pages=args.notice_pages,
        )
    print(json.dumps(summary, ensure_ascii=False))
