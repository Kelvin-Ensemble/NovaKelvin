from django.shortcuts import render
from django.conf import settings

def ticketing_page(request):
    return render(request, "ticket_purchase.html", {
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    })

def ticketing_success(request):
    return render(request, "ticket_purchase_complete.html")
