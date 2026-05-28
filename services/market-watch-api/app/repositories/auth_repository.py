from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import psycopg


ConnectionFactory = Callable[[], AbstractContextManager[psycopg.Connection]]


class AuthRepository:
    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def find_user_by_username(self, username: str) -> dict[str, Any] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select id, username, email, display_name, password_hash, status
                    from public.auth_users
                    where lower(username) = lower(%(username)s)
                       or lower(email) = lower(%(username)s)
                    limit 1;
                    """,
                    {"username": username},
                )
                row = cursor.fetchone()
                return dict(row) if row else None

    def create_session(
        self,
        *,
        user_id: int,
        token_hash: str,
        expires_at: str,
        active_client_id: str | None,
    ) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.auth_sessions (user_id, session_token_hash, active_client_id, active_role_id, expires_at)
                    values (%(user_id)s, %(token_hash)s, %(active_client_id)s, null, %(expires_at)s::timestamptz);
                    """,
                    {
                        "user_id": user_id,
                        "token_hash": token_hash,
                        "active_client_id": active_client_id,
                        "expires_at": expires_at,
                    },
                )
                connection.commit()

    def revoke_session(self, *, token_hash: str) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update public.auth_sessions
                    set revoked_at = now()
                    where session_token_hash = %(token_hash)s
                      and revoked_at is null;
                    """,
                    {"token_hash": token_hash},
                )
                connection.commit()

    def session_context(self, *, token_hash: str) -> dict[str, Any] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    with current_session as (
                      select
                        s.id as session_id,
                        s.active_client_id,
                        s.active_role_id,
                        u.id as user_id,
                        u.username,
                        u.email,
                        u.display_name
                      from public.auth_sessions s
                      join public.auth_users u
                        on u.id = s.user_id
                      where s.session_token_hash = %(token_hash)s
                        and s.revoked_at is null
                        and s.expires_at > now()
                        and u.status = 'active'
                      limit 1
                    ),
                    admin_capability as (
                      select
                        su.user_id,
                        exists (
                          select 1
                          from public.auth_user_roles aur
                          where aur.user_id = su.user_id
                            and aur.role_id = 'system-admin'
                        ) as can_simulate_roles
                      from current_session su
                    ),
                    role_candidates as (
                      select ur.user_id, r.id as role, r.label as role_label, r.scope
                      from public.auth_user_roles ur
                      join public.auth_roles r
                        on r.id = ur.role_id
                      union
                      select ac.user_id, r.id as role, r.label as role_label, r.scope
                      from admin_capability ac
                      cross join public.auth_roles r
                      where ac.can_simulate_roles = true
                    ),
                    ranked_roles as (
                      select
                        rc.user_id,
                        rc.role,
                        rc.role_label,
                        rc.scope,
                        ac.can_simulate_roles,
                        cs.active_role_id is not null and rc.role = cs.active_role_id as is_role_simulated,
                        row_number() over (
                          partition by rc.user_id
                          order by case when cs.active_role_id is not null and rc.role = cs.active_role_id then 0 else 1 end,
                          case rc.role
                            when 'system-admin' then 1
                            when 'system-user' then 2
                            when 'client-admin' then 3
                            when 'client-viewer' then 4
                            else 99
                          end
                        ) as rn
                      from role_candidates rc
                      join current_session cs
                        on cs.user_id = rc.user_id
                      join admin_capability ac
                        on ac.user_id = rc.user_id
                    ),
                    ranked_clients as (
                      select
                        uc.user_id,
                        c.id::text as client_id,
                        c.name as client_name,
                        c.mode as client_mode,
                        row_number() over (
                          partition by uc.user_id
                          order by case
                            when su.active_client_id is not null and c.id::text = su.active_client_id then 0
                            when uc.is_default then 1
                            else 2
                          end, c.id
                        ) as rn
                      from public.auth_user_clients uc
                      join public.auth_clients c
                        on c.id = uc.client_id
                       and c.status = 'active'
                      join current_session su
                        on su.user_id = uc.user_id
                    )
                    select
                      su.session_id,
                      su.user_id::text as user_id,
                      su.username,
                      su.email,
                      su.display_name,
                      rr.role,
                      rr.role_label,
                      rr.scope as role_scope,
                      rr.can_simulate_roles,
                      rr.is_role_simulated,
                      rc.client_id,
                      rc.client_name,
                      rc.client_mode
                    from current_session su
                    join ranked_roles rr
                      on rr.user_id = su.user_id
                     and rr.rn = 1
                    left join ranked_clients rc
                      on rc.user_id = su.user_id
                     and rc.rn = 1
                    limit 1;
                    """,
                    {"token_hash": token_hash},
                )
                row = cursor.fetchone()
                return dict(row) if row else None

    def session_owner_can_simulate_roles(self, *, token_hash: str) -> bool:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select exists (
                      select 1
                      from public.auth_sessions s
                      join public.auth_user_roles ur
                        on ur.user_id = s.user_id
                       and ur.role_id = 'system-admin'
                      where s.session_token_hash = %(token_hash)s
                        and s.revoked_at is null
                        and s.expires_at > now()
                    ) as allowed;
                    """,
                    {"token_hash": token_hash},
                )
                row = cursor.fetchone()
                return bool(row and row["allowed"])

    def set_session_active_role(self, *, token_hash: str, role_id: str | None) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update public.auth_sessions
                    set active_role_id = %(role_id)s
                    where session_token_hash = %(token_hash)s
                      and revoked_at is null
                      and expires_at > now();
                    """,
                    {"token_hash": token_hash, "role_id": role_id},
                )
                connection.commit()

    def list_users(self) -> list[dict[str, Any]]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    with available_clients as (
                      select jsonb_agg(
                        jsonb_build_object('value', id::text, 'label', name)
                        order by name
                      ) as options
                      from public.auth_clients
                      where status = 'active'
                    )
                    select
                      u.id::text as id,
                      u.username,
                      u.email,
                      u.display_name,
                      u.status,
                      min(r.id) as primary_role_id,
                      min(uc.client_id)::text as default_client_id,
                      coalesce(string_agg(distinct r.id, ', '), '') as roles,
                      coalesce(string_agg(distinct c.name, ', '), '') as clients,
                      (select options from available_clients) as client_options
                    from public.auth_users u
                    left join public.auth_user_roles ur on ur.user_id = u.id
                    left join public.auth_roles r on r.id = ur.role_id
                    left join public.auth_user_clients uc on uc.user_id = u.id
                    left join public.auth_clients c on c.id = uc.client_id
                    group by u.id, u.username, u.email, u.display_name, u.status
                    order by u.username;
                    """
                )
                return [dict(row) for row in cursor.fetchall()]

    def create_user(
        self,
        *,
        username: str,
        email: str,
        display_name: str,
        password_hash: str,
        role_ids: list[str],
        client_id: int,
    ) -> dict[str, Any]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.auth_users (username, email, display_name, password_hash, status)
                    values (%(username)s, %(email)s, %(display_name)s, %(password_hash)s, 'active')
                    returning id::text, username, email, display_name, status;
                    """,
                    {
                        "username": username,
                        "email": email,
                        "display_name": display_name,
                        "password_hash": password_hash,
                    },
                )
                user = dict(cursor.fetchone())
                cursor.execute(
                    """
                    insert into public.auth_user_roles (user_id, role_id)
                    select %(user_id)s, unnest(%(role_ids)s::text[]);
                    """,
                    {"user_id": user["id"], "role_ids": role_ids},
                )
                cursor.execute(
                    """
                    insert into public.auth_user_clients (user_id, client_id, is_default)
                    values (%(user_id)s, %(client_id)s, true);
                    """,
                    {"user_id": user["id"], "client_id": client_id},
                )
                connection.commit()
                return user

    def update_user_status(self, *, user_id: int, status: str) -> dict[str, Any] | None:
        return self.update_user(
            user_id=user_id,
            display_name=None,
            password_hash=None,
            status=status,
            role_id=None,
            client_id=None,
        )

    def update_user(
        self,
        *,
        user_id: int,
        display_name: str | None,
        password_hash: str | None,
        status: str | None,
        role_ids: list[str] | None,
        client_id: int | None,
    ) -> dict[str, Any] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update public.auth_users
                    set
                      display_name = coalesce(%(display_name)s, display_name),
                      password_hash = coalesce(%(password_hash)s, password_hash),
                      status = coalesce(%(status)s, status),
                      updated_at = now()
                    where id = %(user_id)s
                    returning id::text, username, email, display_name, status;
                    """,
                    {
                        "user_id": user_id,
                        "display_name": display_name,
                        "password_hash": password_hash,
                        "status": status,
                    },
                )
                row = cursor.fetchone()
                if not row:
                    connection.commit()
                    return None

                if role_ids:
                    cursor.execute("delete from public.auth_user_roles where user_id = %(user_id)s;", {"user_id": user_id})
                    cursor.execute(
                        """
                        insert into public.auth_user_roles (user_id, role_id)
                        select %(user_id)s, unnest(%(role_ids)s::text[]);
                        """,
                        {"user_id": user_id, "role_ids": role_ids},
                    )

                if client_id:
                    cursor.execute("delete from public.auth_user_clients where user_id = %(user_id)s;", {"user_id": user_id})
                    cursor.execute(
                        """
                        insert into public.auth_user_clients (user_id, client_id, is_default)
                        values (%(user_id)s, %(client_id)s, true);
                        """,
                        {"user_id": user_id, "client_id": client_id},
                    )

                connection.commit()
                return dict(row) if row else None

    def list_roles(self) -> list[dict[str, Any]]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                      r.id,
                      r.label,
                      r.scope,
                      r.description,
                      count(distinct ur.user_id)::int as users,
                      count(distinct rp.permission_id)::int as permissions,
                      coalesce(
                        jsonb_agg(
                          distinct jsonb_build_object(
                            'id', u.id::text,
                            'username', u.username,
                            'email', u.email,
                            'display_name', u.display_name,
                            'status', u.status
                          )
                        ) filter (where u.id is not null),
                        '[]'::jsonb
                      ) as assigned_users,
                      coalesce(
                        jsonb_agg(
                          distinct jsonb_build_object(
                            'id', p.id,
                            'label', p.label,
                            'description', p.description
                          )
                        ) filter (where p.id is not null),
                        '[]'::jsonb
                      ) as assigned_permissions
                    from public.auth_roles r
                    left join public.auth_user_roles ur on ur.role_id = r.id
                    left join public.auth_users u on u.id = ur.user_id
                    left join public.auth_role_permissions rp on rp.role_id = r.id
                    left join public.auth_permissions p on p.id = rp.permission_id
                    group by r.id, r.label, r.scope, r.description
                    order by case r.id
                      when 'system-admin' then 1
                      when 'system-user' then 2
                      when 'client-admin' then 3
                      when 'client-viewer' then 4
                      else 99
                    end;
                    """
                )
                return [dict(row) for row in cursor.fetchall()]

    def create_role(self, *, role_id: str, label: str, scope: str, description: str) -> dict[str, Any]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.auth_roles (id, label, scope, description)
                    values (%(id)s, %(label)s, %(scope)s, %(description)s)
                    returning id, label, scope, description;
                    """,
                    {"id": role_id, "label": label, "scope": scope, "description": description},
                )
                row = dict(cursor.fetchone())
                connection.commit()
                return row

    def update_role(
        self,
        *,
        role_id: str,
        label: str | None,
        scope: str | None,
        description: str | None,
    ) -> dict[str, Any] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update public.auth_roles
                    set
                      label = coalesce(%(label)s, label),
                      scope = coalesce(%(scope)s, scope),
                      description = coalesce(%(description)s, description)
                    where id = %(role_id)s
                    returning id, label, scope, description;
                    """,
                    {
                        "role_id": role_id,
                        "label": label,
                        "scope": scope,
                        "description": description,
                    },
                )
                row = cursor.fetchone()
                connection.commit()
                return dict(row) if row else None

    def list_clients(self) -> list[dict[str, Any]]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                      c.id::text as id,
                      c.client_key,
                      c.name,
                      c.market,
                      c.mode,
                      c.status,
                      count(distinct uc.user_id)::int as users
                    from public.auth_clients c
                    left join public.auth_user_clients uc on uc.client_id = c.id
                    group by c.id, c.client_key, c.name, c.market, c.mode, c.status
                    order by c.name;
                    """
                )
                return [dict(row) for row in cursor.fetchall()]

    def create_client(self, *, client_key: str, name: str, market: str, mode: str) -> dict[str, Any]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.auth_clients (client_key, name, market, mode, status)
                    values (%(client_key)s, %(name)s, %(market)s, %(mode)s, 'active')
                    returning id::text, client_key, name, market, mode, status;
                    """,
                    {"client_key": client_key, "name": name, "market": market, "mode": mode},
                )
                row = dict(cursor.fetchone())
                connection.commit()
                return row

    def update_client_status(self, *, client_id: int, status: str) -> dict[str, Any] | None:
        return self.update_client(
            client_id=client_id,
            name=None,
            market=None,
            mode=None,
            status=status,
        )

    def update_client(
        self,
        *,
        client_id: int,
        name: str | None,
        market: str | None,
        mode: str | None,
        status: str | None,
    ) -> dict[str, Any] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update public.auth_clients
                    set
                      name = coalesce(%(name)s, name),
                      market = coalesce(%(market)s, market),
                      mode = coalesce(%(mode)s, mode),
                      status = coalesce(%(status)s, status),
                      updated_at = now()
                    where id = %(client_id)s
                    returning id::text, client_key, name, market, mode, status;
                    """,
                    {
                        "client_id": client_id,
                        "name": name,
                        "market": market,
                        "mode": mode,
                        "status": status,
                    },
                )
                row = cursor.fetchone()
                connection.commit()
                return dict(row) if row else None
