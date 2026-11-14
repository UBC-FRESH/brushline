"""Plan approval and audit record."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AUDIT_SCHEMA_VERSION: Literal["brushline.plan-approval.v1"] = "brushline.plan-approval.v1"


class ApprovalRecord(BaseModel):
    """An approval or review record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.plan-approval.v1"] = AUDIT_SCHEMA_VERSION
    plan_id: str
    version: int = Field(ge=1)
    reviewer: str
    status: Literal["pending", "approved", "rejected"]
    comment: str = ""
    plan_digest: str
    created_utc: datetime


def plan_digest(exchange: object) -> str:
    """Return a canonical digest of a plan exchange or plan."""
    payload = exchange.model_dump_json() if hasattr(exchange, "model_dump_json") else str(exchange)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def approve_plan(
    *,
    plan_id: str,
    version: int,
    reviewer: str,
    status: Literal["pending", "approved", "rejected"],
    plan: object,
    comment: str = "",
    created_utc: datetime | None = None,
) -> ApprovalRecord:
    """Create an approval record with a plan digest."""
    return ApprovalRecord(
        plan_id=plan_id,
        version=version,
        reviewer=reviewer,
        status=status,
        comment=comment,
        plan_digest=plan_digest(plan),
        created_utc=created_utc or datetime.now(UTC),
    )


def write_approval(record: ApprovalRecord, path: str | Path) -> Path:
    """Write an approval record."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination
