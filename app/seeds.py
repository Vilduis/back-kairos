from sqlalchemy.orm import Session
from .models import Question as QuestionModel, User as UserModel
from .security import get_password_hash


def seed_riasec_questions(db: Session) -> dict:
    # Escala Likert estándar (acuerdo) para RIASEC guiado
    scale_options = {
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
    validation = {"required": True, "allowed_range": [1, 5], "integer": True}
    riasec_items = {
        "R": [
            "Armar o reparar objetos mecánicos, eléctricos o electrónicos, me resulta:",
            "Trabajar al aire libre con plantas, animales o herramientas, me resulta:",
            "Usar máquinas, herramientas o equipos en un taller o laboratorio, me resulta:",
            "Conducir vehículos o maquinaria, me resulta:",
            "Realizar actividades físicas o manuales, me resulta:",
            "Seguir instrucciones para construir o ensamblar cosas, me resulta:",
        ],
        "I": [
            "Hacer experimentos científicos, me resulta:",
            "Analizar o resolver problemas matemáticos o técnicos, me resulta:",
            "Leer sobre temas de ciencia, tecnología o naturaleza, me resulta:",
            "Investigar por qué ocurren ciertos fenómenos, me resulta:",
            "Trabajar con datos, estadísticas o gráficos, me resulta:",
            "Usar computadoras para analizar información o programar, me resulta:",
        ],
        "A": [
            "Dibujar, pintar o diseñar cosas nuevas, me resulta:",
            "Escribir historias, poemas o canciones, me resulta:",
            "Participar en obras de teatro o presentaciones, me resulta:",
            "Tocar instrumentos musicales o cantar, me resulta:",
            "Crear contenido visual o multimedia (videos, fotos, diseño), me resulta:",
            "Expresarte libremente con ideas o estilos propios, me resulta:",
        ],
        "S": [
            "Ayudar a otras personas con sus problemas o necesidades, me resulta:",
            "Enseñar, explicar o capacitar a otros, me resulta:",
            "Trabajar en equipo para lograr un objetivo común, me resulta:",
            "Cuidar a niños, adultos mayores o personas enfermas, me resulta:",
            "Escuchar y aconsejar a compañeros o amigos, me resulta:",
            "Participar en actividades de voluntariado o servicio social, me resulta:",
        ],
        "E": [
            "Liderar o coordinar grupos de trabajo, me resulta:",
            "Convencer a otros de tus ideas o productos, me resulta:",
            "Tomar decisiones rápidas y asumir responsabilidades, me resulta:",
            "Iniciar proyectos nuevos o crear tu propio negocio, me resulta:",
            "Organizar eventos o actividades escolares, me resulta:",
            "Vender productos o servicios a otras personas, me resulta:",
        ],
        "C": [
            "Ordenar archivos, documentos o datos, me resulta:",
            "Seguir procedimientos o normas con precisión, me resulta:",
            "Manejar números, planillas o registros contables, me resulta:",
            "Revisar y corregir errores en documentos, me resulta:",
            "Trabajar con computadoras en tareas administrativas, me resulta:",
            "Mantener el orden y la organización en tu entorno, me resulta:",
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
                # Si la pregunta ya existe, aseguramos que tenga el tipo y anchors correctos
                # Sin cambiar el display_order original
                try:
                    updated = False
                    if getattr(existing, "question_type", None) != "scale":
                        existing.question_type = "scale"
                        updated = True
                    # Asegurar categoría consistente (riasec_X)
                    expected_cat = f"riasec_{cat}"
                    if getattr(existing, "category", None) != expected_cat:
                        existing.category = expected_cat
                        updated = True
                    # Normalizar opciones/anchors
                    opts = getattr(existing, "options", {}) or {}
                    anchors = (opts.get("anchors") or {})
                    # Si faltan claves 2,3,4 o los textos no coinciden, sobreescribimos anchors
                    expected_anchors = scale_options["anchors"]
                    def _anchors_match(a: dict, b: dict) -> bool:
                        try:
                            return all(str(k) in a and str(a[str(k)]) == str(v) for k, v in b.items())
                        except Exception:
                            return False
                    if not _anchors_match(anchors, expected_anchors):
                        opts["anchors"] = expected_anchors
                        updated = True
                    # Asegurar rango 1-5
                    if opts.get("scale_min") != scale_options["scale_min"] or opts.get("scale_max") != scale_options["scale_max"]:
                        opts["scale_min"] = scale_options["scale_min"]
                        opts["scale_max"] = scale_options["scale_max"]
                        updated = True
                    existing.options = opts
                    # Validación
                    rules = getattr(existing, "validation_rules", {}) or {}
                    if rules.get("allowed_range") != validation["allowed_range"] or rules.get("integer") != validation["integer"]:
                        existing.validation_rules = validation
                        updated = True
                    if updated:
                        skipped += 1  # contamos como skipped (no insert) pero se actualizó
                    else:
                        skipped += 1
                    continue
                except Exception:
                    # Si algo falla en actualización, seguimos con inserción para no bloquear seed
                    pass
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
