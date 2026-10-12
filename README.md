# Kairos — Backend

API de Kairos, la plataforma de orientación vocacional para colegios del Perú. Recibe las
respuestas del estudiante, calcula su perfil RIASEC, le recomienda carreras y controla qué
puede ver y hacer cada persona del colegio.

Producción: https://back-kairos.onrender.com (documentación interactiva en `/docs`)

## Cómo funciona

El estudiante llega a su perfil por uno de dos caminos:

- **Test guiado:** 36 preguntas de escala del 1 al 5, seis por cada dimensión RIASEC e
  intercaladas para no agruparlas. La suma por dimensión se lleva a una escala de 0 a 1.
- **Chat abierto:** la IA generativa (DeepSeek, con Gemini de respaldo) conduce la
  conversación y hace las preguntas. Cuando el estudiante ya dio suficientes señales sobre sus
  gustos, un modelo propio de Machine Learning (TF-IDF + RandomForest multi-salida, pipeline
  v8) convierte todo lo que escribió en su perfil. Si ningún proveedor de IA responde, el chat
  sigue con preguntas predefinidas.

Con el perfil, el recomendador compara al estudiante con un catálogo de **60 carreras en
13 facultades** por similitud coseno y devuelve las 3 más afines. Cada una trae una
explicación calculada con los datos, sin IA generativa: el código Holland de la carrera,
en qué letras coincide con los tres intereses más altos del estudiante (con sus porcentajes)
y qué letras pide la carrera que en él están más bajas.

## Roles y permisos

| Rol                                           | Puede                                                                                                                               |
| --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Estudiante** (`student`)                    | Aceptar el consentimiento, hacer el test o el chat, ver sus resultados y las observaciones de su orientador, valorar la plataforma. |
| **Orientador** (`evaluator`)                  | Ver los resultados de sus estudiantes asignados y escribir, editar y borrar sus propias observaciones.                              |
| **Administrador de colegio** (`school_admin`) | Gestionar estudiantes y orientadores de su colegio, generar códigos de acceso, asignar estudiantes y ver el resumen del colegio.    |
| **Equipo Kairos** (`admin`)                   | Todo lo anterior en cualquier colegio, además de crear colegios y administradores y leer la valoración de la plataforma.            |

Las reglas se aplican en el servidor, no solo en la interfaz:

- Cada colegio está aislado: un usuario o recurso de otro colegio responde igual que uno que
  no existe.
- El orientador nunca ve lo que el estudiante escribió en el chat ni lo que marcó en el test,
  solo el perfil y las carreras.
- El estudiante se registra con el código de acceso de su colegio (con vencimiento y número
  de usos opcionales) y no puede empezar el test ni el chat sin aceptar el consentimiento
  vigente.

## Tecnología

- **Python 3.14**, **FastAPI** y Pydantic v2, con **uv** como gestor de paquetes.
- **PostgreSQL 18** con SQLAlchemy 2.1 y migraciones de **Alembic**.
- Autenticación con JWT (PyJWT) y contraseñas con Argon2 (pwdlib).
- **scikit-learn** y numpy para el modelo y el recomendador; los artefactos viven en
  `artifacts/`.
- DeepSeek y Gemini en una cadena configurable para el chat abierto.
- **Resend** para la recuperación de contraseña y el formulario de contacto.
- **ruff** para lint y formato.

Todos los mensajes que devuelve la API están en español. El producto está documentado en
`../design_kairos/PRODUCT.md`.

## Puesta en marcha

Requisitos: Python 3.14, [uv](https://docs.astral.sh/uv/) y PostgreSQL 18.

```bash
uv sync
cp .env.example .env
uv run alembic upgrade head
uv run python -m backend.seeds
uv run fastapi dev
```

La API queda en http://127.0.0.1:8000 y su documentación en http://127.0.0.1:8000/docs. Los
seeds cargan las 36 preguntas del test y los administradores de `SEED_ADMINS`; se pueden
volver a ejecutar sin duplicar datos.

Variables de entorno (`.env`):

| Variable                                              | Uso                                                                                    |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `DATABASE_URL`                                        | Conexión a PostgreSQL                                                                  |
| `SECRET_KEY`                                          | Clave para firmar los tokens                                                           |
| `CORS_ORIGINS`, `FRONTEND_URL`                        | Origen del frontend y base de los enlaces de recuperación de contraseña                |
| `SEED_ADMINS`                                         | Cuentas del equipo Kairos que crean los seeds                                          |
| `RESEND_API_KEY`, `RESEND_FROM`                       | Envío de correos; sin clave, los correos se omiten                                     |
| `CONTACT_EMAIL`                                       | Destino de los mensajes del formulario de contacto                                     |
| `LLM_PROVIDERS`, `DEEPSEEK_API_KEY`, `GEMINI_API_KEY` | Orden de los proveedores de IA y sus claves; sin claves se usan preguntas predefinidas |

`.env.example` trae el resto con sus valores por defecto.

## Comandos

| Comando                                                   | Uso                               |
| --------------------------------------------------------- | --------------------------------- |
| `uv run fastapi dev`                                      | Servidor de desarrollo            |
| `uv run fastapi run`                                      | Servidor de producción            |
| `uv run alembic upgrade head`                             | Aplica las migraciones            |
| `uv run alembic revision --autogenerate -m "descripcion"` | Crea una migración                |
| `uv run python -m backend.seeds`                          | Carga preguntas y administradores |
| `uv run ruff check .` / `uv run ruff format .`            | Lint y formato                    |

## Equipo

Proyecto de tesis de Vilder Sandoval (backend, IA y arquitectura) y Katerin Penadillo
(frontend y UX).
