from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit

import pymysql
from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export assignment and ready-preset content for simulation task selection."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dotenv-path", type=Path, default=PROJECT_ROOT / ".env")
    return parser.parse_args()


def parse_json_list(value: object) -> list:
    if value in (None, ""):
        return []
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def export_candidates(output: Path, dotenv_path: Path) -> int:
    settings = dotenv_values(dotenv_path)
    database_url = str(settings.get("DATABASE_URL") or settings.get("DEV_DATABASE_URL") or "")
    if not database_url:
        raise ValueError("DATABASE_URL or DEV_DATABASE_URL is required")
    parsed = urlsplit(database_url)

    connection = pymysql.connect(
        host=parsed.hostname or "localhost",
        port=parsed.port or 3306,
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        database=parsed.path.lstrip("/"),
        charset="utf8mb4",
        connect_timeout=5,
        read_timeout=20,
        cursorclass=pymysql.cursors.DictCursor,
    )
    sql = """
        SELECT
            a.id AS assignment_id,
            a.title,
            a.description,
            a.difficulty_level,
            p.status,
            p.algorithm_summary,
            p.key_steps,
            p.reference_code,
            p.quiz_steps
        FROM assignments AS a
        INNER JOIN assignment_thinking_presets AS p
            ON p.assignment_id = a.id
        WHERE p.status = 'ready'
        ORDER BY a.id
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
    finally:
        connection.close()

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "assignment_id",
        "title",
        "description",
        "difficulty_level",
        "algorithm_summary",
        "key_steps_json",
        "reference_code",
        "quiz_steps_json",
    ]
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "assignment_id": row["assignment_id"],
                    "title": row["title"] or "",
                    "description": row["description"] or "",
                    "difficulty_level": row["difficulty_level"],
                    "algorithm_summary": row["algorithm_summary"] or "",
                    "key_steps_json": json.dumps(
                        parse_json_list(row["key_steps"]), ensure_ascii=False
                    ),
                    "reference_code": row["reference_code"] or "",
                    "quiz_steps_json": json.dumps(
                        parse_json_list(row["quiz_steps"]), ensure_ascii=False
                    ),
                }
            )
    return len(rows)


def main() -> int:
    args = parse_args()
    count = export_candidates(args.output, args.dotenv_path)
    print(f"Simulation task candidates exported: {args.output.resolve()} ({count} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
