"""Google OIDC sign-in for the Django admin.

Replaces the old django_saml2_auth integration, which relied on the Google
Workspace SAML app to reject non-Workspace accounts on Google's side. Google's
generic OAuth/OIDC client has no such app-assignment restriction, so entitlement
now has to be enforced here instead, via GOOGLE_WORKSPACE_DOMAIN.
"""
from django.conf import settings
from django.contrib.auth.models import Group

from mozilla_django_oidc.auth import OIDCAuthenticationBackend


class GoogleWorkspaceOIDCBackend(OIDCAuthenticationBackend):
    def verify_claims(self, claims):
        if not super().verify_claims(claims):
            return False

        if not claims.get("email_verified"):
            return False

        allowed_domain = settings.GOOGLE_WORKSPACE_DOMAIN
        email = claims.get("email", "")
        return email.lower().endswith(f"@{allowed_domain}")

    def get_username(self, claims):
        # Matches the convention from the previous SAML setup, where email was
        # used as the username (ATTRIBUTES_MAP -> username: user.email)
        return claims["email"].lower()

    def create_user(self, claims):
        user = super().create_user(claims)
        user.first_name = claims.get("given_name", "")
        user.last_name = claims.get("family_name", "")
        user.is_staff = True
        user.is_active = True
        user.is_superuser = False
        user.save()

        committee_group, _ = Group.objects.get_or_create(name="Committee")
        user.groups.set([committee_group])

        return user
