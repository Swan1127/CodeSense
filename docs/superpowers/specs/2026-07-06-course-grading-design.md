# Course Grading Statistics Design

## Goal

Add a teacher-facing course grading statistics page for the current course project. The score is out of 10 and should reflect real platform usage without being overly strict: students who used the system should generally receive high scores, while students with no evidence of use should receive 0.

The design must keep the grading rule isolated so it can be replaced later with a stricter policy.

## Data Sources

Use existing data only. Do not add a new score table for this version.

- `User`: student identity, class membership, teacher permissions through managed classes.
- `Submission`: formal assignment attempts, scores, submitted time.
- `Assignment`: assignment metadata and ownership.
- `ThinkingSession`: guided learning participation, stage progress, total time, start and completion time.
- `ThinkingStageLog`: interaction timestamps for guided learning sessions, used when `total_time_seconds` is missing or unreliable.

## Current Scoring Policy

Create a service module, `services/course_grading.py`, with a named policy such as `trial_usage_friendly_v1`.

Rules:

- No formal submissions and no guided learning activity: `0`.
- Any credible usage evidence: start from a high base score, around `8`.
- Formal submissions raise the score based on participated assignments, submission count, and best score.
- Guided learning activity also raises the score. A started session, recorded stage log, nonzero elapsed time, stage progress, or completed session all count as credible use.
- Students who completed guided learning or have strong formal assignment evidence should land near `9.5-10`.
- Cap all scores at `10` and round to one decimal place.

Each result should include a short reason string, for example: "完成 2 个正式作业，参与 1 次引导式学习，用时 18 分钟".

## Teacher Page

Add a teacher/admin route such as `/grades`.

Page behavior:

- Teacher sees only students in classes they manage.
- Admin can see all classes.
- Supports class filtering.
- Shows summary cards: student count, used count, unused count, average course score.
- Shows a table with student, class, formal assignment count, submission count, best formal score, guided session count, guided learning minutes, course score, and reason.

The navigation should add a teacher/admin item named "成绩统计".

## Architecture

Keep calculation separate from Flask routes and templates:

- Route gathers accessible classes and selected filters.
- Service computes per-student grading records and aggregate stats.
- Template renders records without embedding scoring rules.

This keeps later policy changes localized to `services/course_grading.py`.

## Edge Cases

- Students with only guided learning and no formal submissions still receive a high usage score.
- Guided learning sessions with `total_time_seconds = 0` can still count if they have stage logs or meaningful timestamps.
- In-progress guided learning sessions count if there is time or log evidence.
- Null formal scores are ignored for best-score calculation, but their submissions still count as usage.
- Classes with no students render an empty state instead of failing.

## Testing

Add focused tests for the grading service:

- no activity gives 0;
- formal submission only gives high score;
- guided learning only gives high score;
- completed guided learning increases score;
- score never exceeds 10;
- reason text includes both formal and guided evidence when present.

Run the existing test suite enough to catch route/import regressions.
