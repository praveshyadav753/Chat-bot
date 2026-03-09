from app.REG.store.parsedoc import process_document
import asyncio
from app.REG.store.vec_store import store_documents
from app.celery_app import celery_app

@celery_app.task
def store_rag_doc(file_path: str,document_id: str, user_id: int, session_id: str,access_level:int,department:str):   
    async def run():
        docs =  process_document(file_path,document_id ,user_id, access_level,department)

        if not docs:
            return False

        store_documents(docs)
        print("stored")
        return True

    return asyncio.run(run())




if __name__ == "__main__":
   asyncio.run( store_rag_doc("REG/llm.pdf",1,2))