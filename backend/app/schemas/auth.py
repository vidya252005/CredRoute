from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class EvaluateRequest(BaseModel):
    name: str
    pan: str
    age: int
    monthlyIncome: int
    incomeType: str
    cibilScore: int | None = None
    existingEmis: int = 0
    bankStatementAvgBalance: int = 0
    cityTier: int = 1
    amount: int
    tenureMonths: int
