from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.identity import is_valid_pan, normalize_pan


class EvaluateApplicationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    pan: str
    age: int = Field(ge=21, le=60)
    monthlyIncome: int = Field(gt=0, le=10_000_000)
    incomeType: Literal["salaried", "self_employed", "msme", "gig"]
    cibilScore: int | None = Field(default=None, ge=300, le=900)
    existingEmis: int = Field(default=0, ge=0)
    bankStatementAvgBalance: int = Field(default=0, ge=0)
    cityTier: int = Field(default=1, ge=1, le=3)
    amount: int = Field(gt=0, le=20_000_000)
    tenureMonths: int = Field(ge=6, le=84)
    consentAltData: bool = False
    financialNotes: str | None = None
    financialText: str | None = None
    androidApiLevel: int | None = None
    simTenureMonths: int | None = None
    rooted: bool | None = None

    @field_validator("pan")
    @classmethod
    def validate_pan(cls, value: str) -> str:
        pan = normalize_pan(value)
        if not is_valid_pan(pan):
            raise ValueError("pan must match format ABCDE1234F")
        return pan

    @field_validator("cibilScore", mode="before")
    @classmethod
    def empty_cibil(cls, value):
        if value in ("", None, 0):
            return None
        return value


class LenderPolicyUpdateRequest(BaseModel):
    min_income: int | None = Field(default=None, ge=0)
    min_credit_score: int | None = Field(default=None, ge=0, le=900)
    max_amount: int | None = Field(default=None, gt=0)
    max_foir: float | None = Field(default=None, gt=0, le=1)
    base_interest_rate: float | None = Field(default=None, gt=0, le=40)
    processing_fee: int | None = Field(default=None, ge=0)
    success_rate: float | None = Field(default=None, ge=0, le=1)
    journey_score: float | None = Field(default=None, ge=0, le=1)
    serves_prime: bool | None = None
    serves_near_prime: bool | None = None
    serves_thin_file: bool | None = None
    description: str | None = Field(default=None, max_length=500)
