"""Command-line entry point for the CodeSense research data export."""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_export import Anonymizer, export_research_archive  # noqa: E402


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Export anonymized CodeSense data for learning research."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Exact ZIP output path. Overrides --output-dir.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research_exports"),
        help="Directory for the timestamped ZIP (default: research_exports).",
    )
    parser.add_argument(
        "--include-text",
        action="store_true",
        help="Include redacted learning descriptions and non-code dialogue.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacement of an existing output ZIP.",
    )
    return parser.parse_args(argv)


def resolve_salt() -> bytes:
    configured = os.environ.get("CODE_SENSE_EXPORT_SALT")
    if configured:
        return configured.encode("utf-8")
    return secrets.token_bytes(32)


def resolve_output_path(args) -> Path:
    if args.output is not None:
        return args.output.expanduser().resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"codesense-research-export-{timestamp}.zip"
    return (args.output_dir / filename).expanduser().resolve()


def load_project_environment(dotenv_path: Path | None = None) -> None:
    """Load the same project .env file used by the web application."""

    from dotenv import load_dotenv

    load_dotenv(dotenv_path or PROJECT_ROOT / ".env", override=False)


def database_config_source(config_name: str) -> tuple[str, str]:
    """Return a credential-free description of the selected database config."""

    from sqlalchemy.engine import make_url

    database_url = os.environ.get("DATABASE_URL")
    source = "DATABASE_URL"
    if not database_url and config_name in {"development", "default"}:
        database_url = os.environ.get("DEV_DATABASE_URL")
        source = "DEV_DATABASE_URL"
    if not database_url and config_name in {"development", "default"}:
        database_url = "sqlite:///dev_student_code_review.db"
        source = "built-in development default"
    if not database_url and config_name == "testing":
        database_url = os.environ.get("TEST_DATABASE_URL")
        source = "TEST_DATABASE_URL"
    if not database_url and config_name == "testing":
        database_url = "sqlite:///test_student_code_review.db"
        source = "built-in testing default"
    if not database_url:
        return "missing DATABASE_URL", "unknown"

    return source, make_url(database_url).drivername


def _database_engine(config_name: str):
    """Initialize only Flask-SQLAlchemy; do not start the web app or init DB."""

    from flask import Flask

    from config import config
    from models import db

    if config_name not in config:
        raise ValueError(f"Unknown FLASK_CONFIG value: {config_name}")

    app = Flask("codesense-research-export", instance_relative_config=True)
    app.config.from_object(config[config_name])
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app, db


def main(argv=None) -> int:
    args = parse_args(argv)
    output_path = resolve_output_path(args)
    load_project_environment()

    if args.include_text:
        print(
            "WARNING: --include-text performs best-effort redaction only. "
            "Review the archive manually before sharing.",
            file=sys.stderr,
        )

    config_name = os.environ.get("FLASK_CONFIG", "development")
    config_source, database_backend = database_config_source(config_name)
    print(
        f"Database selected: backend={database_backend}; "
        f"source={config_source}; FLASK_CONFIG={config_name}"
    )
    if config_source == "built-in development default":
        print(
            "WARNING: DATABASE_URL and DEV_DATABASE_URL are unset. "
            "The exporter is using the local development SQLite database.",
            file=sys.stderr,
        )
    app, db = _database_engine(config_name)
    anonymizer = Anonymizer(resolve_salt())

    with app.app_context():
        result = export_research_archive(
            db.engine,
            output_path,
            anonymizer,
            include_text=args.include_text,
            overwrite=args.overwrite,
        )

    print(f"Research archive created: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

