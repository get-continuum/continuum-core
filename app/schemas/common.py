from __future__ import annotations

from pydantic import BaseModel


DEFAULT_WORKSPACE_ID = "default"


class WorkspaceQuery(BaseModel):
    workspace_id: str = DEFAULT_WORKSPACE_ID

