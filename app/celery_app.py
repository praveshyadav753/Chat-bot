from celery import Celery
# import app.REG.store.process 
from app.core.config import settings
from celery.signals import worker_ready

@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Pre-load models when worker starts — not on each task."""
    print("[celery] warming up models...")
    from app.REG.embedding_model import get_embeddings
    from app.REG.store.vec_store import get_vectorstore
    get_embeddings()      # loads once into this worker's memory
    get_vectorstore()     # loads once
    print("[celery] models ready")


celery_app = Celery(
    "chatbot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_pool="solo",
    worker_concurrency=1,
)
celery_app.conf.task_routes = {
    "app.tasks.*": {"queue": "default"},
}

celery_app.autodiscover_tasks(["app.tasks"])
