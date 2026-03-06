from typing import List
from fastapi import APIRouter, UploadFile, File, Depends
from uuid import uuid4
import os
import aiofiles

from app.tasks.ingest_document import store_rag_doc
from app.models.document import Document
from app.models.connection import get_db
from app.auth.utility import get_current_active_user

router = APIRouter(prefix="/api/documents", tags=["Documents"])

UPLOAD_DIR = "uploads"


@router.post("/upload")
async def upload_document(
    documents: List[UploadFile] = File(...),
    user=Depends(get_current_active_user),
    db=Depends(get_db)
):

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    uploaded_docs = []

    for file in documents:

        file_id = str(uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")

        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                await f.write(chunk)

        new_doc = Document(
            id=file_id,
            filename=file.filename,
            file_path=file_path,
            uploaded_by=user.id,
            access_level=user.access_level,
            department=user.department,
            status="PROCESSING",
        )

        db.add(new_doc)
        await db.commit()

        store_rag_doc.delay(
            file_path=file_path,
            document_id=file_id,
            session_id="None",
            user_id=user.id,
            access_level=user.access_level,
            department=user.department,
        )

        uploaded_docs.append({
            "document_id": file_id,
            "filename": file.filename,
            "status": "PROCESSING"
        })

    return {
        "documents": uploaded_docs
    }