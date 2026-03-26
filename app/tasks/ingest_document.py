import os
import tempfile
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from typing import Optional

from celery.utils.log import get_task_logger
from app.models.connection import sync_session_maker
from app.REG.store.parsedoc import process_document
from app.REG.store.vec_store import store_documents
from app.celery_app import celery_app
from app.models.document import Document
from app.redis_client import redis_client
from app.core.config import settings  # S3_BUCKET, AWS_REGION pulled from here

import json

logger = get_task_logger(__name__)

s3_client = boto3.client("s3", region_name=settings.AWS_REGION)


def publish_status(document_id: str, status: str, session_id: str, user_id: int):
    """Publish document status update to Redis."""
    payload = {
        "document_id": document_id,
        "status": status,
        "session_id": session_id,
    }
    redis_client.publish(
        f"document_status:{user_id}",
        json.dumps(payload),
    )


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def store_rag_doc(
    self,
    s3_key: str,
    document_id: str,
    user_id: int,
    session_id: Optional[str],
    access_level: int,
    department: str,
):
    db = sync_session_maker()
    tmp_path = None
    doc = None  # ← initialize early

    try:
        logger.warning("Processing document...")

        doc = db.get(Document, document_id)
        if not doc:
            logger.error("Document not found in DB")
            return False

        doc.status = "PROCESSING"
        db.commit()
        publish_status(document_id, "PROCESSING", session_id, user_id)

        # ── Download from S3 
        suffix = os.path.splitext(s3_key)[-1] or ".tmp"
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        os.close(tmp_fd)

        try:
            s3_client.download_file(settings.S3_BUCKET, s3_key, tmp_path)
        except (BotoCoreError, ClientError) as e:
            logger.error(f"S3 download failed: {s3_key} — {e}")
            try:
                raise self.retry(exc=e, countdown=2 ** self.request.retries)
            except self.MaxRetriesExceededError:
                doc.status = "FAILED"
                db.commit()
                publish_status(document_id, "FAILED", session_id, user_id)
                return False

        # ── Process document 
        docs = process_document(tmp_path, document_id, user_id, access_level, department)

        if not docs:
            doc.status = "FAILED"
            db.commit()
            publish_status(document_id, "FAILED", session_id, user_id)
            return False

        # ── Store embeddings 
        store_documents(docs)

        # ── Mark ready 
        doc.status = "READY"
        db.commit()
        publish_status(document_id, "READY", session_id, user_id)

        logger.warning("Document stored successfully")
        return True

    except Exception as e:
        logger.error(f"Unhandled error: {str(e)}")
        try:
            db.rollback()
        except Exception:
            pass
        if doc:
            doc.status = "FAILED"
            db.commit()
            publish_status(document_id, "FAILED", session_id, user_id)
        raise e

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        db.close()