from celery import Celery
# import app.REG.store.process 

celery_app = Celery(
    "chatbot",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
celery_app.conf.task_routes = {
    "app.tasks.*": {"queue": "default"},
}

celery_app.autodiscover_tasks(["app.tasks"])
