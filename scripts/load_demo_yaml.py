from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml


def _req(
    method: str,
    url: str,
    *,
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
    timeout_s: float = 20.0,
) -> requests.Response:
    return requests.request(method, url, params=params, json=json_body, timeout=timeout_s)


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _metric_exists(base_url: str, workspace_id: str, metric_id: str) -> bool:
    r = _req("GET", f"{base_url}/metrics/{metric_id}", params={"workspace_id": workspace_id})
    return r.status_code == 200


def _get_overlays(base_url: str, workspace_id: str, metric_id: str) -> list[dict]:
    r = _req("GET", f"{base_url}/metrics/{metric_id}/overlays", params={"workspace_id": workspace_id})
    if r.status_code == 200:
        return r.json()
    return []


def _overlay_key(o: dict) -> Tuple[str, int]:
    selector = o.get("selector") or {}
    priority = int(o.get("priority") or 0)
    return (_stable_json(selector), priority)


def _overlay_exists(existing: list[dict], selector: dict, priority: int) -> bool:
    target = (_stable_json(selector or {}), int(priority))
    keys = {_overlay_key(o) for o in existing}
    return target in keys


def _get_history(base_url: str, workspace_id: str, metric_id: str, limit: int = 200) -> list[dict]:
    r = _req(
        "GET",
        f"{base_url}/metrics/{metric_id}/history",
        params={"workspace_id": workspace_id, "limit": limit},
    )
    if r.status_code == 200:
        return r.json()
    return []


def _event_exists(existing: list[dict], candidate: dict) -> bool:
    # Best-effort idempotency: skip if an event with same core identity already exists.
    cand = {
        "event_type": candidate.get("event_type"),
        "source_system": candidate.get("source_system"),
        "source_ref": candidate.get("source_ref") or {},
        "snapshot": candidate.get("snapshot") or {},
    }
    cand_key = _stable_json(cand)
    for e in existing:
        existing_key = _stable_json(
            {
                "event_type": e.get("event_type"),
                "source_system": e.get("source_system"),
                "source_ref": e.get("source_ref") or {},
                "snapshot": e.get("snapshot") or {},
            }
        )
        if existing_key == cand_key:
            return True
    return False


def _pretty(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser(description="Load demo YAML into Memory Core via HTTP API.")
    ap.add_argument("--yaml", default="demo/demo.yaml", help="Path to demo yaml file")
    ap.add_argument("--base-url", default=None, help="Override base_url in yaml (e.g. http://127.0.0.1:8000)")
    ap.add_argument("--workspace-id", default=None, help="Override workspace_id in yaml")
    args = ap.parse_args()

    with open(args.yaml, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    base_url = (args.base_url or doc.get("base_url") or "http://127.0.0.1:8000").rstrip("/")
    workspace_id = args.workspace_id or doc.get("workspace_id") or "default"

    metrics: list[dict] = doc.get("metrics") or []
    if not metrics:
        print("No metrics found in YAML.", file=sys.stderr)
        return 2

    print(f"Using base_url={base_url} workspace_id={workspace_id}")

    # Health
    r = _req("GET", f"{base_url}/health")
    if r.status_code != 200:
        print(f"Health check failed: {r.status_code} {r.text}", file=sys.stderr)
        return 1

    for m in metrics:
        metric_id = m["metric_id"]
        print("\n" + "=" * 72)
        print(f"Metric: {metric_id}")

        # 1) Metric create (skip if exists)
        if _metric_exists(base_url, workspace_id, metric_id):
            print("- metric: exists (skip create)")
        else:
            r = _req(
                "POST",
                f"{base_url}/metrics",
                params={"workspace_id": workspace_id},
                json_body={
                    "metric_id": metric_id,
                    "canonical_name": m["canonical_name"],
                    "description": m.get("description"),
                },
            )
            if r.status_code != 200:
                print(f"- metric: create failed: {r.status_code} {r.text}", file=sys.stderr)
                return 1
            print("- metric: created")

        # 2) Aliases (best-effort idempotent: our API upserts by source_system+source_locator)
        for a in m.get("aliases") or []:
            r = _req(
                "POST",
                f"{base_url}/metrics/{metric_id}/aliases",
                params={"workspace_id": workspace_id},
                json_body=a,
            )
            if r.status_code != 200:
                print(f"- alias: failed: {r.status_code} {r.text}", file=sys.stderr)
                return 1
            print(f"- alias: ok ({a['source_system']}:{a['source_locator']})")

        # 3) Events (skip if same event already exists)
        existing_events = _get_history(base_url, workspace_id, metric_id, limit=500)
        for e in m.get("events") or []:
            if _event_exists(existing_events, e):
                print(f"- event: exists (skip) ({e.get('event_type')} {e.get('source_ref')})")
                continue
            r = _req(
                "POST",
                f"{base_url}/metrics/{metric_id}/events",
                params={"workspace_id": workspace_id},
                json_body=e,
            )
            if r.status_code != 200:
                print(f"- event: failed: {r.status_code} {r.text}", file=sys.stderr)
                return 1
            out = r.json()
            print(f"- event: appended version_id={out.get('version_id')} ({e.get('event_type')})")

        # 4) Overlays (skip if selector+priority already exists)
        existing_overlays = _get_overlays(base_url, workspace_id, metric_id)
        for o in m.get("overlays") or []:
            selector = o.get("selector") or {}
            priority = int(o.get("priority") or 0)
            if _overlay_exists(existing_overlays, selector, priority):
                print(f"- overlay: exists (skip) selector={selector} priority={priority}")
                continue
            r = _req(
                "POST",
                f"{base_url}/metrics/{metric_id}/overlays",
                params={"workspace_id": workspace_id},
                json_body=o,
            )
            if r.status_code != 200:
                print(f"- overlay: failed: {r.status_code} {r.text}", file=sys.stderr)
                return 1
            out = r.json()
            print(f"- overlay: created overlay_id={out.get('overlay_id')} selector={selector} priority={priority}")

        # 5) Resolve and print clearly
        resolves = m.get("resolves") or []
        if resolves:
            print("\nResolve results")
            for item in resolves:
                label = item.get("label") or "resolve"
                ctx = item.get("context") or {}
                r = _req(
                    "POST",
                    f"{base_url}/metrics/{metric_id}/resolve",
                    params={"workspace_id": workspace_id},
                    json_body={"context": ctx},
                )
                if r.status_code != 200:
                    print(f"- resolve({label}): failed: {r.status_code} {r.text}", file=sys.stderr)
                    return 1
                out = r.json()
                print(f"\n[{label}] context={ctx}")
                print("applied_overlays:", out.get("applied_overlays"))
                print("resolved_snapshot:")
                print(_pretty(out.get("resolved_snapshot")))

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

