from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.models.connection import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True)

    session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=False)

    role = Column(String, nullable=False)  
    # user | assistant | system | tool

    content = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())