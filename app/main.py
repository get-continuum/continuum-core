from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.events import router as events_router
from app.api.routes.health import router as health_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.overlays import router as overlays_router
from app.api.routes.resolve import router as resolve_router
from app.api.routes.search import router as search_router
from app.api.routes.usage import router as usage_router


app = FastAPI(title="Engram Semantic Memory Core", version="0.1.0")

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(metrics_router)
app.include_router(events_router)
app.include_router(overlays_router)
app.include_router(resolve_router)
app.include_router(search_router)
app.include_router(usage_router)

