"""Import every model so Base.metadata knows all tables."""
from app.models.application import Application, ApplicationDocument, ApplicationVersion, ExtractedField
from app.models.audit import AuditEvent
from app.models.misc import InspectionRecord, Notification
from app.models.user import Institution, User
from app.models.validation import Finding, ReviewAction, RuleSetVersion, ValidationRun, VerificationRequest

__all__ = [
    "Application", "ApplicationDocument", "ApplicationVersion", "AuditEvent", "ExtractedField",
    "Finding", "InspectionRecord", "Institution", "Notification", "ReviewAction",
    "RuleSetVersion", "User", "ValidationRun", "VerificationRequest",
]
