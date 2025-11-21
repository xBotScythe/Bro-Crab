from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from web.api.routes import finds

CLIENT_DIST = Path(__file__).resolve().parents[1] / "client" / "dist"


def create_app() -> FastAPI:
    # shared fastapi instance for uvicorn and tests
    app = FastAPI(title="dew map service", version="1.0.0")

    # allow the vite dev server + production origins to hit the api
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # api routes stay under /api
    app.include_router(finds.router, prefix="/api")

    _mount_client(app)
    return app


def _mount_client(app: FastAPI) -> None:
    # serve the built spa if it exists, fall back to a json root handler otherwise
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
