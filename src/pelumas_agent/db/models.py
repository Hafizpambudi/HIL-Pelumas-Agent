import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from pelumas_agent.config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class EmbeddingType(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(get_settings().embed_dim))
        return dialect.type_descriptor(JSON())


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "product"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    part_no: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    slug: Mapped[str | None] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    brand: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(120))
    description_id: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    data_confidence: Mapped[str] = mapped_column(String(10), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="active")
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    embedding = mapped_column(EmbeddingType, nullable=True)

    specs: Mapped[list["Spec"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class Spec(Base):
    __tablename__ = "spec"
    __table_args__ = (UniqueConstraint("product_id", "key", name="uq_spec_product_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(60))
    value_num: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(String(255))
    unit: Mapped[str | None] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(20), default="site")
    confidence: Mapped[str] = mapped_column(String(10), default="medium")

    product: Mapped[Product] = relationship(back_populates="specs")


class FitmentRule(Base):
    __tablename__ = "fitment_rule"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    category: Mapped[str] = mapped_column(String(60))
    dimension: Mapped[str] = mapped_column(String(60))
    relation: Mapped[str] = mapped_column(String(20))
    threshold: Mapped[dict] = mapped_column(JSON, default=dict)
    rationale: Mapped[str] = mapped_column(Text)
    verified_by: Mapped[str | None] = mapped_column(String(120))


class Equivalence(Base):
    __tablename__ = "equivalence"
    __table_args__ = (UniqueConstraint("a_product_id", "b_product_id", name="uq_equiv_pair"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    a_product_id: Mapped[str] = mapped_column(ForeignKey("product.id"), index=True)
    b_product_id: Mapped[str] = mapped_column(ForeignKey("product.id"), index=True)
    relation: Mapped[str] = mapped_column(String(20))
    differing_dims: Mapped[dict] = mapped_column(JSON, default=dict)
    verified_by: Mapped[str | None] = mapped_column(String(120))
    confidence: Mapped[str] = mapped_column(String(10), default="low")


class Conversation(Base):
    __tablename__ = "conversation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    wa_thread_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    buyer_phone: Mapped[str] = mapped_column(String(32), index=True)
    buyer_type: Mapped[str] = mapped_column(String(20), default="unknown")
    stage: Mapped[str] = mapped_column(String(30), default="NEW")
    paused: Mapped[bool] = mapped_column(default=False)
    state_json: Mapped[dict] = mapped_column(JSON, default=dict)
    assigned_admin: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Rfq(Base):
    __tablename__ = "rfq"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversation.id"), index=True)
    company: Mapped[str | None] = mapped_column(String(255))
    contact_name: Mapped[str | None] = mapped_column(String(255))
    buyer_type: Mapped[str] = mapped_column(String(20), default="unknown")
    items: Mapped[list] = mapped_column(JSON, default=list)
    delivery_city: Mapped[str | None] = mapped_column(String(120))
    urgency: Mapped[str | None] = mapped_column(String(60))
    open_questions: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    admin_note: Mapped[str | None] = mapped_column(Text)
    quoted_total: Mapped[str | None] = mapped_column(String(120))
    quoted_by: Mapped[str | None] = mapped_column(String(32))
    quoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Event(Base):
    __tablename__ = "event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), index=True)
    type: Mapped[str] = mapped_column(String(30), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class ProcessedMessage(Base):
    __tablename__ = "processed_message"

    wamid: Mapped[str] = mapped_column(String(128), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AvailabilityCheck(Base):
    __tablename__ = "availability_check"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    part_no: Mapped[str] = mapped_column(String(120), index=True)
    state: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(20))
    qty: Mapped[int | None] = mapped_column(Integer)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
