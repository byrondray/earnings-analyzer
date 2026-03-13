import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db, get_engine
from app.db.models import Base
from app.routers import analysis, calendar, chart, favorites, news, public_pages
from app.services.cache import close_redis

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()
    for attempt in range(5):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
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

def _get_cors_origins() -> list[str]:
    extra = os.environ.get("CORS_ORIGINS", "")
    origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
    if extra:
        origins.extend(o.strip() for o in extra.split(",") if o.strip())
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

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = (STATIC_DIR / full_path).resolve()
        if not file_path.is_relative_to(STATIC_DIR.resolve()):
            return FileResponse(STATIC_DIR / "index.html")
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
