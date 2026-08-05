from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import Settings


@dataclass(frozen=True)
class PortalUser:
    id: str
    email: str
    full_name: str
    organization: str
    province: str
    role: str
    membership_status: str
    demo: bool = False

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def can_access_portal(self) -> bool:
        return self.is_admin or self.membership_status == "active"


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str


DEMO_USERS = {
    "member": PortalUser(
        id="demo-member",
        email="member@demo.aiacanada.com",
        full_name="Jordan Martin",
        organization="Maple Auto Service",
        province="ON",
        role="member",
        membership_status="active",
        demo=True,
    ),
    "admin": PortalUser(
        id="demo-admin",
        email="admin@demo.aiacanada.com",
        full_name="Avery Chen",
        organization="AIA Canada",
        province="ON",
        role="admin",
        membership_status="active",
        demo=True,
    ),
}


class SupabaseAuth:
    """Small server-side wrapper around supabase-py authentication."""

    def __init__(self, settings: Settings):
        if not settings.supabase_configured:
            raise RuntimeError("Supabase is not configured.")
        from supabase import ClientOptions, create_client

        options = ClientOptions(auto_refresh_token=False, persist_session=False)
        self.client = create_client(
            settings.supabase_url,
            settings.supabase_publishable_key,
            options=options,
        )

    def sign_in(self, email: str, password: str) -> tuple[PortalUser, SessionTokens]:
        response = self.client.auth.sign_in_with_password({"email": email, "password": password})
        if not response.user or not response.session:
            raise RuntimeError("Sign-in did not return a user session.")
        # get_user verifies the access token with the Auth server. Do not authorize from
        # unverified, locally decoded session claims.
        verified = self.client.auth.get_user(response.session.access_token)
        if not verified.user:
            raise RuntimeError("The authenticated user could not be verified.")
        profile = self._profile(str(verified.user.id))
        return self._portal_user(verified.user, profile), SessionTokens(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
        )

    def restore(self, tokens: SessionTokens) -> tuple[PortalUser, SessionTokens]:
        response = self.client.auth.set_session(tokens.access_token, tokens.refresh_token)
        if not response.user or not response.session:
            raise RuntimeError("Your session has expired. Please sign in again.")
        verified = self.client.auth.get_user(response.session.access_token)
        if not verified.user:
            raise RuntimeError("Your session could not be verified.")
        profile = self._profile(str(verified.user.id))
        return self._portal_user(verified.user, profile), SessionTokens(
            access_token=response.session.access_token,
            refresh_token=response.session.refresh_token,
        )

    def sign_out(self) -> None:
        self.client.auth.sign_out()

    def _profile(self, user_id: str) -> dict[str, Any]:
        response = self.client.table("profiles").select(
            "id, full_name, organization, province, role, membership_status"
        ).eq("id", user_id).single().execute()
        return dict(response.data or {})

    @staticmethod
    def _portal_user(auth_user: Any, profile: dict[str, Any]) -> PortalUser:
        return PortalUser(
            id=str(auth_user.id),
            email=str(auth_user.email or ""),
            full_name=str(profile.get("full_name") or auth_user.email or "Member"),
            organization=str(profile.get("organization") or ""),
            province=str(profile.get("province") or ""),
            role=str(profile.get("role") or "member"),
            membership_status=str(profile.get("membership_status") or "pending"),
        )


def authenticated_client(settings: Settings, tokens: SessionTokens):
    """Return a user-scoped client so Postgres and Storage RLS remain authoritative."""
    from supabase import ClientOptions, create_client

    options = ClientOptions(auto_refresh_token=False, persist_session=False)
    client = create_client(
        settings.supabase_url,
        settings.supabase_publishable_key,
        options=options,
    )
    client.auth.set_session(tokens.access_token, tokens.refresh_token)
    return client
