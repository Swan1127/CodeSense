from __future__ import annotations

import argparse
import importlib
import json
import os
import secrets
import tempfile
from pathlib import Path
from typing import Any, Callable


CONFIRM_LITERAL = "CREATE_RESEARCH_LOAD_USERS"
MAX_USERS = 32
DEDICATED_CLASS_NAME = "research_load_test"


class CredentialPublishError(RuntimeError):
    """Credential publication failed without leaving committed unknown passwords."""


class CredentialRecoveryError(CredentialPublishError):
    """Committed users remain; a secure staged credential file must be recovered."""

    def __init__(self, recovery_path: Path):
        self.recovery_path = recovery_path
        super().__init__(
            "credential publication and database compensation failed; "
            f"recover credentials from {recovery_path}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provision isolated research_load_ accounts for guarded load evaluation."
    )
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--count", required=True, type=int)
    parser.add_argument("--assignment-id", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--config", default=os.getenv("FLASK_CONFIG", "development"))
    return parser


def validate_provision_request(
    *, prefix: str, count: int, assignment_id: int, output: str | Path, confirm: str
) -> Path:
    if not isinstance(prefix, str) or not prefix.startswith("research_load_"):
        raise ValueError("prefix must start with research_load_")
    if not isinstance(count, int) or isinstance(count, bool) or count != MAX_USERS:
        raise ValueError("count must be exactly 32")
    if not isinstance(assignment_id, int) or isinstance(assignment_id, bool) or assignment_id < 1:
        raise ValueError("assignment ID must be a positive integer")
    if confirm != CONFIRM_LITERAL:
        raise ValueError(f"--confirm must equal {CONFIRM_LITERAL}")
    output_path = Path(output).expanduser().resolve()
    _require_path_outside_git(output_path)
    return output_path


def provision_users(
    *,
    db: Any,
    User: Any,
    Assignment: Any,
    AssignmentThinkingPreset: Any,
    prefix: str,
    count: int,
    assignment_id: int,
    output: str | Path,
    password_factory: Callable[[], str] = lambda: secrets.token_urlsafe(24),
) -> dict[str, object]:
    if not prefix.startswith("research_load_"):
        raise ValueError("prefix must start with research_load_")
    if not isinstance(count, int) or isinstance(count, bool) or count != MAX_USERS:
        raise ValueError("count must be exactly 32")
    if assignment_id < 1:
        raise ValueError("assignment ID must be a positive integer")
    output_path = Path(output).expanduser().resolve()

    assignment = Assignment.query.get(assignment_id)
    if assignment is None:
        raise ValueError("assignment does not exist")
    preset = AssignmentThinkingPreset.query.filter_by(assignment_id=assignment_id).first()
    if preset is None or preset.status != "ready":
        raise ValueError("assignment must have a ready AssignmentThinkingPreset")

    saved = _read_existing_credentials(output_path)
    saved_by_username = {item["username"]: item["password"] for item in saved}
    credentials: list[dict[str, str]] = []
    newly_created: list[Any] = []
    existing_count = 0

    width = max(2, len(str(count)))
    expected_usernames = {
        f"{prefix}{index:0{width}d}" for index in range(1, count + 1)
    }
    if set(saved_by_username) - expected_usernames:
        raise ValueError(
            "existing credentials contain a username outside the expected 32-account namespace"
        )
    for index in range(1, count + 1):
        username = f"{prefix}{index:0{width}d}"
        if len(username) > 20:
            raise ValueError("prefix is too long for the student_id field")
        existing = User.query.filter_by(username=username).first()
        if existing is not None:
            password = saved_by_username.get(username)
            if not password:
                raise ValueError(
                    f"existing credentials are required for existing account {username}"
                )
            _validate_existing_user(existing, username, password)
            existing_count += 1
        else:
            password = saved_by_username.get(username) or password_factory()
            if not isinstance(password, str) or not password:
                raise ValueError("password generator returned an empty password")
            user = User(
                student_id=username,
                username=username,
                usertype="学生",
                class_name=DEDICATED_CLASS_NAME,
                full_name=f"Research Load {index:0{width}d}",
            )
            user.password = password
            newly_created.append(user)
        credentials.append({"username": username, "password": password})

    try:
        staged_path = _stage_credentials(output_path, credentials)
    except Exception as exc:
        raise CredentialPublishError("failed to stage secure credentials") from exc

    try:
        for user in newly_created:
            db.session.add(user)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        _remove_staged_credentials(staged_path)
        raise CredentialPublishError("database commit failed before credential publication") from exc

    try:
        _replace_staged_credentials(staged_path, output_path)
    except Exception as replace_error:
        if not newly_created:
            _remove_staged_credentials(staged_path)
            raise CredentialPublishError("credential replace failed; database was unchanged") from replace_error
        try:
            for user in newly_created:
                db.session.delete(user)
            db.session.commit()
        except Exception as compensation_error:
            db.session.rollback()
            raise CredentialRecoveryError(staged_path) from compensation_error
        _remove_staged_credentials(staged_path)
        raise CredentialPublishError(
            "credential replace failed; newly created users were compensated"
        ) from replace_error

    return {
        "created": len(newly_created),
        "existing": existing_count,
        "output": str(output_path),
    }


def _read_existing_credentials(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("existing credentials file must contain valid JSON") from exc
    if not isinstance(value, list):
        raise ValueError("existing credentials file must contain a JSON list")
    result = []
    seen = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("existing credentials entries must be objects")
        username = item.get("username")
        password = item.get("password")
        if not isinstance(username, str) or not username.startswith("research_load_"):
            raise ValueError("existing credentials usernames must start with research_load_")
        if not isinstance(password, str) or not password:
            raise ValueError("existing credentials entries must contain passwords")
        if username in seen:
            raise ValueError("existing credentials contain a duplicate username")
        seen.add(username)
        result.append({"username": username, "password": password})
    return result


def _validate_existing_user(user: Any, username: str, saved_password: str) -> None:
    if getattr(user, "username", None) != username:
        raise ValueError(f"existing account {username} has a mismatched username")
    if getattr(user, "student_id", None) != username:
        raise ValueError(f"existing account {username} has a mismatched student_id")
    if getattr(user, "usertype", None) != "学生":
        raise ValueError(f"existing account {username} is not a student")
    if getattr(user, "class_name", None) != DEDICATED_CLASS_NAME:
        raise ValueError(f"existing account {username} has a mismatched class_name")
    verifier = getattr(user, "verify_password", None)
    try:
        password_matches = callable(verifier) and verifier(saved_password)
    except Exception:
        password_matches = False
    if not password_matches:
        raise ValueError(f"existing account {username} password does not match saved credentials")


def _stage_credentials(path: Path, credentials: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            os.chmod(temporary_path, 0o600)
            json.dump(credentials, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, 0o600)
        return temporary_path
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise


def _replace_staged_credentials(staged_path: Path, output_path: Path) -> None:
    os.replace(staged_path, output_path)


def _remove_staged_credentials(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _require_path_outside_git(path: Path) -> None:
    for parent in (path.parent, *path.parents):
        if (parent / ".git").exists():
            raise ValueError("credentials output must be outside the Git worktree")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = validate_provision_request(
        prefix=args.prefix,
        count=args.count,
        assignment_id=args.assignment_id,
        output=args.output,
        confirm=args.confirm,
    )

    os.environ["FLASK_CONFIG"] = args.config
    app_module = importlib.import_module("app")
    models_module = importlib.import_module("models")
    app = app_module.app
    with app.app_context():
        result = provision_users(
            db=models_module.db,
            User=models_module.User,
            Assignment=models_module.Assignment,
            AssignmentThinkingPreset=models_module.AssignmentThinkingPreset,
            prefix=args.prefix,
            count=args.count,
            assignment_id=args.assignment_id,
            output=output,
        )
    print(
        "Research load users provisioned: "
        f"created={result['created']}, existing={result['existing']}, output={result['output']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
