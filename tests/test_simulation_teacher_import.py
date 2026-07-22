import pytest

from research_eval.simulation.judging import FLAG_FIELDS, RATING_DIMENSIONS
from scripts.import_simulation_teacher_ratings import merge_extracted_ratings


def completed_workbook(rater_id, packet_ids):
    rows = []
    for review_id in sorted(packet_ids):
        row = {"review_id": review_id, "comment": ""}
        row.update({name: 4 for name in RATING_DIMENSIONS})
        row.update({name: 0 for name in FLAG_FIELDS})
        rows.append(row)
    return {"rater_id": rater_id, "rows": rows}


def test_merge_requires_two_complete_independent_raters():
    packet_ids = {f"R{index:04d}" for index in range(1, 97)}
    extracted = [
        completed_workbook("teacher_1", packet_ids),
        completed_workbook("teacher_2", packet_ids),
    ]

    validated = merge_extracted_ratings(extracted, packet_ids)

    assert len(validated) == 192
    assert {row["rater_id"] for row in validated} == {"teacher_1", "teacher_2"}


def test_merge_rejects_missing_rater_id():
    packet_ids = {"R0001"}
    extracted = [
        completed_workbook("teacher_1", packet_ids),
        completed_workbook("", packet_ids),
    ]

    with pytest.raises(ValueError, match="rater_id"):
        merge_extracted_ratings(extracted, packet_ids)
