from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core import signing
from django.urls import reverse
from urllib.parse import urlencode
from rest_framework.throttling import AnonRateThrottle
from decimal import Decimal
import traceback
import stripe

from ticketing import models as ts_models
from ticketing.webhook_handler import handle_webhook
from .serializers import ConcertSerializer, TicketTypeSummarySerializer
from . import newsletter

# Initialize Stripe with your secret key
stripe.api_key = settings.STRIPE_SECRET_KEY


class ConcertsView(APIView):
    def get(self, request):
        concerts = ts_models.Concert.objects.all()
        serializer = ConcertSerializer(concerts, many=True)
        return Response(serializer.data)

    def post(self, request):
        return Response(status=status.HTTP_401_UNAUTHORIZED)


class ConcertTicketTypesView(APIView):
    """
    GET /api/tickets/concert/tickettypes?concert_id=<ID>
    Returns ticket type details for that concert.
    """

    def get(self, request):
        concert_id = request.query_params.get("concert_id")
        if not concert_id:
            return Response(
                {"detail": "concert_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        concert = get_object_or_404(ts_models.Concert, pk=concert_id)

        # All ticket types for this concert (using related_name="ticket_types")
        ticket_types = concert.ticket_types.all().order_by("position")

        serializer = TicketTypeSummarySerializer(ticket_types, many=True)
        return Response(serializer.data)


class CreateCheckoutSessionView(APIView):
    """
    POST /api/tickets/create-checkout-session/
    Creates a Stripe checkout session for ticket purchase.

    Expected payload:
    {
        "concert_id": 1,
        "line_items": [
            {"ticket_type_id": 1, "quantity": 2},
            {"ticket_type_id": 2, "quantity": 1}
        ]
    }
    """
    # Disable CSRF for webhooks
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        line_items_data = request.data.get("line_items", [])

        if not line_items_data:
            return Response(
                {"detail": "line_items are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            # Build Stripe line items
            stripe_line_items = []
            order_items_data = []

            for item in line_items_data:
                ticket_type_id = item.get("ticket_type_id")
                quantity = item.get("quantity", 0)

                if quantity <= 0:
                    continue

                if (type(ticket_type_id) == int):
                    ticket_type = get_object_or_404(
                        ts_models.TicketType,
                        pk=ticket_type_id,
                    )

                    # Validate availability
                    if quantity > ticket_type.qty_available:
                        return Response(
                            {
                                "detail": f"Only {ticket_type.qty_available} {ticket_type.ticket_label} tickets available."
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    # Use the price_id from your ticket type model
                    stripe_line_items.append({
                        "price": ticket_type.price_id,
                        "quantity": quantity,
                    })

                    # Store order item data for pending order
                    order_items_data.append({
                        'ticket_type': ticket_type,
                        'quantity': quantity,
                        'price_per_ticket': ticket_type.price,
                    })
                    # print("Appended item: {}, qty: {}, price: {}".format(ticket_type, quantity, ticket_type.price))
                else: # Assume if not an int, its a price_id
                    stripe_line_items.append({
                        "price": ticket_type_id,
                        "quantity": quantity,
                    })

            if not stripe_line_items:
                return Response(
                    {"detail": "No valid line items provided."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create Stripe checkout session.
            # `embedded_page` replaced `embedded` in API version 2026-03-25.dahlia,
            # which is the version pinned by stripe-python 15.x.
            checkout_session = stripe.checkout.Session.create(
                ui_mode='embedded_page',
                line_items=stripe_line_items,
                mode='payment',
                redirect_on_completion='never',
                automatic_tax={'enabled': True},
            )

            # Create pending order in database. The totals come from the session
            # Stripe just priced, so donations (which are passed as bare price IDs)
            # are included; the webhook overwrites them with the final amounts.
            order = ts_models.Order.objects.create(
                stripe_session_id=checkout_session.id,
                status='pending',
                customer_email='',  # Will be filled by webhook
                total_amount=Decimal(checkout_session.amount_total or 0) / 100,
                currency=(checkout_session.currency or 'gbp').upper(),
            )

            # Create order items
            # for item_data in order_items_data:
            #     ts_models.OrderItem.objects.create(
            #         order=order,
            #         ticket_type=item_data['ticket_type'],
            #         quantity=item_data['quantity'],
            #         price_per_ticket=item_data['price_per_ticket'],
            #     )

            return Response({
                "client_secret": checkout_session.client_secret,
                "session_id": checkout_session.id,
            })

        except stripe.error.StripeError as e:
            return Response(
                {"detail": f"Stripe error: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"detail": f"Error creating checkout session: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StripeWebhookView(APIView):
    """
    POST /api/tickets/stripe-webhook/
    Handles Stripe webhook events for payment confirmation.
    """

    # Disable CSRF for webhooks
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            return Response(
                {"detail": "Invalid payload"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except stripe.error.SignatureVerificationError:
            return Response(
                {"detail": "Invalid signature"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return handle_webhook(event)


class OrderStatusView(APIView):
    """
    GET /api/tickets/order-status/?session_id=<SESSION_ID>
    Returns the order status, polling this until status is 'confirmed' or 'failed'.
    """

    def get(self, request):
        session_id = request.query_params.get("session_id")

        if not session_id:
            return Response(
                {"detail": "session_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            order = ts_models.Order.objects.get(stripe_session_id=session_id)

            response_data = {
                "status": order.status,
                "order_id": order.id,
            }

            # Only include customer details if order is confirmed
            if order.status == 'confirmed':
                response_data.update({
                    "customer_email": order.customer_email,
                    "customer_name": order.customer_name,
                    "total_amount": str(order.total_amount),
                    "currency": order.currency,
                })

            return Response(response_data)

        except ts_models.Order.DoesNotExist:
            return Response(
                {"detail": "Order not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


class NewsletterSignupThrottle(AnonRateThrottle):
    # Sends a confirmation email per request, so keep it from being hammered.
    # Each throttle needs its own scope, otherwise they share one request history per IP.
    scope = "newsletter_signup"
    rate = "5/hour"


class NewsletterSubscribeConfirmThrottle(AnonRateThrottle):
    scope = "newsletter_subscribe_confirm"
    rate = "20/hour"


class NewsletterUnsubscribeRequestThrottle(AnonRateThrottle):
    # Sends an email per request, so keep this tight
    scope = "newsletter_unsubscribe_request"
    rate = "5/hour"


class NewsletterUnsubscribeConfirmThrottle(AnonRateThrottle):
    scope = "newsletter_unsubscribe_confirm"
    rate = "20/hour"


def _confirmation_url(request, url_name, email, action):
    """Absolute link to the confirm page `url_name`, carrying a signed token for `action`."""
    url = request.build_absolute_uri(reverse(url_name))
    if not settings.DEBUG:
        # Behind the proxy Django sees plain http; links in emails should be https
        url = url.replace("http://", "https://", 1)
    return url + "?" + urlencode({"token": newsletter.make_token(email, action)})


def _read_token_or_error(request, action):
    """Return (email, None) for a valid token, or (None, error Response)."""
    try:
        return newsletter.read_token(str(request.data.get("token", "")), action), None
    except signing.SignatureExpired:
        return None, Response(
            {"detail": "This link has expired. Please request a new one."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except signing.BadSignature:
        return None, Response(
            {"detail": "This link is invalid. Please request a new one."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class NewsletterSignupView(APIView):
    """
    POST /api/newsletter/subscribe/
    Emails a link to confirm subscribing; nobody is added to the group until they click it.
    The response is the same whether or not the address is already subscribed, so it can't
    be used to check who is on the list.

    Expected payload:
    {
        "email": "someone@example.com"
    }
    """
    authentication_classes = []
    permission_classes = []
    throttle_classes = [NewsletterSignupThrottle]

    SENT_MESSAGE = ("Almost done! Check your inbox for a link to confirm your subscription. "
                    "If nothing arrives, you may already be on the list.")

    def post(self, request):
        # Honeypot: real users never see or fill this field
        if request.data.get("website"):
            return Response({"detail": self.SENT_MESSAGE})

        email = str(request.data.get("email", "")).strip().lower()
        try:
            validate_email(email)
        except ValidationError:
            return Response(
                {"detail": "Please enter a valid email address."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            try:
                newsletter.membership_name(email)  # already subscribed: nothing to confirm
            except newsletter.NotSubscribed:
                newsletter.send_confirmation_email(
                    email, "subscribe",
                    _confirmation_url(request, "newsletter_confirm", email, "subscribe"),
                )
        except Exception:
            traceback.print_exc()
            return Response(
                {"detail": "Sorry, something went wrong. Please try again later."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({"detail": self.SENT_MESSAGE})


class NewsletterSubscribeConfirmView(APIView):
    """
    POST /api/newsletter/subscribe/confirm/
    Adds the address in a signed token (from the confirmation email) to the newsletter group.

    Expected payload:
    {
        "token": "<token from the email link>"
    }
    """
    authentication_classes = []
    permission_classes = []
    throttle_classes = [NewsletterSubscribeConfirmThrottle]

    def post(self, request):
        email, error = _read_token_or_error(request, "subscribe")
        if error:
            return error

        try:
            newsletter.subscribe(email)
        except newsletter.AlreadySubscribed:
            return Response({"detail": "You're already subscribed — thanks!"})
        except Exception:
            traceback.print_exc()
            return Response(
                {"detail": "Sorry, something went wrong. Please try again later."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({"detail": "You're subscribed! Thanks for joining our mailing list."})


class NewsletterUnsubscribeRequestView(APIView):
    """
    POST /api/newsletter/unsubscribe/
    Emails a confirmation link to the address if it is subscribed.
    The response is the same either way, so it can't be used to check who is on the list.

    Expected payload:
    {
        "email": "someone@example.com"
    }
    """
    authentication_classes = []
    permission_classes = []
    throttle_classes = [NewsletterUnsubscribeRequestThrottle]

    SENT_MESSAGE = "If that address is subscribed, we've emailed it a link to confirm unsubscribing."

    def post(self, request):
        # Honeypot: real users never see or fill this field
        if request.data.get("website"):
            return Response({"detail": self.SENT_MESSAGE})

        email = str(request.data.get("email", "")).strip().lower()
        try:
            validate_email(email)
        except ValidationError:
            return Response(
                {"detail": "Please enter a valid email address."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            newsletter.membership_name(email)
            newsletter.send_confirmation_email(
                email, "unsubscribe",
                _confirmation_url(request, "newsletter_unsubscribe_confirm", email, "unsubscribe"),
            )
        except newsletter.NotSubscribed:
            pass
        except Exception:
            traceback.print_exc()
            return Response(
                {"detail": "Sorry, something went wrong. Please try again later."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({"detail": self.SENT_MESSAGE})


class NewsletterUnsubscribeConfirmView(APIView):
    """
    POST /api/newsletter/unsubscribe/confirm/
    Removes the address in a signed token (from the confirmation email) from the newsletter group.

    Expected payload:
    {
        "token": "<token from the email link>"
    }
    """
    authentication_classes = []
    permission_classes = []
    throttle_classes = [NewsletterUnsubscribeConfirmThrottle]

    def post(self, request):
        email, error = _read_token_or_error(request, "unsubscribe")
        if error:
            return error

        try:
            newsletter.unsubscribe(email)
        except newsletter.NotSubscribed:
            return Response({"detail": "You're already unsubscribed."})
        except Exception:
            traceback.print_exc()
            return Response(
                {"detail": "Sorry, something went wrong. Please try again later."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({"detail": "You've been unsubscribed. Sorry to see you go!"})