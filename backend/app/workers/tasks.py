from celery import Celery

from app.core.config import settings

celery_app = Celery("credroute", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_routes = {"app.workers.tasks.*": {"queue": "lender_evaluation_queue"}}


@celery_app.task(name="app.workers.tasks.evaluate_application_async")
def evaluate_application_async(payload: dict, idempotency_key: str | None) -> dict:
    import asyncio

    from app.db.session import SessionLocal
    from app.services.application_service import evaluate_application

    db = SessionLocal()
    try:
        response, replay = asyncio.run(evaluate_application(db, payload, idempotency_key))
        return {**response, "idempotentReplay": replay}
    finally:
        db.close()
