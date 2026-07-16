# CodeSense Research Data Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only command-line exporter that packages anonymized CodeSense research data, schema inventory, and quality metadata into a ZIP file.

**Architecture:** Keep privacy and serialization logic in an importable module so it can be tested without starting the full Flask application. The command-line script creates the existing CodeSense app, inspects the configured SQLAlchemy database, streams selected table rows through explicit safe-field transforms, and writes CSV/JSON files into a temporary directory before creating the final ZIP.

**Tech Stack:** Python standard library, Flask 2.2, Flask-SQLAlchemy 3.0, SQLAlchemy inspector, pytest/unittest-compatible tests.

## Global Constraints

- Database access is read-only: only SQLAlchemy inspection and `SELECT` queries are permitted.
- Support the project's existing MySQL and SQLite database configurations.
- Do not add third-party dependencies.
- Default output excludes names, student numbers, email addresses, passwords, tokens, source code, feedback text, assignment text, and learning-dialogue text.
- `--include-text` may add redacted stage-one descriptions and non-code learning dialogue, but never source-code events.
- Missing optional tables or columns must be reported without aborting the remaining export.
- Existing output files are not overwritten unless `--overwrite` is provided.

---

### Task 1: Privacy and serialization helpers

**Files:**
- Create: `research_export.py`
- Test: `tests/test_research_data_export.py`

**Interfaces:**
- Produces: `Anonymizer(salt: bytes)`, `redact_text(text: str) -> str`, `text_metrics(text: str) -> dict`, `safe_json_counts(value: str, keys: tuple[str, ...]) -> dict`.
- Consumes: Python `hashlib`, `hmac`, `json`, and `re`.

- [ ] **Step 1: Write failing helper tests**

```python
from research_export import Anonymizer, redact_text, text_metrics


def test_anonymizer_is_stable_and_namespace_separated():
    anonymizer = Anonymizer(b"fixed-test-salt")
    assert anonymizer.id("user", "20240001") == anonymizer.id("user", "20240001")
    assert anonymizer.id("user", "20240001") != anonymizer.id("assignment", "20240001")
    assert "20240001" not in anonymizer.id("user", "20240001")


def test_redact_text_removes_common_identifiers():
    value = redact_text("联系 test@example.com，手机 13800138000，IP 10.0.0.8，学号 2024123456")
    assert "test@example.com" not in value
    assert "13800138000" not in value
    assert "10.0.0.8" not in value
    assert "2024123456" not in value


def test_text_metrics_do_not_return_source_text():
    metrics = text_metrics("int main() {\n\n return 0;\n}")
    assert metrics == {"char_count": 25, "nonempty_line_count": 3}
```

- [ ] **Step 2: Run tests and verify RED**

Run: `py -m pytest tests/test_research_data_export.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'research_export'`.

- [ ] **Step 3: Implement minimal helpers**

```python
class Anonymizer:
    def __init__(self, salt: bytes):
        self.salt = salt

    def id(self, namespace: str, value) -> str:
        if value is None or value == "":
            return ""
        digest = hmac.new(self.salt, f"{namespace}:{value}".encode("utf-8"), hashlib.sha256)
        return f"{namespace[:3]}_{digest.hexdigest()[:16]}"
```

Implement compiled regular expressions for email, mainland mobile number, IPv4 address, and 8-14 digit student-number-like values. Implement `text_metrics` using character count and non-empty line count. Parse JSON defensively and return counts only.

- [ ] **Step 4: Run helper tests and verify GREEN**

Run: `py -m pytest tests/test_research_data_export.py -q`

Expected: helper tests pass.

### Task 2: Database table transforms and archive writer

**Files:**
- Modify: `research_export.py`
- Modify: `tests/test_research_data_export.py`

**Interfaces:**
- Consumes: `Anonymizer`, SQLAlchemy `Engine`, output path, `include_text`, and `overwrite`.
- Produces: `export_research_archive(engine, output_path, anonymizer, include_text=False, overwrite=False) -> pathlib.Path`.

- [ ] **Step 1: Write failing SQLite integration tests**

Create a temporary SQLite database containing minimal `users`, `assignments`, `submissions`, `assignment_thinking_presets`, `thinking_sessions`, and `thinking_stage_logs` tables. Insert one linked example row in each table, including sensitive strings and source code.

```python
def test_export_archive_contains_joinable_anonymized_csv_files(tmp_path):
    engine = build_sample_engine(tmp_path)
    output = tmp_path / "research.zip"
    export_research_archive(engine, output, Anonymizer(b"salt"))

    with zipfile.ZipFile(output) as archive:
        assert set(EXPECTED_FILES) <= set(archive.namelist())
        users = read_csv(archive, "users.csv")
        submissions = read_csv(archive, "submissions.csv")
        assert users[0]["anonymous_user_id"] == submissions[0]["anonymous_user_id"]
        payload = b"".join(archive.read(name) for name in archive.namelist())
        assert b"20240001" not in payload
        assert b"password" not in payload
        assert b"int main" not in payload
```

Add separate tests for missing optional columns, default text exclusion, `--include-text` redaction, code-event text exclusion, and overwrite refusal.

- [ ] **Step 2: Run integration tests and verify RED**

Run: `py -m pytest tests/test_research_data_export.py -q`

Expected: failures show `export_research_archive` and archive constants are missing.

- [ ] **Step 3: Implement explicit table specifications**

Define CSV headers and row transformers for:

```python
EXPORT_FILES = (
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
)
```

Use `sqlalchemy.inspect(engine)` and reflected `Table` objects. For each table, select only columns that actually exist. Iterate with `result.mappings()` and write explicit safe output fields. Never serialize reflected rows wholesale.

The archive writer must:

1. Reject an existing destination unless `overwrite=True`.
2. Create intermediate files with `tempfile.TemporaryDirectory`.
3. Record missing tables and columns in `data_quality.json`.
4. Record row counts, database dialect, script version, and salt fingerprint in `manifest.json`.
5. Create the final ZIP only after every selected export has closed successfully.

- [ ] **Step 4: Run integration tests and verify GREEN**

Run: `py -m pytest tests/test_research_data_export.py -q`

Expected: all research exporter tests pass.

### Task 3: Production CLI and operator documentation

**Files:**
- Create: `scripts/export_research_dataset.py`
- Create: `docs/research_data_export.md`
- Modify: `tests/test_research_data_export.py`

**Interfaces:**
- Consumes: current CodeSense `create_app`, `models.db.engine`, `CODE_SENSE_EXPORT_SALT`, and command-line options.
- Produces: executable CLI exit code and final ZIP path.

- [ ] **Step 1: Write failing argument and main-function tests**

```python
def test_parse_args_defaults_to_safe_text_mode():
    args = parse_args([])
    assert args.include_text is False
    assert args.overwrite is False


def test_resolve_salt_uses_environment_value(monkeypatch):
    monkeypatch.setenv("CODE_SENSE_EXPORT_SALT", "repeatable-salt")
    assert resolve_salt() == b"repeatable-salt"
```

- [ ] **Step 2: Run CLI tests and verify RED**

Run: `py -m pytest tests/test_research_data_export.py -q`

Expected: import failure for `scripts.export_research_dataset`.

- [ ] **Step 3: Implement the CLI**

`scripts/export_research_dataset.py` must add the project root to `sys.path`, parse `--output`, `--output-dir`, `--include-text`, and `--overwrite`, create the app using `FLASK_CONFIG` or `development`, and call:

```python
with app.app_context():
    export_research_archive(
        db.engine,
        output_path,
        Anonymizer(resolve_salt()),
        include_text=args.include_text,
        overwrite=args.overwrite,
    )
```

Print a privacy warning when `--include-text` is enabled. Print only the final output path and aggregate file counts; never print the database URI or source identifiers.

- [ ] **Step 4: Write operator documentation**

Document Windows PowerShell and Linux commands, environment setup, default privacy behavior, stable-salt usage, ZIP contents, upload instructions, and the warning that `--include-text` requires manual privacy review.

- [ ] **Step 5: Run focused and full verification**

Run:

```powershell
py -m pytest tests/test_research_data_export.py -q
py scripts/export_research_dataset.py --output-dir research_exports
py -c "import zipfile,glob; p=sorted(glob.glob('research_exports/*.zip'))[-1]; z=zipfile.ZipFile(p); print(len(z.testzip() or ''), sorted(z.namelist()))"
```

Expected: tests pass; the script exits 0; `ZipFile.testzip()` reports no corrupt member; all ten expected files are listed.

- [ ] **Step 6: Inspect archive privacy**

Extract aggregate file names and search the ZIP payload for a known local student ID, password-field names, `DATABASE_URL`, and a known source-code snippet. Expected: no matches.

