import json
from pathlib import Path

import numpy as np
import pytest

from backend.core.enums import RiasecType
from backend.ml.artifacts import ModelArtifacts, get_model_artifacts
from backend.ml.profiling import RiasecProfile, profile_from_likert_sums, profile_from_text
from backend.ml.recommender import recommend_careers

DATA_DIR = Path(__file__).parent / "data"


def _load_cases(filename: str) -> list[dict]:
    return json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))["cases"]


@pytest.fixture(scope="module")
def artifacts() -> ModelArtifacts:
    return get_model_artifacts()


@pytest.fixture(scope="module")
def vectors_by_career(artifacts: ModelArtifacts) -> dict[str, np.ndarray]:
    return dict(zip((c.name for c in artifacts.careers), artifacts.career_vectors, strict=True))


def _similarity(profile: RiasecProfile, vector: np.ndarray) -> float:
    user = np.array(list(profile.values()))
    return float(user @ vector / (np.linalg.norm(user) * np.linalg.norm(vector)))


@pytest.mark.parametrize("case", _load_cases("pipeline_v8_reference.json"), ids=lambda c: c["text"])
def test_pipeline_matches_original_training_version(artifacts: ModelArtifacts, case: dict) -> None:
    profile = profile_from_text(artifacts.pipeline, case["text"])

    assert list(profile.values()) == pytest.approx(case["profile"], abs=1e-12)


@pytest.mark.parametrize("case", _load_cases("recommender_v8_reference.json"))
def test_recommender_is_equivalent_to_legacy_backend(
    artifacts: ModelArtifacts, vectors_by_career: dict[str, np.ndarray], case: dict
) -> None:
    # El legado ordenaba los empates de forma arbitraria: se exige que cada posición tenga
    # la misma similitud coseno que la carrera que devolvía el legado.
    profile = {RiasecType(key): value for key, value in case["profile"].items()}

    recommendations = recommend_careers(profile, artifacts)

    legacy = case["top_careers"]
    assert [r.score for r in recommendations] == [c["score"] for c in legacy]
    assert [_similarity(profile, vectors_by_career[r.career]) for r in recommendations] == (
        pytest.approx([_similarity(profile, vectors_by_career[c["career"]]) for c in legacy])
    )


def test_ties_follow_catalog_order(
    artifacts: ModelArtifacts, vectors_by_career: dict[str, np.ndarray]
) -> None:
    first = artifacts.career_vectors[0]
    tied = [name for name, vector in vectors_by_career.items() if (vector == first).all()]
    profile = dict(zip(RiasecType, first.tolist(), strict=True))

    recommendations = recommend_careers(profile, artifacts, top_n=len(tied))

    assert [r.career for r in recommendations] == tied


def test_text_profile_ignores_case_and_accents(artifacts: ModelArtifacts) -> None:
    plain = profile_from_text(artifacts.pipeline, "me gusta la programacion")
    accented = profile_from_text(artifacts.pipeline, "  Me gusta la PROGRAMACIÓN ")

    assert list(accented.values()) == pytest.approx(list(plain.values()), abs=1e-12)


def test_empty_text_gives_empty_profile(artifacts: ModelArtifacts) -> None:
    assert profile_from_text(artifacts.pipeline, "   ") == dict.fromkeys(RiasecType, 0.0)


@pytest.mark.parametrize(
    ("answer", "expected"),
    [(1, 0.0), (5, 1.0), (3, 0.5), (4, 0.75)],
)
def test_likert_profile_uses_full_range(answer: int, expected: float) -> None:
    sums = dict.fromkeys(RiasecType, answer * 6.0)

    assert profile_from_likert_sums(sums) == dict.fromkeys(RiasecType, expected)


def test_likert_profile_rounds_intermediate_scale_to_one_decimal() -> None:
    profile = profile_from_likert_sums(dict.fromkeys(RiasecType, 20.0))

    assert profile[RiasecType.R] == pytest.approx(0.575)
