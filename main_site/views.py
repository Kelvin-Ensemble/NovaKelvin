import urllib.parse

from django.shortcuts import render
from django.urls import reverse
from main_site.models import CommitteeMember,PastConcert,AuditionSection

# Create your views here.

def sso_choose_account(request):
    """
    Interstitial shown before handing off to Google SSO. Google auto-signs people
    in with whatever single Google session is already active in the browser and
    skips its account picker entirely, so if that's the wrong (e.g. personal)
    account, a Google logout is the only documented way to get the normal
    sign-in page back where a different account can be entered.
    """
    next_param = request.GET.get('next', '')
    signin_path = reverse('saml_signin')
    if next_param:
        signin_path += '?' + urllib.parse.urlencode({'next': next_param})
    signin_url = request.build_absolute_uri(signin_path)

    switch_account_url = (
        'https://accounts.google.com/Logout?continue='
        + urllib.parse.quote(signin_url, safe='')
    )

    return render(request, 'sso_choose_account.html', {
        'signin_url': signin_url,
        'switch_account_url': switch_account_url,
    })

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
    sections = AuditionSection.objects.filter(is_published=True).prefetch_related('dates', 'excerpts')
    return render(request, 'website/../join_us.html', {
        'sections': sections
    })

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