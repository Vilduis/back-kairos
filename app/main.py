import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import engine, SessionLocal
from .models import Base
from .config import settings
from .routers import auth, student, admin, evaluator, chat, recommendation
from .services.model_service import init_recommender_artifacts
from .seeds import seed_riasec_questions, seed_default_admins

logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    try:
        init_recommender_artifacts()
    except Exception as e:
        logger.error(f"Error cargando artefactos del recomendador: {e}")

    if settings.DEBUG or settings.SEED_ON_STARTUP:
        db = SessionLocal()
        try:
            seed_default_admins(db)
            seed_riasec_questions(db)
        except Exception as e:
            logger.error(f"Error ejecutando seeds: {e}")
        finally:
            db.close()

    yield  # La app corre aquí
    # --- Shutdown (sin acciones necesarias) ---


app = FastAPI(title="Vocational Chatbot API", debug=settings.DEBUG, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(student.router)
app.include_router(admin.router)
app.include_router(evaluator.router)
app.include_router(chat.router)
app.include_router(recommendation.router)


@app.get("/")
def read_root():
    return {"message": "Bienvenido a la API de Kairos - Chatbot Vocacional"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
