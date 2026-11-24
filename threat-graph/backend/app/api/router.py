from fastapi import APIRouter

from app.api import analytics, auth, dashboard, feeds, graph, indicators, ingestion, investigations, reports, system

router = APIRouter(prefix="/api")
router.include_router(auth.router)
router.include_router(indicators.router)
router.include_router(ingestion.router)
router.include_router(graph.router)
router.include_router(analytics.router)
router.include_router(investigations.router)
router.include_router(dashboard.router)
router.include_router(feeds.router)
router.include_router(reports.router)
router.include_router(system.router)
