from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
# Create your models here.


class Concert(models.Model):
    concert_name = models.CharField(max_length=100, unique=False)
    concert_date = models.DateField()
    concert_time = models.TimeField()
    concert_location = models.CharField(max_length=100)
    concert_description = models.TextField()
    conductor = models.CharField(max_length=100, unique=False, null=True, blank=True)

    def __str__(self):
        return f"{self.concert_name} - {self.concert_date}, {self.concert_time}"

    @property
    def concert_ticket_types(self):
        """
        Read-only access to all TicketType rows pointing to this Concert.
        """
        return self.ticket_types.all()

class TicketType(models.Model):
    position = models.IntegerField(
        help_text="(Lower value shows first)", default=0
    )
    ticket_label = models.CharField(
        max_length=40,
        help_text="This will be the ticket name shown to the audience "
                  "(i.e. 'Standard Seating' or 'Concession Seating' or 'Restricted View')",
    )
    price = models.DecimalField(default=0, max_digits=10, decimal_places=2)
    price_id = models.CharField(max_length=100, null=True, blank=True, help_text="The price_id generated when creating the price point in stripe.")
    description = models.CharField(max_length=100, null=True, blank=True, help_text="Description of the ticket type.")
    for_concert = models.ForeignKey(
        Concert,
        help_text="Please select the matching concert here. Make sure this is selected "
                  "or the ticket will not show.",
        on_delete=models.CASCADE,
        default=None,
        null=True,
        related_name="ticket_types",   # <-- key line
    )
    qty_total = models.IntegerField(default=0)
    qty_available = models.IntegerField(default=0)
    qty_sold = models.IntegerField(default=0)
    linked_tickets = models.ManyToManyField(
        "self",
        blank=True,
        help_text="Use this to select which tickets should have their ticket quantities synced.",
        symmetrical=True,
    )
    display_ticket = models.BooleanField(
        default=False,
        help_text="When ticked, this will show as a purchasable ticket. "
                  "This should only be false for complimentary tickets.",
    )

    def __str__(self):
        return f"{self.ticket_label}"

    def get_linked_cluster(self):
        """
        Returns a queryset of all TicketTypes in the same 'pool' as this one:
        this ticket type + anything linked to it (symmetric).
        """
        visited_ids = set()
        to_visit = [self]

        while to_visit:
            current = to_visit.pop()
            if current.pk in visited_ids:
                continue
            visited_ids.add(current.pk)
            for neighbor in current.linked_tickets.all():
                if neighbor.pk not in visited_ids:
                    to_visit.append(neighbor)

        return TicketType.objects.filter(pk__in=visited_ids)

    @classmethod
    def recalculate_quantities_for_cluster(cls, root_ticket_type):
        """
        Recalculate qty_sold and qty_available for the entire 'cluster'
        of linked TicketTypes around root_ticket_type.
        """
        # if Ticket is in the same models.py, no import needed; otherwise:
        # from .models import Ticket

        cluster = root_ticket_type.get_linked_cluster()

        sold_count = Ticket.objects.filter(
            ticket_type__in=cluster,
            validity=True,
        ).count()

        for tt in cluster:
            tt.qty_sold = sold_count
            remaining = tt.qty_total - sold_count
            tt.qty_available = remaining if remaining > 0 else 0
            tt.save(update_fields=["qty_sold", "qty_available"])

    def save(self, *args, **kwargs):
        # Detect if qty_total changed (or this is new)
        old_total = None
        if self.pk is not None:
            try:
                old_total = TicketType.objects.only("qty_total").get(pk=self.pk).qty_total
            except TicketType.DoesNotExist:
                pass

        # Save this TicketType first
        super().save(*args, **kwargs)

        # If new or qty_total changed, propagate to cluster and recalc
        if old_total is None or old_total != self.qty_total:
            cluster = self.get_linked_cluster()

            # Propagate the same total to all in the cluster (including self).
            # Use update() to avoid calling save() again and causing recursion.
            cluster.update(qty_total=self.qty_total)

            # Now recalc sold/available for the cluster
            TicketType.recalculate_quantities_for_cluster(self)


class Ticket(models.Model):
    name = models.CharField(max_length=60, help_text="Customer's Name", default="")
    email = models.CharField(max_length=100, help_text="Customer's Email", default="")
    transaction_ID = models.CharField(
        max_length=100, help_text="Autogenerated transaction ID from STRIPE", default=""
    )
    for_concert = models.ForeignKey(
        Concert, on_delete=models.CASCADE, null=True, default=None
    )
    ticket_type = models.ForeignKey(
        TicketType, on_delete=models.CASCADE, null=True, default=None
    )
    ticket_ID = models.CharField(blank=True, null=True, max_length=100)
    checked_in_at = models.DateTimeField(null=True, blank=True, default=None)
    validity = models.BooleanField(
        help_text="If ticked, this ticket is valid.", default=True
    )
    change_log = models.TextField(
        help_text="Will log any changes by automatic systems. I recommend adding any changes here if editing manually.",
        blank=True,
        default="",
    )


    def __str__(self):
        return self.name

@receiver(post_save, sender=Ticket)
def update_tickettype_quantities_on_save(sender, instance, **kwargs):
    """
    Whenever a Ticket is created or updated, recalc the quantities
    for its TicketType cluster.
    """
    if instance.ticket_type_id:
        TicketType.recalculate_quantities_for_cluster(instance.ticket_type)


@receiver(post_delete, sender=Ticket)
def update_tickettype_quantities_on_delete(sender, instance, **kwargs):
    """
    Whenever a Ticket is deleted, recalc the quantities
    for its TicketType cluster.
    """
    if instance.ticket_type_id:
        TicketType.recalculate_quantities_for_cluster(instance.ticket_type)


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    stripe_session_id = models.CharField(max_length=255, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    customer_email = models.EmailField()
    customer_name = models.CharField(max_length=255, blank=True)

    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='GBP')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    tickets = models.ManyToManyField(Ticket, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order {self.id} - {self.stripe_session_id[:20]} - {self.status}"


# class OrderItem(models.Model):
#     order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
#     ticket_type = models.ForeignKey(TicketType, on_delete=models.CASCADE)
#     quantity = models.PositiveIntegerField()
#     price_per_ticket = models.DecimalField(max_digits=10, decimal_places=2)
#
#     created_at = models.DateTimeField(auto_now_add=True)
#
#     class Meta:
#         ordering = ['id']
#
#     def __str__(self):
#         return f"{self.quantity}x {self.ticket_type.ticket_label}"
#
#     @property
#     def subtotal(self):
#         return self.quantity * self.price_per_ticket