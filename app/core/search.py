from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Metric, MetricAlias


def _rank_match(query: str, candidate: str) -> Optional[int]:
    """
    Lower is better.
    exact (0) > prefix (1) > substring (2) > no match (None)
    """
    q = (query or "").lower()
    c = (candidate or "").lower()
    if not q:
        return None
    if q == c:
        return 0
    if c.startswith(q):
        return 1
    if q in c:
        return 2
    return None


def search_metrics(db: Session, workspace_id: str, query: str, limit: int = 20) -> list[dict]:
    # MVP: no vectors. rank metric_id, canonical_name, alias_name.
    q = (query or "").strip()
    if not q:
        return []

    metrics = list(
        db.execute(select(Metric).where(Metric.workspace_id == workspace_id)).scalars()
    )
    aliases = list(
        db.execute(select(MetricAlias).where(MetricAlias.workspace_id == workspace_id)).scalars()
    )

    alias_by_metric: dict[str, list[MetricAlias]] = {}
    for a in aliases:
        alias_by_metric.setdefault(a.metric_id, []).append(a)

    scored: list[tuple[tuple[int, int, str], dict]] = []
    for m in metrics:
        ranks: list[tuple[int, str]] = []
        r_id = _rank_match(q, m.metric_id)
        if r_id is not None:
            ranks.append((r_id, "metric_id"))
        r_name = _rank_match(q, m.canonical_name)
        if r_name is not None:
            ranks.append((r_name, "canonical_name"))

        best_alias_rank = None
        best_alias = None
        for a in alias_by_metric.get(m.metric_id, []):
            r = _rank_match(q, a.alias_name)
            if r is None:
                continue
            if best_alias_rank is None or r < best_alias_rank:
                best_alias_rank = r
                best_alias = a
        if best_alias_rank is not None:
            ranks.append((best_alias_rank, "alias_name"))

        if not ranks:
            continue

        best_rank, best_field = sorted(ranks, key=lambda x: x[0])[0]

        # exact id should beat exact alias/canonical; use a secondary weight:
        field_weight = 0 if best_field == "metric_id" else 1
        sort_key = (best_rank, field_weight, m.metric_id)

        scored.append(
            (
                sort_key,
                {
                    "metric_id": m.metric_id,
                    "canonical_name": m.canonical_name,
                    "description": m.description,
                    "match": {
                        "field": best_field,
                        "rank": best_rank,
                    },
                },
            )
        )

    scored.sort(key=lambda x: x[0])
    return [row for _, row in scored[:limit]]
