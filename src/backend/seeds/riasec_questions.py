from itertools import chain
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.core.enums import CompatibleMode, QuestionType, RiasecType
from backend.modules.evaluations.models import Question

LIKERT_OPTIONS = {
    "scale_min": 1,
    "scale_max": 5,
    "anchors": {
        "1": "Nada interesante",
        "2": "Poco interesante",
        "3": "Neutral",
        "4": "Interesante",
        "5": "Muy interesante",
    },
}

LIKERT_VALIDATION = {"required": True, "allowed_range": [1, 5], "integer": True}

RIASEC_ITEMS: dict[RiasecType, tuple[str, ...]] = {
    RiasecType.R: (
        "Armar o reparar objetos mecánicos, eléctricos o electrónicos, me resulta:",
        "Trabajar al aire libre con plantas, animales o herramientas, me resulta:",
        "Usar máquinas, herramientas o equipos en un taller o laboratorio, me resulta:",
        "Conducir vehículos o maquinaria, me resulta:",
        "Realizar actividades físicas o manuales, me resulta:",
        "Seguir instrucciones para construir o ensamblar cosas, me resulta:",
    ),
    RiasecType.I: (
        "Hacer experimentos científicos, me resulta:",
        "Analizar o resolver problemas matemáticos o técnicos, me resulta:",
        "Leer sobre temas de ciencia, tecnología o naturaleza, me resulta:",
        "Investigar por qué ocurren ciertos fenómenos, me resulta:",
        "Trabajar con datos, estadísticas o gráficos, me resulta:",
        "Usar computadoras para analizar información o programar, me resulta:",
    ),
    RiasecType.A: (
        "Dibujar, pintar o diseñar cosas nuevas, me resulta:",
        "Escribir historias, poemas o canciones, me resulta:",
        "Participar en obras de teatro o presentaciones, me resulta:",
        "Tocar instrumentos musicales o cantar, me resulta:",
        "Crear contenido visual o multimedia (videos, fotos, diseño), me resulta:",
        "Expresarte libremente con ideas o estilos propios, me resulta:",
    ),
    RiasecType.S: (
        "Ayudar a otras personas con sus problemas o necesidades, me resulta:",
        "Enseñar, explicar o capacitar a otros, me resulta:",
        "Trabajar en equipo para lograr un objetivo común, me resulta:",
        "Cuidar a niños, adultos mayores o personas enfermas, me resulta:",
        "Escuchar y aconsejar a compañeros o amigos, me resulta:",
        "Participar en actividades de voluntariado o servicio social, me resulta:",
    ),
    RiasecType.E: (
        "Liderar o coordinar grupos de trabajo, me resulta:",
        "Convencer a otros de tus ideas o productos, me resulta:",
        "Tomar decisiones rápidas y asumir responsabilidades, me resulta:",
        "Iniciar proyectos nuevos o crear tu propio negocio, me resulta:",
        "Organizar eventos o actividades escolares, me resulta:",
        "Vender productos o servicios a otras personas, me resulta:",
    ),
    RiasecType.C: (
        "Ordenar archivos, documentos o datos, me resulta:",
        "Seguir procedimientos o normas con precisión, me resulta:",
        "Manejar números, planillas o registros contables, me resulta:",
        "Revisar y corregir errores en documentos, me resulta:",
        "Trabajar con computadoras en tareas administrativas, me resulta:",
        "Mantener el orden y la organización en tu entorno, me resulta:",
    ),
}


def _question_rows() -> list[dict[str, Any]]:
    # Se intercalan las dimensiones (R, I, A, S, E, C, R, ...) para que el test guiado
    # no agrupe preguntas de un mismo tipo y reduzca el sesgo por fatiga.
    tagged = ([(dimension, text) for text in texts] for dimension, texts in RIASEC_ITEMS.items())
    interleaved = chain.from_iterable(zip(*tagged, strict=True))
    return [
        {
            "question_text": text,
            "question_type": QuestionType.SCALE,
            "category": f"riasec_{dimension}",
            "display_order": order,
            "options": LIKERT_OPTIONS,
            "validation_rules": LIKERT_VALIDATION,
            "compatible_modes": CompatibleMode.GUIDED,
        }
        for order, (dimension, text) in enumerate(interleaved, start=1)
    ]


def seed_riasec_questions(session: Session) -> int:
    statement = (
        insert(Question)
        .values(_question_rows())
        .on_conflict_do_nothing(index_elements=[Question.question_text])
        .returning(Question.question_id)
    )
    return len(session.scalars(statement).all())
