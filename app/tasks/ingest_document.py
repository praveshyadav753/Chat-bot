import fastapi.security.utils
import logging
from app.models.connection import async_session_maker
from celery.utils.log import get_task_logger
from app.REG.store.parsedoc import process_document
import asyncio
from app.REG.store.vec_store import store_documents
from app.celery_app import celery_app
from app.models.document import Document
# from app.models.connection import get_db
# logger = logging.getLogger(__name__)


# @celery_app.task
# def store_rag_doc(file_path: str,document_id: str, user_id: int, session_id: str,access_level:int,department:str):   
#     async def run():
#         logger.warning("storing in vectore db.....")
#         docs = await process_document(file_path,document_id ,user_id, access_level,department)

#         if not docs:
#             return False

#         await store_documents(docs)
#         print("stored")
#         return True

#     return asyncio.run(run())




# if __name__ == "__main__":
#    asyncio.run( store_rag_doc("REG/llm.pdf",1,2))





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
    async def run():
        async with async_session_maker() as db:
            try:
                logger.warning("Processing document...")

                doc = await db.get(Document, document_id)
                doc.status = "PROCESSING"
                await db.commit()

                docs = await process_document(
                    file_path,
                    document_id,
                    user_id,
                    access_level,
                    department,
                )

                if not docs:
                    doc.status = "FAILED"
                    await db.commit()
                    return False

                await store_documents(docs)

                # Mark as READY
                doc.status = "READY"
                await db.commit()

                logger.warning("Document stored successfully")
                return True

            except Exception as e:
                logger.error(f"Error: {str(e)}")
                doc.status = "FAILED"
                await db.commit()
                raise e

    return asyncio.run(run())