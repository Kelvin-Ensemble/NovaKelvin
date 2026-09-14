from django.shortcuts import render
from main_site.models import CommitteeMember,PastConcert

# Create your views here.

def home(request):
    """
    Homepage view displaying upcoming concert highlights
    """
    return render(request, 'website/../home.html')

def about(request):
    """
    About view
    """
    return render(request, 'website/../about.html')

def committee(request):
    committee_members = CommitteeMember.objects.all().order_by('order')
    return render(request, 'website/../committee.html', {
        'committee_members': committee_members
    })

def pastconcerts(request):
    past_concerts = PastConcert.objects.all()
    return render(request, 'past_concerts.html', {
        'past_concerts': past_concerts
    })

def joinus(request):
    return render(request, 'website/../join_us.html')

def newsletter(request):
    return render(request, 'newsletter.html')

def newsletter_confirm(request):
    # Button page, like the unsubscribe confirm page, so link scanners can't confirm sign-ups
    return render(request, 'newsletter_confirm.html', {
        'token': request.GET.get('token', '')
    })

def newsletter_unsubscribe(request):
    return render(request, 'newsletter_unsubscribe.html')

def newsletter_unsubscribe_confirm(request):
    # The page only shows a button; the token is POSTed from there so email link
    # scanners that pre-open links can't unsubscribe people by accident
    return render(request, 'newsletter_unsubscribe_confirm.html', {
        'token': request.GET.get('token', '')
    })