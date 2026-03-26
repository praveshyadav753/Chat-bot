from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Form
from uuid import uuid4
import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.tasks.ingest_document import store_rag_doc
from app.models.document import Document
from app.models.connection import get_db
from app.auth.utility import get_current_active_user
from app.core.config import settings  # S3_BUCKET, AWS_REGION pulled from here

router = APIRouter(prefix="/api/documents", tags=["Documents"])

s3_client = boto3.client("s3", region_name=settings.AWS_REGION)


@router.post("/upload")
async def upload_document(
    documents: List[UploadFile] = File(...),
    user=Depends(get_current_active_user),
    db=Depends(get_db),
    session_id: Optional[str] = Form(None),
):
    uploaded_docs = []

    for file in documents:
        file_id = str(uuid4())
        s3_key = f"uploads/{file_id}_{file.filename}"

        # ── Upload to S3 ──────────────────────────────────────────────────────
        try:
            # file_contents = await file.read()
            # s3_client.put_object(
            #     Bucket=settings.S3_BUCKET,
            #     Key=s3_key,
            #     Body=file_contents,
            #     ContentType=file.content_type or "application/octet-stream",
            # )
            s3_client.upload_fileobj(
                file.file,  # streams in chunks
                settings.S3_BUCKET,
                s3_key,
                ExtraArgs={
                    "ContentType": file.content_type or "application/octet-stream"
                },
            )
        except (BotoCoreError, ClientError) as e:
            raise HTTPException(status_code=500, detail=f"S3 upload failed: {str(e)}")

        # ── Save DB record
        new_doc = Document(
            id=file_id,
            filename=file.filename,
            file_path=s3_key,  # store S3 key, not a local path
            uploaded_by=user.id,
            access_level=user.access_level,
            department=user.department,
            status="PROCESSING",
            session_id=session_id,
        )
        db.add(new_doc)
        await db.commit()

        # ── Dispatch Celery task
        store_rag_doc.delay(
            s3_key=s3_key,
            document_id=file_id,
            session_id=session_id,
            user_id=user.id,
            access_level=user.access_level,
            department=user.department,
        )

        uploaded_docs.append(
            {
                "document_id": file_id,
                "filename": file.filename,
                "status": "PROCESSING",
            }
        )

    return {"documents": uploaded_docs}
