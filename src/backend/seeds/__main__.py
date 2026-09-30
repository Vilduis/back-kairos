import logging

import backend.models  # noqa: F401
from backend.core.database import SessionLocal
from backend.seeds.admins import seed_admins
from backend.seeds.riasec_questions import seed_riasec_questions

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with SessionLocal.begin() as session:
        questions = seed_riasec_questions(session)
        admins = seed_admins(session)
    logger.info("Preguntas RIASEC insertadas: %d", questions)
    logger.info("Administradores insertados: %d", admins)


if __name__ == "__main__":
    main()
