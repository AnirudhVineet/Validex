from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.enums import Role
from app.models import Notification, User
from app.models.base import utcnow
from app.schemas import NotificationOut
from app.services import alerts

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(unread_only: bool = False, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)) -> list[Notification]:
    if user.role == Role.scrutiny_officer:
        # Time-based alert: verifications pending too long. Checked when officers look.
        if alerts.pending_verifications(db):
            db.commit()
    return alerts.for_user(db, user, unread_only)


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: str, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)) -> Notification:
    note = db.get(Notification, notification_id)
    if note is None or note.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    note.read_at = note.read_at or utcnow()
    db.commit()
    return note
