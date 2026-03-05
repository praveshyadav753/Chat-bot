from pydantic import BaseModel
from typing import Optional


class RetrievalQuery(BaseModel):
    query: str
    top_k: Optional[int] = None
    department: Optional[str] = None


class RetrievalUser(BaseModel):
    user_id: int
    access_level: int
    department: str
    role: str