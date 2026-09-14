from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin  # add this
from django.urls import reverse
from django.utils.html import format_html_join

import json

from django.contrib import admin
from django.urls import path
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from ticketing.models import Ticket, Concert


from main_site.models import CommitteeMember, PastConcert
from ticketing.models import Concert, TicketType, Ticket, Order

# from import_export.admin import ExportMixin
# from import_export.admin import ImportExportModelAdmin
# from import_export import fields, resources
# from import_export.widgets import ForeignKeyWidget


class TicketTypeAdminForm(forms.ModelForm):
    class Meta:
        model = TicketType
        fields = "__all__"

    def clean_linked_tickets(self):
        linked = self.cleaned_data.get("linked_tickets")
        if self.instance.pk and linked.filter(pk=self.instance.pk).exists():
            # Prevent self-linking
            raise forms.ValidationError("A ticket type cannot be linked to itself.")
        return linked

@admin.register(Concert)
class ConcertAdmin(ModelAdmin):
    list_display = ("concert_name", "concert_date", "concert_time", "concert_location")
    readonly_fields = ("concert_ticket_types_display",)

    fields = (
        "concert_name",
        "concert_date",
        "concert_time",
        "concert_location",
        "concert_description",
        "concert_ticket_types_display",
    )

    def concert_ticket_types_display(self, obj):
        tickets = obj.concert_ticket_types.order_by("position")
        if not tickets.exists():
            return "No ticket types"

        return format_html_join(
            ", ",
            '<a href="{}">{}</a>',
            (
                (
                    reverse("admin:ticketing_tickettype_change", args=[t.pk]),
                    t.ticket_label,
                )
                for t in tickets
            ),
        )

    concert_ticket_types_display.short_description = "Ticket types (read-only)"


@admin.register(TicketType)
class TicketTypeAdmin(ModelAdmin):
    form = TicketTypeAdminForm  # <-- use the custom form

    readonly_fields = ["qty_available", "qty_sold"]

    list_display = (
        "ticket_label",
        "for_concert",
        "qty_total",
        "qty_available",
        "qty_sold",
        "display_ticket",
    )
    list_filter = ("for_concert", "display_ticket")
    search_fields = ("ticket_label",)
    filter_horizontal = ("linked_tickets",)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        field = super().formfield_for_manytomany(db_field, request, **kwargs)
        if db_field.name == "linked_tickets" and request.resolver_match:
            object_id = request.resolver_match.kwargs.get("object_id")
            if object_id:
                field.queryset = field.queryset.exclude(pk=object_id)
        return field


@admin.register(Ticket)
# class ticketAdmin(ExportMixin, ModelAdmin):
class ticketAdmin(ModelAdmin):
    # resource_class = ticketResource
    list_display = ("ticket_ID", "name", "ticket_type", "for_concert",
                    "validity", "checked_in_at")
    list_filter = ("for_concert", "validity", "ticket_type")
    search_fields = ("ticket_ID", "name", "email")
    # a handy link to the scanner from the changelist (see change_list template note)
    change_list_template = "admin/ticketing/ticket_change_list.html"

    # ---- custom admin URLs ----
    def get_urls(self):
        custom = [
            path("scan/", self.admin_site.admin_view(self.scan_view),
                 name="ticketing_ticket_scan"),
            path("scan/check/", self.admin_site.admin_view(self.scan_check),
                 name="ticketing_ticket_scan_check"),
        ]
        return custom + super().get_urls()

    # ---- the scanner page ----
    def scan_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            "title": "Scan tickets at the door",
            "concerts": Concert.objects.order_by("-concert_date", "-concert_time"),
        }
        return render(request, "admin/ticketing/scan.html", context)

    # ---- the JSON validate + check-in endpoint ----
    def scan_check(self, request):
        if request.method != "POST":
            return JsonResponse({"status": "error", "message": "POST required"}, status=405)
        if not request.user.has_perm("ticketing.change_ticket"):
            return JsonResponse({"status": "error", "message": "Not permitted"}, status=403)

        try:
            data = json.loads(request.body or "{}")
        except ValueError:
            data = {}
        code = (data.get("code") or "").strip()
        concert_id = data.get("concert_id") or None

        if not code:
            return JsonResponse({"status": "invalid", "message": "Empty scan"})

        try:
            ticket = Ticket.objects.select_related("for_concert", "ticket_type").get(ticket_ID=code)
        except Ticket.DoesNotExist:
            return JsonResponse({"status": "invalid", "message": "No matching ticket"})

        info = {
            "name": ticket.name,
            "type": ticket.ticket_type.ticket_label if ticket.ticket_type else "",
            "concert": ticket.for_concert.concert_name if ticket.for_concert else "",
            "ticket_id": ticket.ticket_ID,
        }

        if not ticket.validity:
            return JsonResponse({"status": "void", "message": "Ticket is void", **info})

        if concert_id and str(ticket.for_concert_id) != str(concert_id):
            return JsonResponse({"status": "wrong_event",
                                 "message": "Ticket is for a different concert", **info})

        # Atomic first-scan check-in: the UPDATE only touches rows still un-checked-in,
        # so concurrent scans of the same ticket can't both succeed.
        now = timezone.now()
        claimed = Ticket.objects.filter(pk=ticket.pk, checked_in_at__isnull=True).update(checked_in_at=now)
        if not claimed:
            ticket.refresh_from_db(fields=["checked_in_at"])
            local = timezone.localtime(ticket.checked_in_at)
            return JsonResponse({"status": "already_used",
                                 "message": "Already admitted",
                                 "checked_in_at": local.strftime("%H:%M:%S"), **info})

        # audit trail in the existing change_log field (update() to skip the qty signals)
        who = request.user.get_username()
        Ticket.objects.filter(pk=ticket.pk).update(
            change_log=(ticket.change_log or "") +
                       f"[{timezone.localtime(now):%Y-%m-%d %H:%M:%S}] Admitted at door by {who}.\n"
        )
        return JsonResponse({"status": "ok", "message": "Admit one", **info})

admin.site.register(CommitteeMember)
admin.site.register(PastConcert)
admin.site.register(Order)
