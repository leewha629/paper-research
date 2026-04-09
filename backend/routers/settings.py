from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import AppSetting
from schemas import SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

SETTING_KEYS = [
    "ai_backend",
    "claude_api_key",
    "ollama_base_url",
    "ollama_model",
    "semantic_scholar_api_key",
    "unpaywall_email",
    "check_interval",
    "relevance_threshold",
]

SENSITIVE_KEYS = {"claude_api_key", "semantic_scholar_api_key"}


def mask_value(key: str, value: str) -> str:
    if key in SENSITIVE_KEYS and value:
        if len(value) <= 8:
            return "*" * len(value)
        return value[:4] + "*" * (len(value) - 8) + value[-4:]
    return value


@router.get("")
async def get_settings(db: Session = Depends(get_db)):
    settings = {}
    for key in SETTING_KEYS:
        record = db.query(AppSetting).filter(AppSetting.key == key).first()
        value = record.value if record else ""
        settings[key] = mask_value(key, value or "")
    return settings


@router.put("")
async def update_settings(body: SettingsUpdate, db: Session = Depends(get_db)):
    for key, value in body.model_dump(exclude_unset=True).items():
        if key not in SETTING_KEYS:
            continue

        # If the value is masked (contains ***), skip updating
        if value and "***" in value:
            continue

        record = db.query(AppSetting).filter(AppSetting.key == key).first()
        if record:
            record.value = value
        else:
            record = AppSetting(key=key, value=value)
            db.add(record)

    db.commit()

    # Return updated settings (masked)
    settings = {}
    for key in SETTING_KEYS:
        record = db.query(AppSetting).filter(AppSetting.key == key).first()
        value = record.value if record else ""
        settings[key] = mask_value(key, value or "")
    return settings
