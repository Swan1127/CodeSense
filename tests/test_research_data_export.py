import csv
import io
import json
import zipfile

import pytest
from sqlalchemy import create_engine, text

from research_export import (
    Anonymizer,
    EXPECTED_ARCHIVE_FILES,
    export_research_archive,
    redact_text,
    text_metrics,
)
from scripts.export_research_dataset import parse_args, resolve_salt


def _read_csv(archive, name):
    content = archive.read(name).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(content)))


def _build_sample_engine(tmp_path, include_optional_columns=True):
    engine = create_engine(f"sqlite:///{tmp_path / 'sample.db'}")
    with engine.begin() as connection:
        connection.execute(text(
            """
            CREATE TABLE users (
                student_id TEXT PRIMARY KEY,
                username TEXT,
                password_hash TEXT,
                usertype TEXT,
                class_name TEXT,
                created_at DATETIME
            )
            """
        ))
        connection.execute(text(
            """
            CREATE TABLE assignments (
                id INTEGER PRIMARY KEY,
                title TEXT,
                description TEXT,
                created_time DATETIME,
                due_date DATETIME,
                target_classes TEXT,
                difficulty_level INTEGER
            )
            """
        ))
        submission_optional = (
            ", feedback TEXT, ai_feedback TEXT, sandbox_status TEXT, "
            "sandbox_passed INTEGER, sandbox_total INTEGER"
            if include_optional_columns else ""
        )
        connection.execute(text(
            f"""
            CREATE TABLE submissions (
                id INTEGER PRIMARY KEY,
                student_id TEXT,
                assignment_id INTEGER,
                code TEXT,
                score INTEGER,
                language TEXT,
                submitted_at DATETIME,
                status TEXT
                {submission_optional}
            )
            """
        ))
        connection.execute(text(
            """
            CREATE TABLE assignment_thinking_presets (
                id INTEGER PRIMARY KEY,
                assignment_id INTEGER,
                reference_code TEXT,
                key_steps TEXT,
                code_blocks TEXT,
                noise_blocks TEXT,
                quiz_steps TEXT,
                difficulty_config TEXT,
                status TEXT,
                created_at DATETIME,
                updated_at DATETIME
            )
            """
        ))
        connection.execute(text(
            """
            CREATE TABLE thinking_sessions (
                id INTEGER PRIMARY KEY,
                student_id TEXT,
                assignment_id INTEGER,
                current_stage INTEGER,
                stage1_description TEXT,
                stage1_score REAL,
                stage1_hint_count INTEGER,
                stage2_completed BOOLEAN,
                stage2_hint_count INTEGER,
                stage3_completed BOOLEAN,
                stage3_teacher_rounds INTEGER,
                stage3_student_rounds INTEGER,
                total_time_seconds INTEGER,
                started_at DATETIME,
                completed_at DATETIME,
                status TEXT
            )
            """
        ))
        connection.execute(text(
            """
            CREATE TABLE thinking_stage_logs (
                id INTEGER PRIMARY KEY,
                session_id INTEGER,
                stage INTEGER,
                event_type TEXT,
                role TEXT,
                content TEXT,
                metadata_json TEXT,
                created_at DATETIME
            )
            """
        ))

        connection.execute(text(
            """
            INSERT INTO users VALUES (
                '20240001', '真实姓名', 'password-secret', '学生',
                '软件工程一班', '2026-06-01 08:00:00'
            )
            """
        ))
        connection.execute(text(
            """
            INSERT INTO assignments VALUES (
                7, '敏感题目标题', '题目正文', '2026-06-01 09:00:00',
                '2026-07-01 09:00:00', '软件工程一班', 3
            )
            """
        ))
        if include_optional_columns:
            connection.execute(text(
                """
                INSERT INTO submissions VALUES (
                    9, '20240001', 7, 'int main(){return 0;}', 88, 'cpp',
                    '2026-06-02 10:00:00', 'evaluated', '联系 test@example.com',
                    'AI反馈正文', 'passed', 3, 3
                )
                """
            ))
        else:
            connection.execute(text(
                """
                INSERT INTO submissions VALUES (
                    9, '20240001', 7, 'int main(){return 0;}', 88, 'cpp',
                    '2026-06-02 10:00:00', 'evaluated'
                )
                """
            ))
        connection.execute(text(
            """
            INSERT INTO assignment_thinking_presets VALUES (
                3, 7, 'int answer(){return 1;}', '["步骤一", "步骤二"]',
                '[{"id": 1}]', '[{"id": 2}]', '[{"step_id": 1}]',
                '{"feynman_rounds": 4, "student_persona": "skeptical"}',
                'ready', '2026-06-01 09:10:00', '2026-06-01 09:20:00'
            )
            """
        ))
        connection.execute(text(
            """
            INSERT INTO thinking_sessions VALUES (
                11, '20240001', 7, 3,
                '我是20240001，邮箱test@example.com，我先遍历数组', 82, 1,
                1, 2, 1, 3, 4, 600,
                '2026-06-02 09:00:00', '2026-06-02 09:10:00', 'completed'
            )
            """
        ))
        connection.execute(text(
            """
            INSERT INTO thinking_stage_logs VALUES (
                21, 11, 1, 'companion_chat', 'student',
                '手机号13800138000，我应该先遍历吗？',
                '{"panel": "companion", "attempt": 2}',
                '2026-06-02 09:01:00'
            )
            """
        ))
        connection.execute(text(
            """
            INSERT INTO thinking_stage_logs VALUES (
                22, 11, 3, 'fix_code', 'student',
                'int main(){return 2;}',
                '{"passed": true}', '2026-06-02 09:09:00'
            )
            """
        ))
    return engine


def test_anonymizer_is_stable_and_namespace_separated():
    anonymizer = Anonymizer(b"fixed-test-salt")
    user_id = anonymizer.id("user", "20240001")
    assert user_id == anonymizer.id("user", "20240001")
    assert user_id != anonymizer.id("assignment", "20240001")
    assert "20240001" not in user_id


def test_redact_text_removes_common_identifiers():
    value = redact_text(
        "联系 test@example.com，手机 13800138000，IP 10.0.0.8，学号 2024123456"
    )
    assert "test@example.com" not in value
    assert "13800138000" not in value
    assert "10.0.0.8" not in value
    assert "2024123456" not in value


def test_text_metrics_do_not_return_source_text():
    source = "int main() {\n\n return 0;\n}"
    assert text_metrics(source) == {
        "char_count": len(source),
        "nonempty_line_count": 3,
    }


def test_export_archive_contains_joinable_anonymized_files(tmp_path):
    engine = _build_sample_engine(tmp_path)
    output = tmp_path / "research.zip"
    export_research_archive(engine, output, Anonymizer(b"fixed-salt"))

    with zipfile.ZipFile(output) as archive:
        assert EXPECTED_ARCHIVE_FILES <= set(archive.namelist())
        users = _read_csv(archive, "users.csv")
        submissions = _read_csv(archive, "submissions.csv")
        sessions = _read_csv(archive, "thinking_sessions.csv")
        assert users[0]["anonymous_user_id"] == submissions[0]["anonymous_user_id"]
        assert users[0]["anonymous_user_id"] == sessions[0]["anonymous_user_id"]
        assert submissions[0]["code_char_count"] == "21"
        assert "code" not in submissions[0]

        payload = b"\n".join(archive.read(name) for name in archive.namelist())
        for forbidden in (
            b"20240001",
            b"password-secret",
            b"password_hash",
            b"current_session_id",
            b"test@example.com",
            b"int main",
            b"DATABASE_URL",
        ):
            assert forbidden not in payload


def test_include_text_redacts_learning_text_but_never_exports_code_events(tmp_path):
    engine = _build_sample_engine(tmp_path)
    output = tmp_path / "research-with-text.zip"
    export_research_archive(
        engine,
        output,
        Anonymizer(b"fixed-salt"),
        include_text=True,
    )

    with zipfile.ZipFile(output) as archive:
        sessions = _read_csv(archive, "thinking_sessions.csv")
        logs = _read_csv(archive, "thinking_stage_logs.csv")
        assert "[STUDENT_ID]" in sessions[0]["stage1_description_redacted"]
        assert "[EMAIL]" in sessions[0]["stage1_description_redacted"]
        chat = next(row for row in logs if row["event_type"] == "companion_chat")
        code_fix = next(row for row in logs if row["event_type"] == "fix_code")
        assert "[PHONE]" in chat["content_redacted"]
        assert code_fix["content_redacted"] == ""


def test_missing_optional_columns_are_reported_without_aborting(tmp_path):
    engine = _build_sample_engine(tmp_path, include_optional_columns=False)
    output = tmp_path / "research.zip"
    export_research_archive(engine, output, Anonymizer(b"fixed-salt"))

    with zipfile.ZipFile(output) as archive:
        quality = json.loads(archive.read("data_quality.json"))
        assert "feedback" in quality["missing_columns"]["submissions"]
        assert len(_read_csv(archive, "submissions.csv")) == 1


def test_missing_optional_table_is_reported_and_empty_csv_is_kept(tmp_path):
    engine = _build_sample_engine(tmp_path)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE thinking_stage_logs"))

    output = tmp_path / "research.zip"
    export_research_archive(engine, output, Anonymizer(b"fixed-salt"))

    with zipfile.ZipFile(output) as archive:
        quality = json.loads(archive.read("data_quality.json"))
        assert "thinking_stage_logs" in quality["missing_tables"]
        assert _read_csv(archive, "thinking_stage_logs.csv") == []


def test_quality_report_contains_time_ranges_and_relationship_checks(tmp_path):
    engine = _build_sample_engine(tmp_path)
    output = tmp_path / "research.zip"
    export_research_archive(engine, output, Anonymizer(b"fixed-salt"))

    with zipfile.ZipFile(output) as archive:
        quality = json.loads(archive.read("data_quality.json"))
        assert quality["time_ranges"]["submissions"]["submitted_at"] == {
            "min": "2026-06-02T10:00:00",
            "max": "2026-06-02T10:00:00",
        }
        assert quality["null_counts"]["thinking_sessions"]["completed_at"] == 0
        assert quality["orphan_relationship_counts"] == {
            "submissions_without_user": 0,
            "submissions_without_assignment": 0,
            "thinking_sessions_without_user": 0,
            "thinking_sessions_without_assignment": 0,
            "thinking_logs_without_session": 0,
        }


def test_existing_output_requires_overwrite_flag(tmp_path):
    engine = _build_sample_engine(tmp_path)
    output = tmp_path / "research.zip"
    output.write_bytes(b"already here")
    with pytest.raises(FileExistsError):
        export_research_archive(engine, output, Anonymizer(b"fixed-salt"))


def test_parse_args_defaults_to_safe_text_mode():
    args = parse_args([])
    assert args.include_text is False
    assert args.overwrite is False
    assert args.output is None


def test_resolve_salt_uses_environment_value(monkeypatch):
    monkeypatch.setenv("CODE_SENSE_EXPORT_SALT", "repeatable-salt")
    assert resolve_salt() == b"repeatable-salt"


def test_resolve_salt_generates_random_value_when_environment_is_absent(monkeypatch):
    monkeypatch.delenv("CODE_SENSE_EXPORT_SALT", raising=False)
    first = resolve_salt()
    second = resolve_salt()
    assert len(first) >= 32
    assert first != second
