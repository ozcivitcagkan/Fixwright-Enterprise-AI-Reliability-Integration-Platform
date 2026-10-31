from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

# Built by `npm run build` in frontend/. Read on every request so tests can point it elsewhere.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

# Built asset names contain a hash of their content, so a changed file always gets a new name
ASSET_CACHE = "public, max-age=31536000, immutable"
# The browser asks again every time, so a new deploy shows up at once
NO_CACHE = "no-cache"

router = APIRouter(include_in_schema=False)


@router.get("/")
@router.get("/ui")
def redirect_to_ui():
    return RedirectResponse("/ui/")


@router.get("/ui/{path:path}")
def serve_ui(path: str):
    dist = FRONTEND_DIST.resolve()
    index = dist / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404)

    is_asset = path.startswith("assets/")
    file = (dist / path).resolve()
    # Never serve a file outside the build folder, e.g. /ui/../.env
    if file.is_relative_to(dist) and file.is_file():
        return FileResponse(file, headers={"Cache-Control": ASSET_CACHE if is_asset else NO_CACHE})
    if is_asset:
        raise HTTPException(status_code=404)

    # Any other path is a page of the app (/ui/login, /ui/incidents/INC-1); the app picks what to show
    return FileResponse(index, headers={"Cache-Control": NO_CACHE})