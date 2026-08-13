import os, json, base64
from email.message import EmailMessage
from google.oauth2 import service_account
from googleapiclient.discovery import build
from django.template.loader import render_to_string
from collections import OrderedDict
from datetime import datetime
from decimal import Decimal

from NovaKelvin.settings import BASE_DIR
from ticketing.models import Ticket
from email.mime.image import MIMEImage
from django.core.mail import EmailMultiAlternatives

img = MIMEImage(open(BASE_DIR + "templates/emails/check.png", "rb").read())
img.add_header("Content-ID", "<check_icon>")
img.add_header("Content-Disposition", "inline")

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
SENDER = "tickets@kelvin-symphony.co.uk"   # the mailbox to send as

info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
creds = service_account.Credentials.from_service_account_info(
    info, scopes=SCOPES
).with_subject(SENDER)

service = build("gmail", "v1", credentials=creds)


CURRENCY_SYMBOLS = {"GBP": "£", "USD": "$", "EUR": "€"}


def build_order_confirmation_context(order):
    symbol = CURRENCY_SYMBOLS.get(order.currency, "")
    money = lambda amount: f"{symbol}{amount:.2f}"

    # Order holds individual Ticket rows (OrderItem is commented out),
    # so group them by ticket type to get quantity + line total.
    tickets = order.tickets.select_related("ticket_type", "for_concert").all()

    groups, subtotal = OrderedDict(), Decimal("0")
    for t in tickets:
        tt = t.ticket_type
        if tt is None:
            continue
        row = groups.setdefault(
            tt.pk,
            {"name": tt.ticket_label, "quantity": 0, "unit": tt.price, "position": tt.position},
        )
        row["quantity"] += 1
        subtotal += tt.price

    # TicketType.position controls display order on the site — honour it here too.
    ordered = sorted(groups.values(), key=lambda r: (r["position"], r["name"]))
    items = [
        {"name": r["name"], "quantity": r["quantity"], "line_total": money(r["unit"] * r["quantity"])}
        for r in ordered
    ]

    # Concert isn't linked on Order directly — reach it through the tickets.
    concert = next((t.for_concert for t in tickets if t.for_concert), None)

    # No donation field on the model: reconstruct it as (charged - ticket subtotal),
    # which reproduces the checkout's Subtotal / Donation / Total split.
    diff = order.total_amount - subtotal
    donation = money(diff) if diff > 0 else None

    # First name reads better in the greeting; fall back to the full name.
    name = (order.customer_name or "").strip()

    return {
        "customer_name": name.split(" ")[0] if name else "",
        "order_number": f"#{order.id}",
        "concert_title": concert.concert_name if concert else "",
        # day/month via .day avoids the non-portable %-d / %#d strftime flag
        "concert_date": (
            f"{concert.concert_date.strftime('%A')} {concert.concert_date.day} "
            f"{concert.concert_date.strftime('%B %Y')}"
        ) if concert else "",
        "concert_time": concert.concert_time.strftime("%I:%M %p").lstrip("0") if concert else "",
        "venue": concert.concert_location if concert else "",
        "items": items,
        "subtotal": money(subtotal),
        "donation": donation,                 # None → the row is auto-hidden by the template
        "total": money(order.total_amount),
        "support_email": "info@kelvin-ensemble.co.uk",
        "current_year": datetime.now().year,
        # "tickets_url": request.build_absolute_uri(reverse("order-detail", args=[order.id])),
        # "logo_url": "https://staging.kelvin-symphony.co.uk/static/img/header/logo.png",
        # check_icon_src left unset → template uses cid:check_icon
    }

def send_confirmation_email(order):
    ctx = build_order_confirmation_context(order)

    text_body = render_to_string("emails/order_confirmation.txt", ctx)
    html_body = render_to_string("emails/order_confirmation.html", ctx)

    message = EmailMultiAlternatives(
        f"Your tickets — {ctx['concert_title']}", text_body,
        "tickets@kelvin-symphony.co.uk", [order.customer_email],
    )
    message.attach_alternative(html_body, "text/html")
    message["From"] = SENDER
    message["To"] = order.customer_email
    message["Subject"] = "KSO - Order Confirmation"
    message.attach(img)

