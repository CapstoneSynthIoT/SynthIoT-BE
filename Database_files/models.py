import uuid
from sqlalchemy import Column, String, Text, Integer, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.sql import func
from .database import Base


class User(Base):
    __tablename__ = "users"

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone_num = Column(String)
    password = Column(String, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    location = Column(String)
    bio = Column(Text)


class Project(Base):
    __tablename__ = "projects"

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.uuid"), nullable=False)
    title = Column(String, nullable=False)
    icon = Column(String)
    prompt = Column(Text)
    created_on = Column(TIMESTAMP, server_default=func.now())
    last_active = Column(TIMESTAMP, onupdate=func.now())
    tags = Column(ARRAY(String))
    datapoints_count = Column(Integer, default=0)
    csv_link = Column(String)
