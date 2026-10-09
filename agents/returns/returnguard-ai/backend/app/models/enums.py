"""Shared enumerations persisted as strings."""
from __future__ import annotations


class UserRole:
    ADMIN = "ADMIN"
    AGENT = "AGENT"          # delivery agent
    OPERATOR = "OPERATOR"    # warehouse / inspection operator
    ALL = (ADMIN, AGENT, OPERATOR)
    INSPECTOR_ROLES = (AGENT, OPERATOR)


class ReturnStatus:
    PENDING = "PENDING"                        # created, no active QR yet
    AWAITING_SCAN = "AWAITING_SCAN"            # QR authorization active
    AWAITING_OTP = "AWAITING_OTP"              # QR scanned, OTP challenge open
    AWAITING_INSPECTION = "AWAITING_INSPECTION"  # OTP verified, image upload pending
    INSPECTED = "INSPECTED"                    # pipeline finished, decision recorded
    NEEDS_REVIEW = "NEEDS_REVIEW"              # routed to human review
    APPROVED = "APPROVED"                      # return accepted (auto or by reviewer)
    REJECTED = "REJECTED"                      # return refused (auto or by reviewer)
    CANCELLED = "CANCELLED"                    # admin cancelled the return
    ALL = (
        PENDING, AWAITING_SCAN, AWAITING_OTP, AWAITING_INSPECTION,
        INSPECTED, NEEDS_REVIEW, APPROVED, REJECTED, CANCELLED,
    )
    TERMINAL = (APPROVED, REJECTED, CANCELLED)


class QRStatus:
    ACTIVE = "ACTIVE"
    USED = "USED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    ALL = (ACTIVE, USED, REVOKED, EXPIRED)


class OTPStatus:
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    EXPIRED = "EXPIRED"
    EXHAUSTED = "EXHAUSTED"   # too many wrong attempts
    SUPERSEDED = "SUPERSEDED"  # replaced by a resend
    CONSUMED = "CONSUMED"      # already used to authorize an inspection
    ALL = (PENDING, VERIFIED, EXPIRED, EXHAUSTED, SUPERSEDED, CONSUMED)


class OCRStatus:
    OK = "OK"
    NO_TEXT_DETECTED = "NO_TEXT_DETECTED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    ENGINE_UNAVAILABLE = "ENGINE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"
    ALL = (OK, NO_TEXT_DETECTED, LOW_CONFIDENCE, ENGINE_UNAVAILABLE, TIMEOUT, FAILED)


class DetectionStatus:
    OK = "OK"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"
    ALL = (OK, MODEL_UNAVAILABLE, TIMEOUT, FAILED)


class Observation:
    OBSERVED = "OBSERVED"
    NOT_OBSERVED = "NOT_OBSERVED"          # searched for, no supporting evidence
    NOT_VISIBLE = "NOT_VISIBLE"            # cannot be concluded from this angle
    UNCERTAIN = "UNCERTAIN"
    # Evidence establishes absence (requires a contents-layout view where the
    # item should be visible, or equivalent strong evidence).
    CONFIRMED_MISSING = "CONFIRMED_MISSING"
    ALL = (OBSERVED, NOT_OBSERVED, NOT_VISIBLE, UNCERTAIN, CONFIRMED_MISSING)


class Verdict:
    """Dimension-level outcomes for identity / completeness / condition."""

    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"
    ALL = (PASS, FAIL, UNCERTAIN)


class Disposition:
    RESTOCK = "RESTOCK"
    REFURBISH = "REFURBISH"
    LIQUIDATE = "LIQUIDATE"
    DISPOSE = "DISPOSE"
    ALL = (RESTOCK, REFURBISH, LIQUIDATE, DISPOSE)


class AIStatus:
    """Honest statuses for the Groq/Qwen visual-reasoning stage."""

    OK = "OK"
    UNAVAILABLE = "UNAVAILABLE"    # no key / SDK not installed / disabled
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"  # provider rate limit after bounded retries
    MALFORMED = "MALFORMED"        # response did not match the required schema
    FAILED = "FAILED"              # provider or network failure
    ALL = (OK, UNAVAILABLE, TIMEOUT, RATE_LIMITED, MALFORMED, FAILED)


class ViewType:
    STANDARD = "STANDARD"                  # normal single-product photo
    CONTENTS_LAYOUT = "CONTENTS_LAYOUT"    # all returned contents laid out / organized
    ALL = (STANDARD, CONTENTS_LAYOUT)


class InspectionStatus:
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ALL = (PROCESSING, COMPLETED, FAILED)


class DecisionOutcome:
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    ALL = (APPROVE, REJECT, MANUAL_REVIEW)


class ReviewOutcome:
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ALL = (APPROVE, REJECT)


class AuditAction:
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    RETURN_CREATED = "RETURN_CREATED"
    RETURN_UPDATED = "RETURN_UPDATED"
    RETURN_CANCELLED = "RETURN_CANCELLED"
    QR_GENERATED = "QR_GENERATED"
    QR_REVOKED = "QR_REVOKED"
    QR_SCANNED = "QR_SCANNED"
    QR_SCAN_REJECTED = "QR_SCAN_REJECTED"
    OTP_ISSUED = "OTP_ISSUED"
    OTP_VERIFIED = "OTP_VERIFIED"
    OTP_VERIFY_FAILED = "OTP_VERIFY_FAILED"
    INSPECTION_CREATED = "INSPECTION_CREATED"
    INSPECTION_FAILED = "INSPECTION_FAILED"
    DECISION_RECORDED = "DECISION_RECORDED"
    REVIEW_RESOLVED = "REVIEW_RESOLVED"
    CATALOGUE_CREATED = "CATALOGUE_CREATED"
    CATALOGUE_UPDATED = "CATALOGUE_UPDATED"
    AI_ANALYSIS_RECORDED = "AI_ANALYSIS_RECORDED"
