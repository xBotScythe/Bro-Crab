from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from web.api.routes import finds

ROOT = Path(__file__).resolve().parents[2]
CLIENT_DIST = ROOT / "web" / "client" / "dist"
UPLOADS_DIR = ROOT / "data" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def create_app() -> FastAPI:
    # shared fastapi instance for uvicorn and tests
    app = FastAPI(title="dew map service", version="1.1.0")

    # allow the vite dev server + production origins to hit the api
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # api routes stay under /api
    app.include_router(finds.router, prefix="/api")

    _mount_static(app)
    return app


def _mount_static(app: FastAPI) -> None:
    app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

    if CLIENT_DIST.exists():
        app.mount("/", StaticFiles(directory=CLIENT_DIST, html=True), name="client")
        return

    @app.get("/")
    def _placeholder():
        return {"status": "ok", "detail": "client build missing, run npm run build"}


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web.api.main:app", host="0.0.0.0", port=8000, reload=True)
