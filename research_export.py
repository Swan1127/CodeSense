"""Read-only, privacy-preserving research data export for CodeSense."""

from __future__ import annotations

import csv
import hashlib
import hmac
import json
import re
import tempfile
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import MetaData, Table, case, func, inspect, select


SCRIPT_VERSION = "1.0.0"
EXPECTED_ARCHIVE_FILES = {
    "users.csv",
    "assignments.csv",
    "submissions.csv",
    "thinking_sessions.csv",
    "thinking_stage_logs.csv",
    "thinking_presets.csv",
    "schema_inventory.csv",
    "manifest.json",
    "data_quality.json",
    "README.txt",
}

RESEARCH_TABLES = (
    "users",
    "assignments",
    "submissions",
    "thinking_sessions",
    "thinking_stage_logs",
    "assignment_thinking_presets",
)

EXPECTED_COLUMNS = {
    "users": (
        "student_id",
        "usertype",
        "class_name",
        "class_id",
        "created_at",
    ),
    "assignments": (
        "id",
        "description",
        "created_time",
        "due_date",
        "target_classes",
        "difficulty_level",
    ),
    "submissions": (
        "id",
        "student_id",
        "assignment_id",
        "code",
        "score",
        "language",
        "submitted_at",
        "status",
        "feedback",
        "ai_feedback",
        "sandbox_status",
        "sandbox_passed",
        "sandbox_total",
    ),
    "thinking_sessions": (
        "id",
        "student_id",
        "assignment_id",
        "current_stage",
        "stage1_description",
        "stage1_score",
        "stage1_hint_count",
        "stage2_completed",
        "stage2_hint_count",
        "stage3_completed",
        "stage3_teacher_rounds",
        "stage3_student_rounds",
        "total_time_seconds",
        "started_at",
        "completed_at",
        "status",
    ),
    "thinking_stage_logs": (
        "id",
        "session_id",
        "stage",
        "event_type",
        "role",
        "content",
        "metadata_json",
        "created_at",
    ),
    "assignment_thinking_presets": (
        "id",
        "assignment_id",
        "key_steps",
        "code_blocks",
        "noise_blocks",
        "quiz_steps",
        "difficulty_config",
        "status",
        "created_at",
        "updated_at",
    ),
}

TIME_COLUMNS = {
    "users": ("created_at",),
    "assignments": ("created_time", "due_date"),
    "submissions": ("submitted_at",),
    "thinking_sessions": ("started_at", "completed_at"),
    "thinking_stage_logs": ("created_at",),
    "assignment_thinking_presets": ("created_at", "updated_at"),
}

CSV_HEADERS = {
    "users.csv": (
        "anonymous_user_id",
        "user_role",
        "anonymous_class_id",
        "created_at",
    ),
    "assignments.csv": (
        "anonymous_assignment_id",
        "created_at",
        "due_at",
        "difficulty_level",
        "target_class_count",
        "description_char_count",
        "has_thinking_preset",
    ),
    "submissions.csv": (
        "anonymous_submission_id",
        "anonymous_user_id",
        "anonymous_assignment_id",
        "submitted_at",
        "score",
        "status",
        "language",
        "code_char_count",
        "code_nonempty_line_count",
        "feedback_char_count",
        "ai_feedback_char_count",
        "sandbox_status",
        "sandbox_passed",
        "sandbox_total",
    ),
    "thinking_sessions.csv": (
        "anonymous_session_id",
        "anonymous_user_id",
        "anonymous_assignment_id",
        "current_stage",
        "status",
        "stage1_score",
        "stage1_hint_count",
        "stage1_description_char_count",
        "stage2_completed",
        "stage2_hint_count",
        "stage3_completed",
        "stage3_teacher_rounds",
        "stage3_student_rounds",
        "total_time_seconds",
        "started_at",
        "completed_at",
    ),
    "thinking_stage_logs.csv": (
        "anonymous_log_id",
        "anonymous_session_id",
        "stage",
        "event_type",
        "role",
        "created_at",
        "content_char_count",
        "metadata_key_count",
        "metadata_keys",
        "metadata_boolean_true_count",
        "metadata_numeric_count",
    ),
    "thinking_presets.csv": (
        "anonymous_preset_id",
        "anonymous_assignment_id",
        "status",
        "created_at",
        "updated_at",
        "key_step_count",
        "code_block_count",
        "noise_block_count",
        "quiz_step_count",
        "feynman_rounds",
        "student_persona",
    ),
    "schema_inventory.csv": (
        "table_name",
        "column_name",
        "data_type",
        "nullable",
    ),
}

CODE_EVENT_TYPES = {
    "fix_code",
    "write_code",
    "code_submit",
    "code_submission",
    "code_review",
}

EMAIL_RE = re.compile(
    r"(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"
    r"(?![A-Z0-9.-])",
    re.IGNORECASE,
)
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
IPV4_RE = re.compile(
    r"(?<!\d)(?:25[0-5]|2[0-4]\d|1?\d?\d)"
    r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?!\d)"
)
STUDENT_ID_RE = re.compile(r"(?<!\d)\d{8,14}(?!\d)")


class Anonymizer:
    """Generate stable, namespace-separated identifiers for one export."""

    def __init__(self, salt: bytes):
        if not salt:
            raise ValueError("Anonymous export salt must not be empty")
        self.salt = salt

    def id(self, namespace: str, value: Any) -> str:
        if value is None or value == "":
            return ""
        message = f"{namespace}:{value}".encode("utf-8")
        digest = hmac.new(self.salt, message, hashlib.sha256).hexdigest()
        return f"{namespace[:3]}_{digest[:16]}"

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.salt).hexdigest()[:12]


def redact_text(text_value: Any) -> str:
    """Apply conservative, best-effort redaction to free-form learning text."""

    if text_value is None:
        return ""
    value = str(text_value)
    value = EMAIL_RE.sub("[EMAIL]", value)
    value = PHONE_RE.sub("[PHONE]", value)
    value = IPV4_RE.sub("[IP]", value)
    value = STUDENT_ID_RE.sub("[STUDENT_ID]", value)
    return value


def text_metrics(text_value: Any) -> dict[str, int]:
    value = "" if text_value is None else str(text_value)
    return {
        "char_count": len(value),
        "nonempty_line_count": sum(1 for line in value.splitlines() if line.strip()),
    }


def _json_value(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _json_list_count(value: Any) -> int:
    parsed = _json_value(value)
    return len(parsed) if isinstance(parsed, list) else 0


def _metadata_metrics(value: Any) -> dict[str, Any]:
    parsed = _json_value(value)
    if not isinstance(parsed, dict):
        return {
            "metadata_key_count": 0,
            "metadata_keys": "",
            "metadata_boolean_true_count": 0,
            "metadata_numeric_count": 0,
        }
    keys = sorted(str(key) for key in parsed)
    return {
        "metadata_key_count": len(keys),
        "metadata_keys": ";".join(keys),
        "metadata_boolean_true_count": sum(item is True for item in parsed.values()),
        "metadata_numeric_count": sum(
            isinstance(item, (int, float)) and not isinstance(item, bool)
            for item in parsed.values()
        ),
    }


def _iso(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _bool_value(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        return "1" if value.strip().lower() in {"1", "true", "yes"} else "0"
    return "1" if bool(value) else "0"


def _target_class_count(value: Any) -> int:
    if not value:
        return 0
    return len([part for part in str(value).split(",") if part.strip()])


def _difficulty_fields(value: Any) -> tuple[Any, str]:
    parsed = _json_value(value)
    if not isinstance(parsed, dict):
        return "", ""
    rounds = parsed.get("feynman_rounds", "")
    if not isinstance(rounds, (int, float)):
        rounds = ""
    persona = parsed.get("student_persona", "")
    if not isinstance(persona, str):
        persona = ""
    return rounds, persona


def _write_csv(path: Path, headers: Iterable[str], rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(headers), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in writer.fieldnames})
            count += 1
    return count


class _DatabaseReader:
    def __init__(self, engine):
        self.engine = engine
        self.inspector = inspect(engine)
        self.table_names = set(self.inspector.get_table_names())
        self.columns: dict[str, set[str]] = {}
        self.missing_tables: list[str] = []
        self.missing_columns: dict[str, list[str]] = {}
        self._reflected_tables: dict[str, Table] = {}

        for table_name in RESEARCH_TABLES:
            if table_name not in self.table_names:
                self.missing_tables.append(table_name)
                self.columns[table_name] = set()
                self.missing_columns[table_name] = list(EXPECTED_COLUMNS[table_name])
                continue
            actual = {
                column["name"] for column in self.inspector.get_columns(table_name)
            }
            self.columns[table_name] = actual
            missing = [
                name for name in EXPECTED_COLUMNS[table_name] if name not in actual
            ]
            if missing:
                self.missing_columns[table_name] = missing

    def rows(self, table_name: str):
        if table_name not in self.table_names:
            return
        table = self.table(table_name)
        selected_names = [
            name for name in EXPECTED_COLUMNS[table_name] if name in table.c
        ]
        statement = select(*(table.c[name] for name in selected_names))
        with self.engine.connect() as connection:
            result = connection.execution_options(stream_results=True).execute(statement)
            for row in result.mappings():
                yield row

    def table(self, table_name: str) -> Table:
        if table_name not in self._reflected_tables:
            self._reflected_tables[table_name] = Table(
                table_name,
                MetaData(),
                autoload_with=self.engine,
            )
        return self._reflected_tables[table_name]

    def schema_rows(self):
        for table_name in RESEARCH_TABLES:
            if table_name not in self.table_names:
                continue
            allowed_columns = set(EXPECTED_COLUMNS[table_name])
            for column in self.inspector.get_columns(table_name):
                if column["name"] not in allowed_columns:
                    continue
                yield {
                    "table_name": table_name,
                    "column_name": column["name"],
                    "data_type": str(column["type"]),
                    "nullable": _bool_value(column.get("nullable")),
                }

    def time_ranges(self) -> dict[str, dict[str, dict[str, str]]]:
        result: dict[str, dict[str, dict[str, str]]] = {}
        with self.engine.connect() as connection:
            for table_name, column_names in TIME_COLUMNS.items():
                if table_name not in self.table_names:
                    continue
                table = self.table(table_name)
                table_result: dict[str, dict[str, str]] = {}
                for column_name in column_names:
                    if column_name not in table.c:
                        continue
                    minimum, maximum = connection.execute(
                        select(
                            func.min(table.c[column_name]),
                            func.max(table.c[column_name]),
                        )
                    ).one()
                    table_result[column_name] = {
                        "min": _iso(minimum),
                        "max": _iso(maximum),
                    }
                result[table_name] = table_result
        return result

    def null_counts(self) -> dict[str, dict[str, int]]:
        result: dict[str, dict[str, int]] = {}
        with self.engine.connect() as connection:
            for table_name in RESEARCH_TABLES:
                if table_name not in self.table_names:
                    continue
                table = self.table(table_name)
                column_names = [
                    name
                    for name in EXPECTED_COLUMNS[table_name]
                    if name in table.c
                ]
                expressions = [
                    func.sum(
                        case((table.c[name].is_(None), 1), else_=0)
                    ).label(name)
                    for name in column_names
                ]
                if not expressions:
                    result[table_name] = {}
                    continue
                row = connection.execute(select(*expressions)).mappings().one()
                result[table_name] = {
                    name: int(row[name] or 0) for name in column_names
                }
        return result

    def orphan_relationship_counts(self) -> dict[str, int | None]:
        checks = (
            (
                "submissions_without_user",
                "submissions",
                "student_id",
                "users",
                "student_id",
            ),
            (
                "submissions_without_assignment",
                "submissions",
                "assignment_id",
                "assignments",
                "id",
            ),
            (
                "thinking_sessions_without_user",
                "thinking_sessions",
                "student_id",
                "users",
                "student_id",
            ),
            (
                "thinking_sessions_without_assignment",
                "thinking_sessions",
                "assignment_id",
                "assignments",
                "id",
            ),
            (
                "thinking_logs_without_session",
                "thinking_stage_logs",
                "session_id",
                "thinking_sessions",
                "id",
            ),
        )
        result: dict[str, int | None] = {}
        with self.engine.connect() as connection:
            for label, child_name, child_key, parent_name, parent_key in checks:
                if (
                    child_name not in self.table_names
                    or parent_name not in self.table_names
                ):
                    result[label] = None
                    continue
                child = self.table(child_name)
                parent = self.table(parent_name)
                if child_key not in child.c or parent_key not in parent.c:
                    result[label] = None
                    continue
                statement = (
                    select(func.count())
                    .select_from(
                        child.outerjoin(
                            parent,
                            child.c[child_key] == parent.c[parent_key],
                        )
                    )
                    .where(child.c[child_key].is_not(None))
                    .where(parent.c[parent_key].is_(None))
                )
                result[label] = int(connection.execute(statement).scalar_one())
        return result


def _users_rows(reader: _DatabaseReader, anonymizer: Anonymizer):
    for row in reader.rows("users"):
        class_value = row.get("class_id") or row.get("class_name")
        yield {
            "anonymous_user_id": anonymizer.id("user", row.get("student_id")),
            "user_role": row.get("usertype", ""),
            "anonymous_class_id": anonymizer.id("class", class_value),
            "created_at": _iso(row.get("created_at")),
        }


def _preset_assignment_ids(reader: _DatabaseReader) -> set[Any]:
    return {
        row.get("assignment_id")
        for row in reader.rows("assignment_thinking_presets")
        if row.get("assignment_id") is not None
    }


def _assignments_rows(
    reader: _DatabaseReader,
    anonymizer: Anonymizer,
    preset_assignment_ids: set[Any],
):
    for row in reader.rows("assignments"):
        assignment_id = row.get("id")
        yield {
            "anonymous_assignment_id": anonymizer.id("assignment", assignment_id),
            "created_at": _iso(row.get("created_time")),
            "due_at": _iso(row.get("due_date")),
            "difficulty_level": row.get("difficulty_level", ""),
            "target_class_count": _target_class_count(row.get("target_classes")),
            "description_char_count": text_metrics(row.get("description"))["char_count"],
            "has_thinking_preset": _bool_value(
                assignment_id in preset_assignment_ids
            ),
        }


def _submissions_rows(reader: _DatabaseReader, anonymizer: Anonymizer):
    for row in reader.rows("submissions"):
        code_metrics = text_metrics(row.get("code"))
        yield {
            "anonymous_submission_id": anonymizer.id("submission", row.get("id")),
            "anonymous_user_id": anonymizer.id("user", row.get("student_id")),
            "anonymous_assignment_id": anonymizer.id(
                "assignment", row.get("assignment_id")
            ),
            "submitted_at": _iso(row.get("submitted_at")),
            "score": row.get("score", ""),
            "status": row.get("status", ""),
            "language": row.get("language", ""),
            "code_char_count": code_metrics["char_count"],
            "code_nonempty_line_count": code_metrics["nonempty_line_count"],
            "feedback_char_count": text_metrics(row.get("feedback"))["char_count"],
            "ai_feedback_char_count": text_metrics(row.get("ai_feedback"))[
                "char_count"
            ],
            "sandbox_status": row.get("sandbox_status", ""),
            "sandbox_passed": row.get("sandbox_passed", ""),
            "sandbox_total": row.get("sandbox_total", ""),
        }


def _sessions_rows(
    reader: _DatabaseReader,
    anonymizer: Anonymizer,
    include_text: bool,
):
    for row in reader.rows("thinking_sessions"):
        result = {
            "anonymous_session_id": anonymizer.id("session", row.get("id")),
            "anonymous_user_id": anonymizer.id("user", row.get("student_id")),
            "anonymous_assignment_id": anonymizer.id(
                "assignment", row.get("assignment_id")
            ),
            "current_stage": row.get("current_stage", ""),
            "status": row.get("status", ""),
            "stage1_score": row.get("stage1_score", ""),
            "stage1_hint_count": row.get("stage1_hint_count", ""),
            "stage1_description_char_count": text_metrics(
                row.get("stage1_description")
            )["char_count"],
            "stage2_completed": _bool_value(row.get("stage2_completed")),
            "stage2_hint_count": row.get("stage2_hint_count", ""),
            "stage3_completed": _bool_value(row.get("stage3_completed")),
            "stage3_teacher_rounds": row.get("stage3_teacher_rounds", ""),
            "stage3_student_rounds": row.get("stage3_student_rounds", ""),
            "total_time_seconds": row.get("total_time_seconds", ""),
            "started_at": _iso(row.get("started_at")),
            "completed_at": _iso(row.get("completed_at")),
        }
        if include_text:
            result["stage1_description_redacted"] = redact_text(
                row.get("stage1_description")
            )
        yield result


def _logs_rows(
    reader: _DatabaseReader,
    anonymizer: Anonymizer,
    include_text: bool,
):
    for row in reader.rows("thinking_stage_logs"):
        event_type = str(row.get("event_type") or "")
        result = {
            "anonymous_log_id": anonymizer.id("log", row.get("id")),
            "anonymous_session_id": anonymizer.id("session", row.get("session_id")),
            "stage": row.get("stage", ""),
            "event_type": event_type,
            "role": row.get("role", ""),
            "created_at": _iso(row.get("created_at")),
            "content_char_count": text_metrics(row.get("content"))["char_count"],
        }
        result.update(_metadata_metrics(row.get("metadata_json")))
        if include_text:
            result["content_redacted"] = (
                ""
                if event_type.lower() in CODE_EVENT_TYPES
                else redact_text(row.get("content"))
            )
        yield result


def _presets_rows(reader: _DatabaseReader, anonymizer: Anonymizer):
    for row in reader.rows("assignment_thinking_presets"):
        rounds, persona = _difficulty_fields(row.get("difficulty_config"))
        yield {
            "anonymous_preset_id": anonymizer.id("preset", row.get("id")),
            "anonymous_assignment_id": anonymizer.id(
                "assignment", row.get("assignment_id")
            ),
            "status": row.get("status", ""),
            "created_at": _iso(row.get("created_at")),
            "updated_at": _iso(row.get("updated_at")),
            "key_step_count": _json_list_count(row.get("key_steps")),
            "code_block_count": _json_list_count(row.get("code_blocks")),
            "noise_block_count": _json_list_count(row.get("noise_blocks")),
            "quiz_step_count": _json_list_count(row.get("quiz_steps")),
            "feynman_rounds": rounds,
            "student_persona": persona,
        }


def _headers(name: str, include_text: bool) -> tuple[str, ...]:
    headers = CSV_HEADERS[name]
    if include_text and name == "thinking_sessions.csv":
        return headers + ("stage1_description_redacted",)
    if include_text and name == "thinking_stage_logs.csv":
        return headers + ("content_redacted",)
    return headers


def _readme_text(include_text: bool) -> str:
    return (
        "CodeSense research export\n"
        "=========================\n\n"
        "This archive contains anonymized, read-only extracts for learning "
        "analytics research.\n"
        "Direct identifiers, credentials, database connection strings, source "
        "code, assignment text, and feedback text are excluded.\n"
        f"Redacted learning text included: {'yes' if include_text else 'no'}.\n"
        "Free-form text redaction is best effort. If text is included, review it "
        "manually before sharing beyond the research team.\n"
        "Anonymous identifiers are stable only within exports that use the same "
        "CODE_SENSE_EXPORT_SALT value.\n"
    )


def export_research_archive(
    engine,
    output_path: str | Path,
    anonymizer: Anonymizer,
    *,
    include_text: bool = False,
    overwrite: bool = False,
) -> Path:
    """Export selected research data without modifying the source database."""

    destination = Path(output_path).expanduser().resolve()
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    reader = _DatabaseReader(engine)
    row_counts: dict[str, int] = {}
    preset_ids = _preset_assignment_ids(reader)

    with tempfile.TemporaryDirectory(prefix="codesense-research-") as temp_name:
        temp_dir = Path(temp_name)
        exporters = {
            "users.csv": _users_rows(reader, anonymizer),
            "assignments.csv": _assignments_rows(reader, anonymizer, preset_ids),
            "submissions.csv": _submissions_rows(reader, anonymizer),
            "thinking_sessions.csv": _sessions_rows(
                reader, anonymizer, include_text
            ),
            "thinking_stage_logs.csv": _logs_rows(
                reader, anonymizer, include_text
            ),
            "thinking_presets.csv": _presets_rows(reader, anonymizer),
            "schema_inventory.csv": reader.schema_rows(),
        }

        for filename, rows in exporters.items():
            row_counts[filename] = _write_csv(
                temp_dir / filename,
                _headers(filename, include_text),
                rows,
            )

        manifest = {
            "script_version": SCRIPT_VERSION,
            "exported_at_utc": datetime.now(timezone.utc).isoformat(),
            "database_type": engine.dialect.name,
            "include_text": include_text,
            "anonymous_salt_fingerprint": anonymizer.fingerprint,
            "row_counts": row_counts,
        }
        quality = {
            "missing_tables": sorted(reader.missing_tables),
            "missing_columns": {
                key: sorted(value)
                for key, value in sorted(reader.missing_columns.items())
            },
            "row_counts": row_counts,
            "time_ranges": reader.time_ranges(),
            "null_counts": reader.null_counts(),
            "orphan_relationship_counts": reader.orphan_relationship_counts(),
            "notes": [
                "Missing optional fields are left blank in CSV output.",
                "No source table was modified during export.",
            ],
        }
        (temp_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (temp_dir / "data_quality.json").write_text(
            json.dumps(quality, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (temp_dir / "README.txt").write_text(
            _readme_text(include_text),
            encoding="utf-8",
        )

        with zipfile.ZipFile(
            destination, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for filename in sorted(EXPECTED_ARCHIVE_FILES):
                archive.write(temp_dir / filename, arcname=filename)

    return destination
