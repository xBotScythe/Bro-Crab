import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Cookie, status, Query
from fastapi.responses import JSONResponse

from utils import admin_auth
from utils.dew_map_manager import _connect as dew_connect, delete_find

router = APIRouter(prefix="/admin", tags=["admin"])

# let env override cookie name/flags when deployed
SESSION_COOKIE = os.getenv("ADMIN_SESSION_COOKIE", "admin_session")
COOKIE_SECURE = os.getenv("ADMIN_SESSION_SECURE", "0") == "1"


# trim login payloads and enforce required fields
def _ensure_payload(payload: dict) :
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_payload")
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if not username or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing_credentials")
    return {"username": username, "password": password}


# gate admin endpoints so only valid sessions pass
def _admin_dependency(session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    user = admin_auth.get_user_for_session(session_token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    return {"id": user["id"], "username": user["username"]}


@router.post("/login")
async def admin_login(payload: dict):
    creds = _ensure_payload(payload)
    user = admin_auth.authenticate(creds["username"], creds["password"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    token, expires_at = admin_auth.create_session(user["id"])
    res = JSONResponse({"ok": True, "username": user["username"]})
    res.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=admin_auth.SESSION_TTL_MINUTES * 60,
        path="/",
    )
    return res


@router.post("/logout")
async def admin_logout(session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)):
    if session_token:
        admin_auth.delete_session(session_token)
    res = JSONResponse({"ok": True})
    res.delete_cookie(SESSION_COOKIE, path="/")
    return res


@router.get("/me")
async def admin_me(current=Depends(_admin_dependency)):
    return current


@router.get("/finds")
async def admin_finds(limit: int = Query(25, ge=1, le=200), current=Depends(_admin_dependency)):
    with dew_connect() as conn:
        rows = conn.execute(
            """
            SELECT id, flavor, size, location_name, address, latitude, longitude, image_url, time_zone, created_at, submitted_by
            FROM finds
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "flavor": row["flavor"],
            "size": row["size"],
            "locationName": row["location_name"],
            "address": row["address"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "imageUrl": row["image_url"],
            "timeZone": row["time_zone"],
            "createdAt": row["created_at"],
            "submittedBy": row["submitted_by"],
        }
        for row in rows
    ]


@router.delete("/finds/{find_id}")
async def admin_delete_find(find_id: str, current=Depends(_admin_dependency)):
    # wrap existing delete helper so admin ui can prune bad entries
    deleted = delete_find(find_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="find_not_found")
    return {"ok": True, "id": find_id}
