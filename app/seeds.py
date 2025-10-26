from sqlalchemy.orm import Session
from .models import Question as QuestionModel, User as UserModel
from .security import get_password_hash


def seed_riasec_questions(db: Session) -> dict:
    scale_options = {
        "scale_min": 1,
        "scale_max": 5,
        "anchors": {"1": "Nada interesado", "5": "Muy interesado"},
    }
    validation = {"required": True, "allowed_range": [1, 5], "integer": True}
    riasec_items = {
        "R": [
            "Armar o reparar objetos mecánicos, eléctricos o electrónicos.",
            "Trabajar al aire libre con plantas, animales o herramientas.",
            "Usar máquinas, herramientas o equipos en un taller o laboratorio.",
            "Conducir vehículos o maquinaria.",
            "Realizar actividades físicas o manuales.",
            "Seguir instrucciones para construir o ensamblar cosas.",
        ],
        "I": [
            "Hacer experimentos científicos.",
            "Analizar o resolver problemas matemáticos o técnicos.",
            "Leer sobre temas de ciencia, tecnología o naturaleza.",
            "Investigar por qué ocurren ciertos fenómenos.",
            "Trabajar con datos, estadísticas o gráficos.",
            "Usar computadoras para analizar información o programar.",
        ],
        "A": [
            "Dibujar, pintar o diseñar cosas nuevas.",
            "Escribir historias, poemas o canciones.",
            "Participar en obras de teatro o presentaciones.",
            "Tocar instrumentos musicales o cantar.",
            "Crear contenido visual o multimedia (videos, fotos, diseño).",
            "Expresarte libremente con ideas o estilos propios.",
        ],
        "S": [
            "Ayudar a otras personas con sus problemas o necesidades.",
            "Enseñar, explicar o capacitar a otros.",
            "Trabajar en equipo para lograr un objetivo común.",
            "Cuidar a niños, adultos mayores o personas enfermas.",
            "Escuchar y aconsejar a compañeros o amigos.",
            "Participar en actividades de voluntariado o servicio social.",
        ],
        "E": [
            "Liderar o coordinar grupos de trabajo.",
            "Convencer a otros de tus ideas o productos.",
            "Tomar decisiones rápidas y asumir responsabilidades.",
            "Iniciar proyectos nuevos o crear tu propio negocio.",
            "Organizar eventos o actividades escolares.",
            "Vender productos o servicios a otras personas.",
        ],
        "C": [
            "Ordenar archivos, documentos o datos.",
            "Seguir procedimientos o normas con precisión.",
            "Manejar números, planillas o registros contables.",
            "Revisar y corregir errores en documentos.",
            "Trabajar con computadoras en tareas administrativas.",
            "Mantener el orden y la organización en tu entorno.",
        ],
    }

    inserted = 0
    skipped = 0
    display_order = 1

    for i in range(6):
        for cat in ["R", "I", "A", "S", "E", "C"]:
            text = riasec_items[cat][i]
            existing = (
                db.query(QuestionModel)
                .filter(QuestionModel.question_text == text)
                .first()
            )
            if existing:
                skipped += 1
                continue
            q = QuestionModel(
                question_text=text,
                question_type="scale",
                category=f"riasec_{cat}",
                display_order=display_order,
                options=scale_options,
                validation_rules=validation,
                compatible_modes="guided",
            )
            db.add(q)
            inserted += 1
            display_order += 1

    db.commit()
    return {"inserted": inserted, "skipped": skipped}


def seed_default_admins(db: Session) -> dict:
    import os

    admins = [
        {
            "full_name": os.getenv("ADMIN_FULL_NAME", "Admin"),
            "email": os.getenv("ADMIN_EMAIL", "kairos@gmail.com"),
        },
        {
            "full_name": os.getenv("ADMIN_LUIS_FULL_NAME", "Luis Admin"),
            "email": os.getenv("ADMIN_LUIS_EMAIL", "luis@gmail.com"),
        },
        {
            "full_name": os.getenv("ADMIN_KETY_FULL_NAME", "Katy Admin"),
            "email": os.getenv("ADMIN_KETY_EMAIL", "katy@gmail.com"),
        },
    ]
    password = os.getenv("ADMIN_PASSWORD", "#KV202502")

    results = []
    for adm in admins:
        email = adm["email"]
        full_name = adm["full_name"]
        if not email:
            continue
        existing = db.query(UserModel).filter(UserModel.email == email).first()
        if existing:
            results.append(
                {
                    "email": email,
                    "created": False,
                    "user_id": existing.user_id,
                    "reason": "exists",
                }
            )
            continue
        admin = UserModel(
            full_name=full_name,
            email=email,
            password_hash=get_password_hash(password),
            role="admin",
            educational_institution=None,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        results.append({"email": email, "created": True, "user_id": admin.user_id})

    inserted = sum(1 for r in results if r.get("created"))
    skipped = len(results) - inserted
    return {"inserted": inserted, "skipped": skipped, "details": results}
