from backend.core.enums import RiasecType
from backend.seeds.riasec_questions import _question_rows


def test_seeds_six_questions_per_dimension() -> None:
    rows = _question_rows()

    assert len(rows) == 36
    for dimension in RiasecType:
        assert sum(row["category"] == f"riasec_{dimension}" for row in rows) == 6


def test_dimensions_are_interleaved_in_display_order() -> None:
    categories = [
        row["category"] for row in sorted(_question_rows(), key=lambda r: r["display_order"])
    ]

    first_round = [f"riasec_{dimension}" for dimension in RiasecType]
    assert categories[:6] == first_round
    assert categories[6:12] == first_round
