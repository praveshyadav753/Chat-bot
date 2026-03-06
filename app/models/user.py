from sqlalchemy import (
    Column, Integer, String, Boolean,
    DateTime, Enum, Text
)
from sqlalchemy.orm import relationship
from .connection import Base
from sqlalchemy.sql import func
import enum



class UserRole(str, enum.Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"



class User(Base):
    __tablename__ = "users"

   
    id = Column(Integer, primary_key=True, index=True)

    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)

    hashed_password = Column(String(255), nullable=False)

    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    access_level =Column(Integer ,default=1,nullable=False)
    department =Column(String(40),default="general" ,nullable=False )

    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)

    failed_login_attempts = Column(Integer, default=0)
    last_login_at = Column(DateTime(timezone=True))
    password_changed_at = Column(DateTime(timezone=True))

    first_name = Column(String(100))
    last_name = Column(String(100))
    profile_image = Column(Text)

    is_deleted = Column(Boolean, default=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    documents = relationship("Document", back_populates="user")

    def __repr__(self):
        return f"<User id={self.id} email={self.email} role={self.role}>"