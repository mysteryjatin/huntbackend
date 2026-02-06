"""
Financial Calculator Screen API - Calculation endpoints for the 4 tabs:
Loan Eligibility, Rental Value, Future Value, EMI.
Pure calculation; no DB. Matches frontend financial_calculators_screen.dart.
"""
import math
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter()


# ---------- Loan Eligibility ----------
class LoanEligibilityRequest(BaseModel):
    loan_required: float = Field(..., ge=0, description="Loan Required (₹)")
    net_income_per_month: float = Field(..., ge=0, description="Net income per month (₹)")
    existing_loan_commitments: float = Field(0, ge=0, description="Existing loan commitments (₹)")
    loan_tenure_years: float = Field(..., ge=0.5, le=30, description="Loan Tenure (years)")
    rate_of_interest: float = Field(..., ge=0, le=30, description="Rate of Interest (%)")


@router.post("/loan-eligibility")
async def loan_eligibility(req: LoanEligibilityRequest):
    """
    Loan Eligibility tab: Check max eligible loan amount.
    Uses FOIR (Fixed Obligation to Income Ratio); typically max 50–60% of net income
    can go toward EMI. Eligible EMI = (net_income - existing_commitments) * factor.
    Then back-calculate principal from EMI formula.
    """
    # Max 50% of (net_income - existing_commitments) for new EMI
    available_for_emi = max(0, req.net_income_per_month - req.existing_loan_commitments)
    max_emi_ratio = 0.5
    max_emi = available_for_emi * max_emi_ratio
    if max_emi <= 0:
        return {
            "success": True,
            "data": {
                "eligible": False,
                "message": "Eligibility Check Failed",
                "maximum_eligible_amount": 0,
                "maximum_emi": 0,
            },
        }
    # EMI = P * r * (1+r)^n / ((1+r)^n - 1)  =>  P = EMI * ((1+r)^n - 1) / (r * (1+r)^n)
    r = (req.rate_of_interest / 100) / 12
    n = req.loan_tenure_years * 12
    if r <= 0:
        max_principal = max_emi * n
    else:
        max_principal = max_emi * ((1 + r) ** n - 1) / (r * (1 + r) ** n)
    eligible = req.loan_required <= max_principal
    return {
        "success": True,
        "data": {
            "eligible": eligible,
            "message": "Eligible" if eligible else "Eligibility Check Failed",
            "maximum_eligible_amount": round(max_principal, 0),
            "maximum_emi": round(max_emi, 0),
            "loan_required": req.loan_required,
        },
    }


# ---------- Rental Value ----------
class RentalValueRequest(BaseModel):
    property_value: float = Field(..., ge=0, description="Property Value (₹)")
    rate_of_rent: float = Field(..., ge=0, le=30, description="Rate of Rent (%) - annual yield")
    years: Optional[float] = Field(1, ge=0, description="Years (optional, for display)")


@router.post("/rental-value")
async def rental_value(req: RentalValueRequest):
    """
    Rental Value tab: Annual yield = property_value * (rate_of_rent/100).
    Returns annual and monthly rental value.
    """
    annual_rent = req.property_value * (req.rate_of_rent / 100)
    monthly_rent = annual_rent / 12
    return {
        "success": True,
        "data": {
            "rental_value_annual": round(annual_rent, 0),
            "rental_value_monthly": round(monthly_rent, 0),
            "property_value": req.property_value,
            "rate_of_rent": req.rate_of_rent,
        },
    }


# ---------- Future Value ----------
class FutureValueRequest(BaseModel):
    current_property_value: float = Field(..., ge=0, description="Current property value (₹)")
    years: float = Field(..., ge=0, le=50, description="No. of years")
    average_appreciation: float = Field(..., ge=0, le=50, description="Average appreciation (%)")


@router.post("/future-value")
async def future_value(req: FutureValueRequest):
    """
    Future Value tab: FV = PV * (1 + r/100)^n
    """
    fv = req.current_property_value * ((1 + req.average_appreciation / 100) ** req.years)
    return {
        "success": True,
        "data": {
            "future_value": round(fv, 0),
            "current_property_value": req.current_property_value,
            "years": req.years,
            "average_appreciation": req.average_appreciation,
        },
    }


# ---------- EMI ----------
class EmiRequest(BaseModel):
    loan_amount: float = Field(..., ge=0, description="Loan Amount (₹)")
    loan_tenure_years: float = Field(..., ge=0.5, le=30, description="Loan Tenure (years)")
    rate_of_interest: float = Field(..., ge=0, le=30, description="Rate of Interest (%)")


@router.post("/emi")
async def emi(req: EmiRequest):
    """
    EMI tab: Monthly EMI = P * r * (1+r)^n / ((1+r)^n - 1)
    Also returns total interest and total amount payable.
    """
    r = (req.rate_of_interest / 100) / 12
    n = req.loan_tenure_years * 12
    if r <= 0:
        monthly_emi = req.loan_amount / n
    else:
        monthly_emi = req.loan_amount * r * ((1 + r) ** n) / (((1 + r) ** n) - 1)
    total_payable = monthly_emi * n
    total_interest = total_payable - req.loan_amount
    return {
        "success": True,
        "data": {
            "monthly_emi": round(monthly_emi, 0),
            "total_amount_payable": round(total_payable, 0),
            "total_interest": round(total_interest, 0),
            "loan_amount": req.loan_amount,
            "loan_tenure_years": req.loan_tenure_years,
            "rate_of_interest": req.rate_of_interest,
        },
    }
