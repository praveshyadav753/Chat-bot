import ssl
from celery import Celery
from celery.signals import worker_ready
from app.core.config import settings

celery_app = Celery(
    "chatbot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Detect if SSL is needed from URL
_use_ssl = settings.CELERY_BROKER_URL.startswith("rediss://")

_ssl_opts = {
    "ssl_keyfile": None,
    "ssl_certfile": None,
    "ssl_ca_certs": None,
    "ssl_cert_reqs": ssl.CERT_NONE,
} if _use_ssl else {}

celery_app.conf.update(
    # SSL — only applied if rediss:// URL
    broker_use_ssl=_ssl_opts or None,
    redis_backend_use_ssl=_ssl_opts or None,

    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    worker_pool="solo",
    worker_concurrency=1,

    broker_connection_timeout=10,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 3600},  # 1hr retry window

    worker_hijack_root_logger=False,
    worker_log_format="[%(asctime)s: %(levelname)s] %(message)s",
)

celery_app.conf.task_routes = {
    "app.tasks.*": {"queue": "default"},
}

celery_app.autodiscover_tasks(["app.tasks"])


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    print("[celery] warming up models...")
    from app.REG.embedding_model import get_embeddings
    from app.REG.store.vec_store import get_vectorstore
    get_embeddings()
    get_vectorstore()
    print("[celery] models ready")