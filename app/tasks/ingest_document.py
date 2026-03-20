import os

from celery.utils.log import get_task_logger
from app.models.connection import sync_session_maker
from app.REG.store.parsedoc import process_document
from app.REG.store.vec_store import store_documents
from app.celery_app import celery_app
from app.models.document import Document
from typing import Optional
from app.redis_client import redis_client

import json

logger = get_task_logger(__name__)

# Redis client for pub/sub
# redis_client = redis.Redis(host="localhost", port=6379, db=0)


def publish_status(document_id: str, status: str, session_id: str, user_id: int):
    """
    Publish document status update to Redis
    """
    payload = {
        "document_id": document_id,
        "status": status,
        "session_id": session_id,
    }

    redis_client.publish(
        f"document_status:{user_id}",
        # "document_status",
        json.dumps(payload),
    )


@celery_app.task(bind=True)
def store_rag_doc(
    self,
    file_path: str,
    document_id: str,
    user_id: int,
    session_id: Optional[str],
    access_level: int,
    department: str,
):
    db = sync_session_maker()

    try:
        logger.warning("Processing document...")

        doc = db.get(Document, document_id)
        if not doc:
            logger.error("Document not found in DB")
            return False

        doc.status = "PROCESSING"
        db.commit()

        publish_status(
            document_id, "PROCESSING", session_id=session_id, user_id=user_id
        )

        docs = process_document(
            file_path,
            document_id,
            user_id,
            access_level,
            department,
        )

        if not docs:
            doc.status = "FAILED"
            db.commit()
            try:
                os.remove(file_path)
            except:
                pass
            publish_status(document_id, "FAILED", session_id, user_id=user_id)
            return False

        #  Store embeddings
        store_documents(docs)

        #  Mark ready
        doc.status = "READY"
        db.commit()

        publish_status(document_id, "READY", session_id, user_id=user_id)

        logger.warning("Document stored successfully")
        return True

    except Exception as e:
        logger.error(f"Error: {str(e)}")

        if "doc" in locals() and doc:
            doc.status = "FAILED"
            db.commit()

            publish_status(document_id, "FAILED", session_id, user_id=user_id)

        raise e

    finally:
        db.close()
