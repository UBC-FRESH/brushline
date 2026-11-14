"""Static demo deployment helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

DEPLOY_SCHEMA_VERSION: Literal["brushline.demo-deploy.v1"] = "brushline.demo-deploy.v1"


class DemoDeployConfig(BaseModel):
    """Static deploy metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["brushline.demo-deploy.v1"] = DEPLOY_SCHEMA_VERSION
    base_path: str = "/"
    read_only: bool = True
    service: str = "static"


def write_deploy_config(path: str | Path, *, base_path: str = "/") -> Path:
    """Write deploy metadata for Pages or a path-prefixed static host."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        DemoDeployConfig(base_path=base_path).model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return destination
