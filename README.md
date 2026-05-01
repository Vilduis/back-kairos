# Kairos — API

API REST para la plataforma de orientación vocacional Kairos. Evalúa los intereses, habilidades y valores de estudiantes mediante el modelo RIASEC y recomienda carreras profesionales usando Machine Learning e inteligencia artificial generativa.

---

## ¿Qué hace?

- Gestiona sesiones de chat en dos modos: **guiado** (preguntas estructuradas) y **abierto** (conversación libre con IA).
- En el modo abierto, utiliza **Google Gemini** para generar preguntas de seguimiento naturales y detectar señales vocacionales en el texto.
- Analiza las respuestas con un modelo ML (TF-IDF + RIASEC) y genera scores para los seis perfiles Holland (R, I, A, S, E, C).
- Recomienda las tres carreras más afines usando similitud de coseno contra una base de datos de carreras.
- Provee paneles diferenciados para **estudiantes**, **evaluadores** y **administradores**.
- Envía correos transaccionales para recuperación de contraseña.

---

## Stack

| Área | Tecnología |
|---|---|
| Framework | FastAPI 0.115 + Uvicorn |
| Lenguaje | Python 3.11+ |
| Base de datos | PostgreSQL + SQLAlchemy 2 + Alembic |
| Autenticación | JWT (python-jose) + bcrypt |
| Machine Learning | scikit-learn, TF-IDF, cosine similarity |
| IA Generativa | Google Gemini (google-genai SDK) |
| Validación | Pydantic v2 |
| Email | Resend / SMTP |

---

## Módulos principales

- **Auth** — Registro, login, JWT y recuperación de contraseña por email.
- **Chat** — Creación y gestión de sesiones, flujo conversacional (guiado y abierto) y obtención de resultados.
- **Students** — Perfil del estudiante, historial de evaluaciones y feedback sobre resultados.
- **Evaluators** — Revisión de evaluaciones asignadas y adición de comentarios.
- **Admin** — Gestión completa de usuarios y asignación de estudiantes a evaluadores.
- **Recommendation** — Generación de recomendaciones de carrera a partir del test o del texto del chat.

---

## Configuración local

```bash
# Crear entorno virtual e instalar dependencias
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar DATABASE_URL, SECRET_KEY, GEMINI_API_KEY, etc.

# Iniciar servidor
uvicorn app.main:app --reload
```

La documentación interactiva estará disponible en `/docs` una vez iniciado el servidor.

---

## Variables de entorno requeridas

```env
DATABASE_URL=postgresql+psycopg://user:password@host:5432/db
SECRET_KEY=tu_clave_secreta
GEMINI_API_KEY=tu_api_key_de_google
FRONTEND_URL=http://localhost:3000
```
