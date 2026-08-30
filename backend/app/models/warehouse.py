"""Scale-benchmark warehouse tables (synthetic loan history)."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class WarehouseBorrower(Base):
    __tablename__ = "warehouse_borrowers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pan: Mapped[str] = mapped_column(String(10), index=True)
    age: Mapped[int] = mapped_column(Integer)
    income_type: Mapped[str] = mapped_column(String(32))
    monthly_income: Mapped[int] = mapped_column(Integer)
    cibil_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    city_tier: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WarehouseLoan(Base):
    __tablename__ = "warehouse_loans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    borrower_id: Mapped[int] = mapped_column(ForeignKey("warehouse_borrowers.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    tenure_months: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    interest_rate: Mapped[float] = mapped_column(Float)
    originated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class WarehouseTransaction(Base):
    __tablename__ = "warehouse_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    loan_id: Mapped[int] = mapped_column(ForeignKey("warehouse_loans.id"), index=True)
    borrower_id: Mapped[int] = mapped_column(Integer, index=True)
    amount: Mapped[int] = mapped_column(Integer)
    txn_type: Mapped[str] = mapped_column(String(24), index=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class WarehouseApplication(Base):
    __tablename__ = "warehouse_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    borrower_id: Mapped[int] = mapped_column(Integer, index=True)
    amount: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(16), index=True)
    default_probability: Mapped[float] = mapped_column(Float)
    fraud_probability: Mapped[float] = mapped_column(Float)
    explained: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
