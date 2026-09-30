import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import joblib
import numpy as np
from sklearn.pipeline import Pipeline

from backend.core.config import get_settings

MODEL_VERSION = 8.0
PIPELINE_FILE = "pipeline_riasec_v8_20260427.joblib"
CAREERS_FILE = "careers_db_v8_20260427.json"


@dataclass(frozen=True, slots=True)
class Career:
    name: str
    faculty: str
    code: str


@dataclass(frozen=True, slots=True)
class ModelArtifacts:
    pipeline: Pipeline
    careers: tuple[Career, ...]
    career_vectors: np.ndarray


def load_artifacts(directory: Path) -> ModelArtifacts:
    with (directory / CAREERS_FILE).open(encoding="utf-8") as file:
        raw_careers = json.load(file)
    return ModelArtifacts(
        pipeline=joblib.load(directory / PIPELINE_FILE),
        careers=tuple(
            Career(name=item["name"], faculty=item["faculty"], code=item["code"])
            for item in raw_careers
        ),
        career_vectors=np.array([item["riasec"] for item in raw_careers], dtype=float),
    )


@cache
def get_model_artifacts() -> ModelArtifacts:
    return load_artifacts(get_settings().model_artifacts_dir)
