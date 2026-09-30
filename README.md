# Kairos — Backend

API REST de la plataforma de orientación vocacional Kairos: test RIASEC guiado y chat
abierto con IA generativa, perfilado con Machine Learning y recomendación de carreras.

## Stack

| Área | Tecnología |
|---|---|
| Lenguaje | Python 3.14 |
| Gestor de paquetes | uv |
| Framework | FastAPI + Pydantic v2 |
| Base de datos | PostgreSQL 18 · SQLAlchemy 2.1 · psycopg 3 · Alembic |
| Seguridad | PyJWT (HS256) · pwdlib (Argon2) |
| Machine Learning | scikit-learn (TF-IDF + RandomForest multi-salida, pipeline v8) · numpy |
| IA generativa | DeepSeek y Gemini en cadena configurable, con respaldo predefinido |
| Email | Resend |
| Calidad | ruff · pytest |

## Estructura

```
src/backend/
├── main.py            # create_app, CORS, routers, /health
├── core/              # configuración, base de datos, seguridad, excepciones
├── api/deps.py        # usuario actual y control de acceso por rol
├── modules/           # auth, users, students, evaluators, admin, assignments,
│                      # evaluations, feedback, chat, recommendation
├── ml/                # carga de artefactos, perfilado RIASEC, recomendador
├── conversation/      # prompts y heurísticas del chat abierto
├── integrations/      # proveedores LLM (DeepSeek, Gemini) y email
└── seeds/             # administradores y 36 preguntas RIASEC
migrations/            # Alembic
artifacts/             # pipeline v8 (.joblib) y catálogo de carreras (.json)
tests/
```

## Requisitos

- Python 3.14
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 18

## Puesta en marcha

```powershell
uv sync
Copy-Item .env.example .env
uv run alembic upgrade head
uv run python -m backend.seeds
uv run fastapi dev
```

- API: http://127.0.0.1:8000
- Documentación interactiva: http://127.0.0.1:8000/docs

## Comandos

| Tarea | Comando |
|---|---|
| Servidor de desarrollo | `uv run fastapi dev` |
| Servidor de producción | `uv run fastapi run` |
| Aplicar migraciones | `uv run alembic upgrade head` |
| Crear migración | `uv run alembic revision --autogenerate -m "descripcion"` |
| Cargar seeds | `uv run python -m backend.seeds` |
| Pruebas | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Formato | `uv run ruff format .` |

Las pruebas usan una base separada (`db_kairos_test`) que se crea sola y nunca llaman a
las APIs de IA.

## Roles

| Rol | Prefijo | Funciones |
|---|---|---|
| Estudiante | `/students`, `/chat` | Perfil, test guiado, chat abierto, resultados y feedback |
| Evaluador | `/evaluator` | Estudiantes asignados, sus evaluaciones, resultados y comentarios |
| Administrador | `/admin` | Usuarios, asignaciones y feedback |

Autenticación: `POST /token` (OAuth2 password) y `POST /signup`.
