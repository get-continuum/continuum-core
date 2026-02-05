import requests
from typing import Any, Dict, Optional

from .types import (
    Metric,
    MetricGetOut,
    MintTokenRequest,
    MintTokenResponse,
    ResolutionResponse,
    ResolveStateRequest,
    ResolveStateResponse,
    WhoAmIResponse,
)

class Engram:
    """
    Python SDK for the Engram/Continuum API.

    Auth:
    - workspace key: long-lived `wk_live_...` (admin/ingestion channel)
    - user token: short-lived JWT (runtime channel)
    """

    def __init__(
        self,
        api_base_url: str = "http://localhost:8000",
        *,
        workspace_id: str = "default",
        workspace_key: Optional[str] = None,
        user_token: Optional[str] = None,
    ):
        self.api_base_url = api_base_url.rstrip("/")
        self.workspace_id = workspace_id
        self._workspace_key = workspace_key
        self._user_token = user_token

    def _headers(self, *, auth: str) -> dict:
        if auth == "workspace":
            token = self._workspace_key
        elif auth == "user":
            token = self._user_token
        else:
            token = None
        return {"Authorization": f"Bearer {token}"} if token else {}

    def set_workspace_key(self, token: str) -> None:
        self._workspace_key = token

    def set_user_token(self, token: str) -> None:
        self._user_token = token

    def resolve(self, query: str, context: Dict[str, Any]) -> ResolutionResponse:
        payload = {
            "query": query,
            "context": context
        }
        response = requests.post(
            f"{self.api_base_url}/metrics/resolve_intent",
            params={"workspace_id": self.workspace_id},
            json=payload,
            headers=self._headers(auth="user") or self._headers(auth="workspace"),
            timeout=20,
        )
        response.raise_for_status()
        return ResolutionResponse(**response.json())

    def get_metric(self, metric_id: str) -> Metric:
        response = requests.get(
            f"{self.api_base_url}/metrics/{metric_id}",
            params={"workspace_id": self.workspace_id},
            headers=self._headers(auth="user") or self._headers(auth="workspace"),
            timeout=20,
        )
        response.raise_for_status()
        out = MetricGetOut(**response.json())
        return out.metric

    def create_metric(self, metric_id: str, canonical_name: str, description: Optional[str] = None) -> Metric:
        payload = {
            "metric_id": metric_id,
            "canonical_name": canonical_name,
            "description": description
        }
        response = requests.post(
            f"{self.api_base_url}/metrics",
            params={"workspace_id": self.workspace_id},
            json=payload,
            headers=self._headers(auth="workspace"),
            timeout=20,
        )
        response.raise_for_status()
        return Metric(**response.json())

    def resolve_metric(self, metric_id: str, context: Dict[str, Any]) -> ResolveStateResponse:
        body = ResolveStateRequest(context=context)
        response = requests.post(
            f"{self.api_base_url}/metrics/{metric_id}/resolve",
            params={"workspace_id": self.workspace_id},
            json=body.model_dump(),
            headers=self._headers(auth="user") or self._headers(auth="workspace"),
            timeout=20,
        )
        response.raise_for_status()
        return ResolveStateResponse(**response.json())

    def mint_user_token(self, req: MintTokenRequest) -> MintTokenResponse:
        response = requests.post(
            f"{self.api_base_url}/auth/token",
            json=req.model_dump(),
            headers=self._headers(auth="workspace"),
            timeout=20,
        )
        response.raise_for_status()
        return MintTokenResponse(**response.json())

    def whoami(self) -> WhoAmIResponse:
        response = requests.get(
            f"{self.api_base_url}/auth/whoami",
            headers=self._headers(auth="user") or self._headers(auth="workspace"),
            timeout=20,
        )
        response.raise_for_status()
        return WhoAmIResponse(**response.json())
