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