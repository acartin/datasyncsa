from typing import Any
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.db import get_connection
from app.core.security import ClientContext, require_client_context


router = APIRouter()


class TableViewCreate(BaseModel):
    view_key: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=120)
    state: dict[str, Any] = Field(default_factory=dict)
    icon: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, max_length=40)
    is_favorite: bool = True


class TableViewUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    state: dict[str, Any] | None = None
    icon: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, max_length=40)
    is_favorite: bool | None = None
    view_order: int | None = Field(default=None, ge=0)


@router.get("")
def list_table_views(
    view_key: str,
    context: ClientContext = Depends(require_client_context),
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select table_view_id, view_key, label, icon, color, scope, is_favorite,
                       view_order, state, created_at, updated_at
                from public.mkt_user_table_view
                where client_id::text = %s
                  and user_id::text = %s
                  and view_key = %s
                order by is_favorite desc, view_order, label
                """,
                (context.client_id, context.user_id, view_key),
            )
            rows = cur.fetchall()
    return {"client_id": context.client_id, "items": rows}


@router.post("", status_code=201)
def create_table_view(
    payload: TableViewCreate,
    context: ClientContext = Depends(require_client_context),
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select coalesce(max(view_order), 0) as max_order
                from public.mkt_user_table_view
                where client_id::text = %s
                  and user_id::text = %s
                  and view_key = %s
                """,
                (context.client_id, context.user_id, payload.view_key),
            )
            max_order = cur.fetchone()["max_order"]
            cur.execute(
                """
                insert into public.mkt_user_table_view
                  (client_id, user_id, view_key, label, icon, color, is_favorite, view_order, state)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                returning table_view_id, view_key, label, icon, color, scope, is_favorite,
                          view_order, state, created_at, updated_at
                """,
                (
                    context.client_id,
                    context.user_id,
                    payload.view_key,
                    payload.label.strip(),
                    payload.icon,
                    payload.color,
                    payload.is_favorite,
                    max_order + 1,
                    json.dumps(payload.state),
                ),
            )
            row = cur.fetchone()
            conn.commit()
    return {"client_id": context.client_id, "view": row}


@router.patch("/{table_view_id}")
def update_table_view(
    table_view_id: int,
    payload: TableViewUpdate,
    context: ClientContext = Depends(require_client_context),
):
    sets: list[str] = []
    params: list[Any] = []

    if payload.label is not None:
        sets.append("label = %s")
        params.append(payload.label.strip())
    if payload.state is not None:
        sets.append("state = %s::jsonb")
        params.append(json.dumps(payload.state))
    if payload.icon is not None:
        sets.append("icon = %s")
        params.append(payload.icon)
    if payload.color is not None:
        sets.append("color = %s")
        params.append(payload.color)
    if payload.is_favorite is not None:
        sets.append("is_favorite = %s")
        params.append(payload.is_favorite)
    if payload.view_order is not None:
        sets.append("view_order = %s")
        params.append(payload.view_order)

    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.extend([table_view_id, context.client_id, context.user_id])
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                update public.mkt_user_table_view
                set {', '.join(sets)}, updated_at = now()
                where table_view_id = %s
                  and client_id::text = %s
                  and user_id::text = %s
                returning table_view_id, view_key, label, icon, color, scope, is_favorite,
                          view_order, state, created_at, updated_at
                """,
                params,
            )
            row = cur.fetchone()
            conn.commit()

    if not row:
        raise HTTPException(status_code=404, detail="Table view not found")
    return {"client_id": context.client_id, "view": row}


@router.delete("/{table_view_id}", status_code=204)
def delete_table_view(
    table_view_id: int,
    context: ClientContext = Depends(require_client_context),
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                delete from public.mkt_user_table_view
                where table_view_id = %s
                  and client_id::text = %s
                  and user_id::text = %s
                returning 1
                """,
                (table_view_id, context.client_id, context.user_id),
            )
            deleted = cur.fetchone()
            conn.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Table view not found")
