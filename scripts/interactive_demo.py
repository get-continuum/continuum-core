from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
import yaml
from fastapi.testclient import TestClient

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from scripts.db_engine import DBEngine
from scripts.demo_lib import DemoEngine


@dataclass(frozen=True)
class IngestItem:
    label: str
    path: str


DEMO_FILES: List[IngestItem] = [
    IngestItem("marketing semantic model", "demo/marketing_metrics.yaml"),
    IngestItem("finance semantic model", "demo/finance_metrics.yaml"),
    IngestItem("demo dataset (events/overlays)", "demo/demo.yaml"),
]


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _metric_exists(client: TestClient, metric_id: str, workspace_id: str) -> bool:
    r = client.get(f"/metrics/{metric_id}", params={"workspace_id": workspace_id})
    return r.status_code == 200


def _get_overlays(client: TestClient, metric_id: str, workspace_id: str) -> list[dict]:
    r = client.get(f"/metrics/{metric_id}/overlays", params={"workspace_id": workspace_id})
    if r.status_code == 200:
        return r.json()
    return []


def _get_history(client: TestClient, metric_id: str, workspace_id: str, limit: int = 500) -> list[dict]:
    r = client.get(
        f"/metrics/{metric_id}/history",
        params={"workspace_id": workspace_id, "limit": limit},
    )
    if r.status_code == 200:
        return r.json()
    return []


def _overlay_exists(existing: list[dict], selector: dict, priority: int) -> bool:
    target = (_stable_json(selector or {}), int(priority))
    keys = {(_stable_json(o.get("selector") or {}), int(o.get("priority") or 0)) for o in existing}
    return target in keys


def _event_exists(existing: list[dict], candidate: dict) -> bool:
    cand_key = _stable_json(
        {
            "event_type": candidate.get("event_type"),
            "source_system": candidate.get("source_system"),
            "source_ref": candidate.get("source_ref") or {},
            "snapshot": candidate.get("snapshot") or {},
        }
    )
    for e in existing:
        e_key = _stable_json(
            {
                "event_type": e.get("event_type"),
                "source_system": e.get("source_system"),
                "source_ref": e.get("source_ref") or {},
                "snapshot": e.get("snapshot") or {},
            }
        )
        if e_key == cand_key:
            return True
    return False


def load_demo_yaml_via_client(
    client: TestClient, *, yaml_path: str, workspace_id: str
) -> List[str]:
    """
    Idempotent loader for demo/demo.yaml, but using in-process FastAPI TestClient.
    Creates: metrics, aliases, events, overlays.
    """
    p = Path(yaml_path)
    if not p.exists():
        raise FileNotFoundError(f"YAML not found: {yaml_path}")

    doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    metrics = doc.get("metrics") or []
    logs: List[str] = []

    for m in metrics:
        metric_id = m["metric_id"]

        # 1) Metric create (skip if exists)
        if _metric_exists(client, metric_id, workspace_id):
            logs.append(f"[{metric_id}] metric exists (skip)")
        else:
            r = client.post(
                "/metrics",
                params={"workspace_id": workspace_id},
                json={
                    "metric_id": metric_id,
                    "canonical_name": m["canonical_name"],
                    "description": m.get("description"),
                },
            )
            if r.status_code != 200:
                raise RuntimeError(f"[{metric_id}] metric create failed: {r.status_code} {r.text}")
            logs.append(f"[{metric_id}] metric created")

        # 2) Aliases (API upserts by source_system+source_locator)
        for a in m.get("aliases") or []:
            r = client.post(
                f"/metrics/{metric_id}/aliases",
                params={"workspace_id": workspace_id},
                json=a,
            )
            if r.status_code != 200:
                raise RuntimeError(f"[{metric_id}] alias failed: {r.status_code} {r.text}")
            logs.append(f"[{metric_id}] alias ok ({a.get('source_system')}:{a.get('source_locator')})")

        # 3) Events (skip if same identity exists)
        existing_events = _get_history(client, metric_id, workspace_id, limit=500)
        for e in m.get("events") or []:
            if _event_exists(existing_events, e):
                logs.append(f"[{metric_id}] event exists (skip) ({e.get('event_type')})")
                continue
            r = client.post(
                f"/metrics/{metric_id}/events",
                params={"workspace_id": workspace_id},
                json=e,
            )
            if r.status_code != 200:
                raise RuntimeError(f"[{metric_id}] event failed: {r.status_code} {r.text}")
            out = r.json()
            logs.append(f"[{metric_id}] event appended v{out.get('version_id')} ({e.get('event_type')})")

        # 4) Overlays (skip if selector+priority exists)
        existing_overlays = _get_overlays(client, metric_id, workspace_id)
        for o in m.get("overlays") or []:
            selector = o.get("selector") or {}
            priority = int(o.get("priority") or 0)
            if _overlay_exists(existing_overlays, selector, priority):
                logs.append(f"[{metric_id}] overlay exists (skip) selector={selector} priority={priority}")
                continue
            r = client.post(
                f"/metrics/{metric_id}/overlays",
                params={"workspace_id": workspace_id},
                json=o,
            )
            if r.status_code != 200:
                raise RuntimeError(f"[{metric_id}] overlay failed: {r.status_code} {r.text}")
            out = r.json()
            logs.append(f"[{metric_id}] overlay created {out.get('overlay_id')} priority={priority}")

    return logs


def resolve_contract(
    client: TestClient,
    *,
    metric_id: str,
    workspace_id: str,
    context: dict,
) -> Tuple[Optional[dict], Optional[str]]:
    r = client.post(
        f"/metrics/{metric_id}/resolve",
        params={"workspace_id": workspace_id},
        json={"context": context or {}},
    )
    if r.status_code != 200:
        return None, f"{r.status_code}: {r.text}"
    return r.json(), None


def contract_projection(resolve_response: dict) -> dict:
    """
    Show stable, machine-facing fields only.
    """
    metric_id = resolve_response.get("metric_id")
    snapshot = resolve_response.get("resolved_snapshot") or {}
    return {
        "identity": {"metric_id": metric_id},
        "definition": snapshot.get("definition"),
        "grain": snapshot.get("grain"),
        "source": resolve_response.get("provenance"),
        "constraints": {
            "dimensions": snapshot.get("dimensions"),
            "units": snapshot.get("units"),
        },
    }


def apply_followup_to_contract(contract: dict, followup: str) -> dict:
    """
    Demo-only: interpret a follow-up as extra constraints on the *same* resolved meaning.

    This intentionally does not re-resolve intent; it demonstrates continuity by reusing
    the previously chosen identity and applying a small, visible transformation.
    """
    out = json.loads(json.dumps(contract))  # deep copy, JSON-safe
    f = (followup or "").strip().lower()
    if not f:
        return out

    constraints = out.setdefault("constraints", {})
    dims = list(constraints.get("dimensions") or [])

    # Minimal follow-up parsing (explicit, not magical).
    if "country" in f and "country" not in dims:
        dims.append("country")
    if "campaign" in f and "campaign" not in dims:
        dims.append("campaign")
    if "channel" in f and "channel" not in dims:
        dims.append("channel")
    if "region" in f and "region" not in dims:
        dims.append("region")

    # Grain hints
    if "weekly" in f or "per week" in f or "by week" in f:
        out["grain"] = "week"
    if "monthly" in f or "per month" in f or "by month" in f:
        out["grain"] = "month"

    constraints["dimensions"] = dims
    constraints["followup"] = {"text": followup}
    return out


st.set_page_config(page_title="Continuum Demo", layout="wide")

# Session state
if "engine" not in st.session_state:
    st.session_state.engine = None
if "engine_mode" not in st.session_state:
    st.session_state.engine_mode = None
if "ingestion_status" not in st.session_state:
    st.session_state.ingestion_status = {}  # path -> {"ok": bool, "ts": str}
if "last_intent" not in st.session_state:
    st.session_state.last_intent = None
if "last_selected_metric_id" not in st.session_state:
    st.session_state.last_selected_metric_id = None
if "last_contract" not in st.session_state:
    st.session_state.last_contract = None
if "last_contract_error" not in st.session_state:
    st.session_state.last_contract_error = None
if "last_query" not in st.session_state:
    st.session_state.last_query = ""
if "last_followup" not in st.session_state:
    st.session_state.last_followup = ""
if "followup_applied" not in st.session_state:
    st.session_state.followup_applied = False


client = TestClient(app)
workspace_id = "default"

st.title("Continuum Demo — Meaning Resolution")
st.caption("Left = intent. Right = resolved meaning + typed contract.")

left, right = st.columns([0.42, 0.58], gap="large")

with left:
    st.subheader("📦 Ingestion")
    st.caption("Show only file names + status. No parsing logs.")

    env_mode = os.getenv("ENGRAM_ENV", "demo")
    default_use_prod = True if env_mode == "production" else False
    use_prod = st.toggle(
        "Connect to Postgres-backed engine",
        value=default_use_prod,
        help="Demo mode uses local JSON memory; Postgres mode uses DB-backed memory (aliases/events/overlays).",
    )
    api_key = st.text_input(
        "OpenAI API Key (optional)",
        value=os.getenv("OPENAI_API_KEY", ""),
        type="password",
        help="Optional: enables LLM-based semantic routing. Demo works without it.",
    )

    target_mode = "production" if use_prod else "demo"
    if st.session_state.engine is None or st.session_state.engine_mode != target_mode:
        if use_prod:
            st.session_state.engine = DBEngine(llm_api_key=api_key)
        else:
            st.session_state.engine = DemoEngine(client, llm_api_key=api_key)
        st.session_state.engine_mode = target_mode

    engine = st.session_state.engine

    def _mark_ingested(path: str, ok: bool):
        st.session_state.ingestion_status[path] = {"ok": bool(ok), "ts": st.session_state.get("_now", "")}

    # Ingestion checklist
    for item in DEMO_FILES:
        status = st.session_state.ingestion_status.get(item.path)
        if status and status.get("ok"):
            st.success(f"{item.path} — Ingested ✓", icon="✅")
        else:
            st.info(f"{item.path} — Not ingested", icon="⬜")

    if st.button("Ingest demo definitions", use_container_width=True):
        st.session_state._now = st.session_state.get("_now") or ""  # placeholder for future ts
        try:
            # 1) Semantic models (drives ambiguity + resolver candidates)
            yaml_paths = ["demo/marketing_metrics.yaml", "demo/finance_metrics.yaml"]
            engine.ingest_yamls(yaml_paths)
            for p in yaml_paths:
                _mark_ingested(p, True)

            # 2) Demo dataset: events + overlays (drives typed /resolve contract)
            load_demo_yaml_via_client(client, yaml_path="demo/demo.yaml", workspace_id=workspace_id)
            _mark_ingested("demo/demo.yaml", True)

            st.success("Ingested: marketing_metrics.yaml, finance_metrics.yaml, demo.yaml")
        except Exception as e:
            st.error(str(e))

    st.divider()

    st.subheader("📝 Question")
    role = st.selectbox("Who are you?", ["Unknown / General", "Marketing", "Finance"], index=1)
    context: Dict[str, Any] = {"team": {"Marketing": "marketing", "Finance": "finance"}.get(role, "unknown")}

    use_case = st.text_input("Use case (optional)", value="weekly_performance" if context["team"] == "marketing" else "")
    if use_case.strip():
        context["use_case"] = use_case.strip()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Example: revenue", use_container_width=True):
            st.session_state.last_query = "revenue"
    with c2:
        if st.button("Example: revenue by campaign", use_container_width=True):
            st.session_state.last_query = "revenue by campaign"

    query = st.text_input(
        "Question",
        value=st.session_state.last_query,
        placeholder="What is revenue by campaign?",
        label_visibility="collapsed",
    )
    st.session_state.last_query = query

    if st.button("Resolve meaning", type="primary", use_container_width=True):
        st.session_state.last_contract = None
        st.session_state.last_contract_error = None
        st.session_state.last_selected_metric_id = None
        st.session_state.followup_applied = False

        result = engine.resolve_intent(query, context)
        st.session_state.last_intent = result

        # If resolved immediately, preselect and compute contract.
        if result.get("status") == "resolved" and result.get("resolved_metric"):
            metric_id = result["resolved_metric"]["metric_id"]
            st.session_state.last_selected_metric_id = metric_id
            contract, err = resolve_contract(
                client, metric_id=metric_id, workspace_id=workspace_id, context=context
            )
            st.session_state.last_contract = contract
            st.session_state.last_contract_error = err

    st.divider()
    st.subheader("🔁 Follow-up (reuse meaning)")
    st.caption("Ask a follow-up that reuses the resolved identity (no re-resolution).")

    followup = st.text_input(
        "Follow-up",
        value=st.session_state.last_followup,
        placeholder="Break it down by country",
        label_visibility="collapsed",
        disabled=not bool(st.session_state.last_selected_metric_id),
    )
    st.session_state.last_followup = followup

    if st.button(
        "Apply follow-up",
        use_container_width=True,
        disabled=not bool(st.session_state.last_selected_metric_id),
    ):
        metric_id = st.session_state.last_selected_metric_id
        contract, err = resolve_contract(client, metric_id=metric_id, workspace_id=workspace_id, context=context)
        st.session_state.last_contract = contract
        st.session_state.last_contract_error = err
        st.session_state.followup_applied = True


with right:
    st.subheader("🧭 Continuum Resolution")

    intent = st.session_state.last_intent
    selected_metric_id = st.session_state.last_selected_metric_id

    if not intent:
        st.info("Ingest the demo YAMLs, then ask a question to resolve meaning.")
    else:
        status = intent.get("status")
        reason = intent.get("reason") or ""
        confidence = float(intent.get("confidence") or 0.0)
        memory_hit = ("saved alias" in reason.lower()) or ("alias" in reason.lower() and confidence >= 1.0)

        if status == "resolved":
            m = intent.get("resolved_metric") or {}
            metric_id = m.get("metric_id") or selected_metric_id or ""

            st.markdown("### Resolved Concept")
            st.markdown(f"**{(query or 'query').strip()} → `{metric_id}`**")
            if memory_hit:
                st.caption("✓ Meaning preserved from previous step")
            if st.session_state.followup_applied and st.session_state.last_followup.strip():
                st.caption(f"Using stored semantic context. Reusing: `{metric_id}`")
            st.caption(f"Confidence: {confidence * 100:.0f}% — {reason}")

            st.markdown("**Context**")
            st.json(context)

        elif status == "ambiguous":
            st.warning("Ambiguous meaning. Select the intended definition.")
            st.caption(reason)

            candidates = intent.get("candidates") or []
            if not candidates:
                st.info("No candidates returned.")
            else:
                st.markdown("### Alternatives considered")
                for cand in candidates:
                    cand_id = cand.get("metric_id")
                    cand_desc = cand.get("description") or cand.get("canonical_name") or ""
                    row = st.container()
                    with row:
                        cols = st.columns([0.68, 0.32])
                        with cols[0]:
                            st.markdown(f"**`{cand_id}`**  \n{cand_desc}")
                        with cols[1]:
                            remember_key = f"remember::{cand_id}"
                            remember = st.checkbox("Remember", key=remember_key)
                            if st.button("Select", key=f"select::{cand_id}", use_container_width=True):
                                team = context.get("team") or "unknown"
                                if remember and team in ("marketing", "finance", "unknown"):
                                    engine.save_alias(query, team, cand_id)
                                st.session_state.last_selected_metric_id = cand_id
                                selected_metric_id = cand_id

                                # Build a resolved-shaped intent for summary display.
                                st.session_state.last_intent = {
                                    "status": "resolved",
                                    "resolved_metric": cand,
                                    "confidence": 1.0 if remember else 0.6,
                                    "reason": "Saved alias; meaning preserved from previous step."
                                    if remember
                                    else "User selected meaning from alternatives.",
                                }

                                contract, err = resolve_contract(
                                    client,
                                    metric_id=cand_id,
                                    workspace_id=workspace_id,
                                    context=context,
                                )
                                st.session_state.last_contract = contract
                                st.session_state.last_contract_error = err
                                st.session_state.followup_applied = False
                                st.rerun()

        else:
            st.error("No match.")
            st.caption(reason or "The system could not map this question to a known concept.")

        st.divider()

        st.subheader("📜 Semantic Contract (typed)")
        contract = st.session_state.last_contract
        contract_err = st.session_state.last_contract_error

        if contract_err:
            st.warning(f"Contract unavailable: {contract_err}")
            st.caption("Tip: run Ingest so the metric has events/overlays to resolve.")
        elif not contract:
            st.info("Resolve a concept to view the machine-facing contract.")
        else:
            projected = contract_projection(contract)
            if st.session_state.followup_applied:
                projected = apply_followup_to_contract(projected, st.session_state.last_followup)
            with st.expander("View contract JSON", expanded=True):
                st.json(projected)
