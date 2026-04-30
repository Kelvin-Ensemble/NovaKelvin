from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin  # add this
from django.urls import reverse
from django.utils.html import format_html_join

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
    list_display = ["name", "email", "transaction_ID", "ticket_type", "validity"]
    list_filter = ["for_concert", "ticket_type", "validity"]
    search_fields = ["name", "email", "transaction_ID"]
    search_help_text = "Search for matching name, email or transaction ID."

admin.site.register(CommitteeMember)
admin.site.register(PastConcert)
admin.site.register(Order)
