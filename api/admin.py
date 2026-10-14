"""
Administrator API (role-based access control).

Every route requires an authenticated administrator. Guard rails stop an admin
from locking the platform out: you cannot disable or demote yourself, and the
last active administrator can never be removed.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from database.auth_tokens_repository import revoke_all_refresh_tokens_for_user
from database.user_repository import (
    count_active_admins,
    get_user_by_id,
    list_users,
    set_user_active,
    set_user_admin,
)
from security.dependencies import require_admin, serialize_user

router = APIRouter(
    prefix="/admin",
    tags=["Administration"],
)


class UserUpdate(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None


@router.get("/users")
def users(
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin=Depends(require_admin),
):
    total, rows = list_users(search, limit, offset)

    return {
        "success": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "users": [serialize_user(row) for row in rows],
    }


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    admin=Depends(require_admin),
):
    target = get_user_by_id(user_id)

    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")

    is_self = target["id"] == admin["id"]
    removes_admin = (
        payload.is_admin is False or payload.is_active is False
    ) and target["is_admin"]

    if is_self and (payload.is_active is False or payload.is_admin is False):
        raise HTTPException(
            status_code=400,
            detail="You cannot disable or demote your own account.",
        )

    if removes_admin and target["is_active"] and count_active_admins() <= 1:
        raise HTTPException(
            status_code=400,
            detail="At least one active administrator must remain.",
        )

    if payload.is_admin is not None:
        set_user_admin(user_id, payload.is_admin)

    if payload.is_active is not None:
        set_user_active(user_id, payload.is_active)

        if payload.is_active is False:
            # Cut off refresh capability now; the disabled flag already blocks
            # any access token still in circulation on its next request.
            revoke_all_refresh_tokens_for_user(user_id)

    return {"success": True, "user": serialize_user(get_user_by_id(user_id))}


@router.post("/users/{user_id}/revoke-sessions")
def revoke_sessions(user_id: int, admin=Depends(require_admin)):
    if get_user_by_id(user_id) is None:
        raise HTTPException(status_code=404, detail="User not found.")

    revoke_all_refresh_tokens_for_user(user_id)

    return {"success": True, "message": "All sessions revoked."}
