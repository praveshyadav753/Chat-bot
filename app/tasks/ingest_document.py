from celery.utils.log import get_task_logger
from app.models.connection import sync_session_maker
from app.REG.store.parsedoc import process_document
from app.REG.store.vec_store import store_documents
from app.celery_app import celery_app
from app.models.document import Document

logger = get_task_logger(__name__)


@celery_app.task(bind=True)
def store_rag_doc(
    self,
    file_path: str,
    document_id: str,
    user_id: int,
    session_id: str,
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

        # 🔹 Make these functions SYNC
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
            return False

        store_documents(docs)

        doc.status = "READY"
        db.commit()

        logger.warning("Document stored successfully")
        return True

    except Exception as e:
        logger.error(f"Error: {str(e)}")

        if "doc" in locals() and doc:
            doc.status = "FAILED"
            db.commit()

        raise e

    finally:
        db.close()