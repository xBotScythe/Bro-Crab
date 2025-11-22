from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from web.api.routes import finds, admin as admin_routes

ROOT = Path(__file__).resolve().parents[2]
CLIENT_DIST = ROOT / "web" / "client" / "dist"
UPLOADS_DIR = ROOT / "data" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def create_app() :
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
    # mount admin endpoints under same /api namespace for reuse
    app.include_router(admin_routes.router, prefix="/api")

    _mount_static(app)
    return app


def _mount_static(app: FastAPI):
    app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

    index_path = CLIENT_DIST / "index.html"
    assets_dir = CLIENT_DIST / "assets"
    vite_icon = CLIENT_DIST / "vite.svg"

    if CLIENT_DIST.exists() and index_path.exists():
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
        if vite_icon.exists():
            @app.get("/vite.svg", include_in_schema=False)
            async def _vite_icon():
                return FileResponse(vite_icon)

        @app.get("/", include_in_schema=False)
        async def _root_spa():
            return FileResponse(index_path)

        @app.get("/admin", include_in_schema=False)
        @app.get("/admin/{rest:path}", include_in_schema=False)
        async def _admin_spa(rest: str = ""):
            return FileResponse(index_path)

        @app.get("/{full_path:path}", include_in_schema=False)
        async def _spa_fallback(full_path: str = ""):
            if full_path.startswith("api") or full_path.startswith("uploads") or full_path.startswith("assets") or full_path == "vite.svg":
                raise HTTPException(status_code=404, detail="Not Found")
            return FileResponse(index_path)
        return

    @app.get("/")
    def _placeholder():
        return {"status": "ok", "detail": "client build missing, run npm run build"}

    @app.get("/admin", include_in_schema=False)
    @app.get("/admin/{rest:path}", include_in_schema=False)
    async def _admin_placeholder(rest: str = ""):
        return JSONResponse({"detail": "admin ui build missing, run npm run build"}, status_code=503)


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web.api.main:app", host="0.0.0.0", port=8000, reload=True)
