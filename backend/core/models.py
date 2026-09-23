"""Pydantic request models shared across routers."""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    accepted_terms_version: Optional[str] = None
    accepted_privacy_version: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileRequest(BaseModel):
    dietary: List[str] = []
    targets: List[str] = []
    sensitivities: List[str] = []


class ContributionRequest(BaseModel):
    barcode: str
    product_name: Optional[str] = None
    brand: Optional[str] = None
    notes: Optional[str] = None
    images: List[str] = []


class ScanPurchase(BaseModel):
    quantity: int = Field(ge=1, le=100)
    tier: str


class SubscriptionPurchase(BaseModel):
    plan: str
    country: Optional[str] = None


class SupportRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=140)
    message: str = Field(min_length=5, max_length=4000)
    category: str = Field(default="general")


class ReportRequest(BaseModel):
    barcode: str
    reason: str = Field(min_length=5, max_length=1000)


class PasswordResetStart(BaseModel):
    email: str


class PasswordResetComplete(BaseModel):
    email: str
    otp: str
    new_password: str = Field(min_length=6)


class AdminPricingUpdate(BaseModel):
    country: str
    currency: str
    symbol: str
    scan_intro: float
    scan_standard: float
    monthly: float
    yearly: float
    monthly_regular: float
    yearly_regular: float
    provider: str


class AdminPromocode(BaseModel):
    code: str = Field(min_length=3, max_length=32)
    kind: str  # 'percent' | 'flat' | 'free_scans'
    value: float
    max_redemptions: int = 100
    countries: List[str] = []
    expires_at: Optional[str] = None
    active: bool = True


class SupportUpdate(BaseModel):
    status: str  # 'open' | 'in_progress' | 'resolved' | 'closed'
    admin_note: Optional[str] = None


class UserSuspendRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=280)


class RazorpayOrderIn(BaseModel):
    credits: int = Field(ge=1, le=100)
    tier: str = Field(pattern="^(intro|standard)$")
    promo_code: Optional[str] = None


class RazorpaySubscriptionIn(BaseModel):
    plan: str = Field(pattern="^(monthly|yearly)$")
    promo_code: Optional[str] = None


class RazorpayVerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class AdminRefundIn(BaseModel):
    payment_id: str
    reason: str = Field(min_length=3, max_length=500)


class ProductMergeIn(BaseModel):
    primary_barcode: str
    duplicate_barcodes: List[str] = Field(min_length=1)


class ProductBadgesIn(BaseModel):
    badges_extra: List[Dict[str, str]] = []
    badges_override: Optional[List[Dict[str, str]]] = None
