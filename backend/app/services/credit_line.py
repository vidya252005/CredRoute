"""First-loan cap and repeat-borrower limit ladder (credit-building loop)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.identity import SensitiveIdentity
from app.models.entities import BorrowerCreditLine
from app.services.underwriting_rules import load_underwriting_rules


def _ladder() -> dict:
    return load_underwriting_rules()["limitLadder"]


def starter_limit(monthly_income: int, alt_data_score: float) -> int:
    rules = _ladder()
    raw = int(monthly_income * (1.2 + alt_data_score))
    return max(rules["firstLoanMin"], min(rules["firstLoanMax"], raw))


def stepped_limit(base: int, on_time: int, monthly_income: int) -> int:
    rules = _ladder()
    grown = base + on_time * rules["stepUp"]
    income_cap = monthly_income * rules["incomeMultipleCap"]
    return min(rules["maxLimit"], income_cap, grown)


def serialize_line(line: BorrowerCreditLine) -> dict:
    return {
        "pan": line.pan,
        "currentLimit": line.current_limit,
        "nextLimit": line.next_limit,
        "onTimeRepayments": line.on_time_repayments,
        "originatedCount": line.originated_count,
        "firstLoan": line.originated_count == 0,
        "lastOriginatedAmount": line.last_originated_amount,
    }


def get_or_create_credit_line(
    db: Session,
    pan: str,
    monthly_income: int,
    alt_data_score: float,
) -> BorrowerCreditLine:
    identity = SensitiveIdentity(pan)
    line = (
        db.query(BorrowerCreditLine)
        .filter(BorrowerCreditLine.pan_hash == identity.pan_hash)
        .first()
    )
    if line:
        return line
    base = starter_limit(monthly_income, alt_data_score)
    line = BorrowerCreditLine(
        pan=identity.pan_masked,
        pan_hash=identity.pan_hash,
        current_limit=base,
        next_limit=stepped_limit(base, 1, monthly_income),
        starter_limit=base,
        on_time_repayments=0,
        originated_count=0,
        last_originated_amount=0,
        version=0,
    )
    try:
        with db.begin_nested():
            db.add(line)
            db.flush()
        return line
    except IntegrityError:
        existing = (
            db.query(BorrowerCreditLine)
            .filter(BorrowerCreditLine.pan_hash == identity.pan_hash)
            .first()
        )
        if existing:
            return existing
        raise


def record_origination(line: BorrowerCreditLine, amount: int) -> None:
    line.originated_count += 1
    line.last_originated_amount = amount
    line.version = (line.version or 0) + 1
    line.updated_at = datetime.now(UTC)


def record_on_time_repayment(line: BorrowerCreditLine, monthly_income: int) -> dict:
    line.on_time_repayments += 1
    line.current_limit = stepped_limit(line.starter_limit, line.on_time_repayments, monthly_income)
    line.next_limit = stepped_limit(line.starter_limit, line.on_time_repayments + 1, monthly_income)
    line.version = (line.version or 0) + 1
    line.updated_at = datetime.now(UTC)
    return serialize_line(line)
