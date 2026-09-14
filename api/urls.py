from django.urls import path
from .views import (
    ConcertsView,
    ConcertTicketTypesView,
    CreateCheckoutSessionView,
    StripeWebhookView,
    OrderStatusView,
    NewsletterSignupView,
    NewsletterSubscribeConfirmView,
    NewsletterUnsubscribeRequestView,
    NewsletterUnsubscribeConfirmView,
)

urlpatterns = [
    path('tickets/concerts/', ConcertsView.as_view(), name='concerts'),
    path('tickets/concert/tickettypes', ConcertTicketTypesView.as_view(), name='concert-ticket-types'),
    path('tickets/create-checkout-session/', CreateCheckoutSessionView.as_view(), name='create-checkout-session'),
    path('tickets/stripe-webhook/', StripeWebhookView.as_view(), name='stripe-webhook'),
    path('tickets/order-status/', OrderStatusView.as_view(), name='order-status'),
    path('newsletter/subscribe/', NewsletterSignupView.as_view(), name='newsletter-subscribe'),
    path('newsletter/subscribe/confirm/', NewsletterSubscribeConfirmView.as_view(), name='newsletter-subscribe-confirm'),
    path('newsletter/unsubscribe/', NewsletterUnsubscribeRequestView.as_view(), name='newsletter-unsubscribe'),
    path('newsletter/unsubscribe/confirm/', NewsletterUnsubscribeConfirmView.as_view(), name='newsletter-unsubscribe-confirm'),
]