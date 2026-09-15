import html
import re

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

class CommitteeMember(models.Model):
    name = models.CharField(max_length=100, unique=False)
    role = models.CharField(max_length=100, unique=False)
    email= models.EmailField(unique=False)
    image = models.ImageField(upload_to='static/img/committee/', blank=True, unique=False)
    order = models.IntegerField(blank=True, null=True)


    def __str__(self):
        return f"{self.role} ({self.name})"
# Create your models here.

class PastConcert(models.Model):
    title = models.CharField(max_length=200)
    date = models.DateField(help_text="Rough date of concert")
    venue = models.CharField(max_length=200, blank=True, null=True)
    conductor = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    programme = models.TextField(blank=True, help_text="List of pieces performed")

    class Meta:
        ordering = ['-date']  # Most recent first
        verbose_name_plural = "Past Concerts"

    def __str__(self):
        return f"{self.title}"


class AuditionSection(models.Model):
    name = models.CharField(max_length=100, help_text='e.g. "Strings" or "Brass, Wind and Percussion (BWP)"')
    description = models.TextField(blank=True, help_text="Shown under the section name, e.g. what to prepare")
    booking_url = models.CharField(
        max_length=1000, blank=True, verbose_name="Google booking page embed link",
        help_text="In Google Calendar, open the appointment schedule, click Share → Website embed, "
                  "and paste the inline embed code (or just its src link) here.",
    )
    form_url = models.URLField(
        max_length=500, blank=True, verbose_name="Audition form link",
        help_text="Link to the audition form (e.g. a Google Form) that applicants fill in before booking",
    )
    order = models.IntegerField(default=0, help_text="Lower numbers appear first")
    is_published = models.BooleanField(default=False, help_text="Only published sections appear on the Join Us page")

    class Meta:
        ordering = ['order', 'name']

    def clean(self):
        url = self.booking_url.strip()
        # Accept the full <iframe ...> snippet Google gives you and keep just its link
        match = re.search(r'src="([^"]+)"', url)
        if match:
            url = html.unescape(match.group(1))
        # Only the calendar.google.com embed link can be shown in the pop-up;
        # calendar.app.google short links refuse to load inside another site
        if url and not url.startswith("https://calendar.google.com/"):
            raise ValidationError({"booking_url": "Use the Website embed link from Google Calendar "
                                                  "(it starts with https://calendar.google.com/)."})
        self.booking_url = url

    def __str__(self):
        return self.name


class AuditionDate(models.Model):
    section = models.ForeignKey(AuditionSection, on_delete=models.CASCADE, related_name='dates')
    date = models.DateField()
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    location = models.CharField(max_length=200)

    class Meta:
        ordering = ['date', 'start_time']

    def __str__(self):
        return f"{self.date} – {self.location}"


class AuditionExcerpt(models.Model):
    section = models.ForeignKey(AuditionSection, on_delete=models.CASCADE, related_name='excerpts')
    title = models.CharField(max_length=200, help_text='e.g. "Violin excerpts"')
    pdf = models.FileField(upload_to='auditions/excerpts/', validators=[FileExtensionValidator(['pdf'])])
    order = models.IntegerField(default=0, help_text="Lower numbers appear first")

    class Meta:
        ordering = ['order', 'title']

    def __str__(self):
        return self.title