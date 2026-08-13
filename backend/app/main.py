import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.database import get_db, get_engine
from app.rate_limit import limiter
from app.routers import analysis, calendar, chart, favorites, news, public_pages
from app.services.cache import close_redis

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed by Alembic migrations (`alembic upgrade head`), run as
    # part of deployment. This just waits for the DB to become reachable.
    engine = get_engine()
    for attempt in range(5):
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            break
        except Exception as exc:
            if attempt == 4:
                raise
            wait = 2 ** attempt
            logger.warning("DB connect attempt %d failed (%s), retrying in %ds...", attempt + 1, exc, wait)
            await asyncio.sleep(wait)
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="Stock Earnings Analyzer",
    description="Analyze stock earnings reports with MCP-powered web search and Claude analysis",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


def _get_cors_origins() -> list[str]:
    extra = get_settings().CORS_ORIGINS
    origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
    if extra:
        for raw in extra.split(","):
            origin = raw.strip()
            if not origin:
                continue
            if origin == "*":
                logger.warning("Ignoring '*' in CORS_ORIGINS: wildcard origins are unsafe with allow_credentials=True")
                continue
            if not (origin.startswith("http://") or origin.startswith("https://")):
                logger.warning("Ignoring CORS_ORIGINS entry missing scheme: %r", origin)
                continue
            origins.append(origin)
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(calendar.router)
app.include_router(analysis.router)
app.include_router(favorites.router)
app.include_router(news.router)
app.include_router(chart.router)
app.include_router(public_pages.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/robots.txt")
async def robots_txt(request: Request):
    sitemap_url = str(request.base_url.replace(path="sitemap.xml"))
    content = "\n".join([
        "User-agent: *",
        "Allow: /",
        "Allow: /calendar",
        "Allow: /stocks/",
        "Disallow: /app",
        "Disallow: /api/",
        f"Sitemap: {sitemap_url}",
    ])
    return PlainTextResponse(content)


@app.get("/sitemap.xml")
async def sitemap_xml(request: Request, db: AsyncSession = Depends(get_db)):
    entries = await public_pages.get_public_sitemap_entries(db)
    base_url = str(request.base_url).rstrip("/")
    content = "\n".join([
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        *[
            "\n".join([
                "  <url>",
                f"    <loc>{base_url}{entry['path']}</loc>",
                *( [f"    <lastmod>{entry['lastmod']}</lastmod>"] if entry.get('lastmod') else [] ),
                f"    <changefreq>{entry['changefreq']}</changefreq>",
                f"    <priority>{entry['priority']}</priority>",
                "  </url>",
            ])
            for entry in entries
        ],
        "</urlset>",
    ])
    return Response(content=content, media_type="application/xml")


if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/app")
    async def serve_app_root():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        file_path = (STATIC_DIR / full_path).resolve()
        if not file_path.is_relative_to(STATIC_DIR.resolve()):
            return FileResponse(STATIC_DIR / "index.html")
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
