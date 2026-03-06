from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.user import User

from app.models.connection import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, index=True)

    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)

    uploaded_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    access_level = Column(Integer, nullable=False)
    department = Column(String(40), nullable=False)

    status = Column(String(20), default="PROCESSING", nullable=False)

    session_id = Column(String, ForeignKey("chat_sessions.id"))

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="documents")