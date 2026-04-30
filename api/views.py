from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.conf import settings
from decimal import Decimal
import stripe

from ticketing import models as ts_models
from ticketing.webhook_handler import handle_webhook
from .serializers import ConcertSerializer, TicketTypeSummarySerializer

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

            # Build Stripe line items and calculate total
            stripe_line_items = []
            total_amount = Decimal('0.00')
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

                total_amount += Decimal(str(ticket_type.price)) * quantity # THIS LINE

            if not stripe_line_items:
                return Response(
                    {"detail": "No valid line items provided."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create Stripe checkout session
            checkout_session = stripe.checkout.Session.create(
                ui_mode='embedded',
                line_items=stripe_line_items,
                mode='payment',
                redirect_on_completion='never',
                automatic_tax={'enabled': True},
                metadata={
                },
            )

            # Create pending order in database
            order = ts_models.Order.objects.create(
                stripe_session_id=checkout_session.id,
                status='pending',
                customer_email='',  # Will be filled by webhook
                total_amount=total_amount,
                currency='GBP',
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