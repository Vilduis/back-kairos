from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Dict, Any, List

from ..services.model_service import (
    normalize_1_to_5_to_0_to_1,
    convert_0_to_1_to_1_to_5,
    predict_profile_from_text_v6,
    riasec_types,
    _get_recommendations,
)

router = APIRouter(
    prefix="",
    tags=["recommendation"],
    responses={404: {"description": "Not found"}},
)


class RIASECTestInput(BaseModel):
    R: float = Field(..., ge=1.0, le=5.0)
    I: float = Field(..., ge=1.0, le=5.0)
    A: float = Field(..., ge=1.0, le=5.0)
    S: float = Field(..., ge=1.0, le=5.0)
    E: float = Field(..., ge=1.0, le=5.0)
    C: float = Field(..., ge=1.0, le=5.0)


class ChatTextInput(BaseModel):
    texto: str = Field(..., min_length=1)


@router.post("/recomendar-por-test")
def recomendar_por_test(payload: RIASECTestInput) -> Dict[str, Any]:
    """
    Endpoint 2: Test RIASEC (perfil 1-5)
    RESTRICCIÓN: No usa modelo ni vectorizador.
    - Recibe 6 números (R, I, A, S, E, C) en escala 1-5
    - Normaliza a 0-1 con (score - 1) / 4
    - Usa recomendador interno (cosine_similarity)
    - Devuelve perfil 1-5 original y Top 3 carreras (career, score)
    """
    profile_1_to_5: Dict[str, float] = {k: round(float(getattr(payload, k)), 1) for k in riasec_types}
    profile_0_to_1 = normalize_1_to_5_to_0_to_1(profile_1_to_5)
    top3 = _get_recommendations(profile_0_to_1, top_n=3)
    return {"riasec_profile": profile_1_to_5, "top3_careers": top3}


@router.post("/recomendar-por-chat")
def recomendar_por_chat(payload: ChatTextInput) -> Dict[str, Any]:
    """
    Endpoint 1: Chat IA
    - Recibe el texto completo del chat
    - Vectoriza con el vectorizador v6
    - Predice el perfil 0-1 con el modelo v6
    - Usa recomendador interno (cosine_similarity)
    - Devuelve Top 3 carreras y el perfil convertido a 1-5
    """
    profile_0_to_1 = predict_profile_from_text_v6(payload.texto)
    profile_1_to_5 = convert_0_to_1_to_1_to_5(profile_0_to_1)
    top3 = _get_recommendations(profile_0_to_1, top_n=3)
    return {"riasec_profile": profile_1_to_5, "top3_careers": top3}