import os, json, base64
from datetime import datetime
from functools import lru_cache

from email.mime.image import MIMEImage

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Uses the (legacy) Admin SDK Directory API rather than Cloud Identity Groups: Cloud Identity's
# memberships.create only accepts emails that already resolve to a Google identity, which rules
# out most real subscribers (work/uni addresses, custom domains). The Directory API's Members
# resource accepts any email, like a classic mailing list — but it requires the impersonated
# account to hold the Workspace "Groups" admin privilege, not just group-owner status.
SCOPES = ["https://www.googleapis.com/auth/admin.directory.group.member"]
GROUP_EMAIL = os.environ.get("NEWSLETTER_GROUP_EMAIL", "mailing@kelvin-symphony.co.uk")
GROUP_MANAGER = os.environ.get("NEWSLETTER_GROUP_MANAGER", "tickets@kelvin-symphony.co.uk")


TOKEN_MAX_AGE = 60 * 60 * 24 * 3  # confirmation links last 3 days

# Confirmation email for each action: (subject, template name). The action is also part of
# the signing salt, so a subscribe link can't be used to unsubscribe and vice versa.
CONFIRMATION_EMAILS = {
    "subscribe": ("Confirm your subscription", "newsletter_subscribe"),
    "unsubscribe": ("Confirm unsubscribe", "newsletter_unsubscribe"),
}


class AlreadySubscribed(Exception):
    pass


class NotSubscribed(Exception):
    pass


@lru_cache(maxsize=1)
def _directory_service():
    # Built lazily so a missing/invalid credential doesn't break the whole site at import time
    info = json.loads(base64.b64decode(os.environ["GOOGLE_SERVICE_ACCOUNT_B64"]))
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=SCOPES
    ).with_subject(GROUP_MANAGER)
    return build("admin", "directory_v1", credentials=creds, cache_discovery=False)


def subscribe(email):
    """Add `email` to the newsletter Google Group as a regular member."""
    try:
        _directory_service().members().insert(
            groupKey=GROUP_EMAIL, body={"email": email, "role": "MEMBER"}
        ).execute()
    except HttpError as e:
        # 409 = member already exists
        if e.resp.status == 409:
            raise AlreadySubscribed(email)
        raise


def membership_name(email):
    """Confirm `email` is a member of the group, or raise NotSubscribed."""
    try:
        return _directory_service().members().get(groupKey=GROUP_EMAIL, memberKey=email).execute()["email"]
    except HttpError as e:
        if e.resp.status == 404:
            raise NotSubscribed(email)
        raise


def unsubscribe(email):
    """Remove `email` from the newsletter Google Group."""
    try:
        _directory_service().members().delete(groupKey=GROUP_EMAIL, memberKey=email).execute()
    except HttpError as e:
        if e.resp.status == 404:
            raise NotSubscribed(email)
        raise


def make_token(email, action):
    return signing.dumps(email, salt=f"newsletter-{action}")


def read_token(token, action):
    """Return the email in `token`. Raises signing.SignatureExpired / signing.BadSignature."""
    return signing.loads(token, salt=f"newsletter-{action}", max_age=TOKEN_MAX_AGE)


def send_confirmation_email(email, action, confirm_url):
    """Email `confirm_url` to `email` to confirm `action` ("subscribe" or "unsubscribe")."""
    # Imported here so the Gmail client (built at import time) is only needed when sending
    from ticketing.email_handler import service, SENDER

    subject, template = CONFIRMATION_EMAILS[action]
    ctx = {
        "confirm_url": confirm_url,
        "group_email": GROUP_EMAIL,
        "expiry_days": TOKEN_MAX_AGE // (60 * 60 * 24),
        "support_email": "info@kelvin-symphony.co.uk",
        "current_year": datetime.now().year,
    }
    message = EmailMultiAlternatives(
        subject,
        render_to_string(f"emails/{template}.txt", ctx),
        SENDER, [email],
    )
    message.attach_alternative(render_to_string(f"emails/{template}.html", ctx), "text/html")

    # Header logo, referenced in the template as cid:kso_logo
    with open(settings.BASE_DIR / "templates" / "emails" / "logo.png", "rb") as f:
        logo = MIMEImage(f.read())
    logo.add_header("Content-ID", "<kso_logo>")
    logo.add_header("Content-Disposition", "inline")
    message.attach(logo)

    raw = base64.urlsafe_b64encode(message.message().as_bytes()).decode()
    return service.users().messages().send(userId="me", body={"raw": raw}).execute()
