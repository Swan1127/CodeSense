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

    if args.include_text:
        print(
            "WARNING: --include-text performs best-effort redaction only. "
            "Review the archive manually before sharing.",
            file=sys.stderr,
        )

    config_name = os.environ.get("FLASK_CONFIG", "development")
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

