from celery import Celery

from app.core.config import settings

celery_app = Celery("credroute", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_routes = {"app.workers.tasks.*": {"queue": "lender_evaluation_queue"}}


@celery_app.task(name="app.workers.tasks.evaluate_application_async")
def evaluate_application_async(payload: dict, idempotency_key: str | None) -> dict:
    import asyncio

    from app.application.evaluate_application import EvaluateApplicationUseCase
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        response, replay = asyncio.run(EvaluateApplicationUseCase(db).execute(payload, idempotency_key))
        return {**response, "idempotentReplay": replay}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.reconcile_unknown_attempts")
def reconcile_unknown_attempts_task(limit: int = 50) -> dict:
    from app.db.session import SessionLocal
    from app.services.reconciliation import reconcile_unknown_attempts

    db = SessionLocal()
    try:
        return reconcile_unknown_attempts(db, limit=limit)
    finally:
        db.close()
