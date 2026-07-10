from django.conf import settings
from django.db import models


class CustomerLead(models.Model):

    STATUS_CHOICES = [
        ("new", "New Lead"),
        ("contacted", "Contacted"),
        ("qualified", "Qualified"),
        ("proposal", "Proposal Sent"),
        ("negotiation", "Negotiation"),
        ("won", "Won"),
        ("lost", "Lost"),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="crm_leads",
    )

    company = models.CharField(max_length=200)

    contact_name = models.CharField(max_length=200)

    email = models.EmailField()

    phone = models.CharField(max_length=40, blank=True)

    estimated_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="new",
    )

    source = models.CharField(
        max_length=120,
        blank=True,
    )

    notes = models.TextField(blank=True)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="assigned_leads",
        on_delete=models.SET_NULL,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company
    
class CRMActivity(models.Model):

    lead = models.ForeignKey(
        CustomerLead,
        on_delete=models.CASCADE,
        related_name="activities",
    )

    title = models.CharField(max_length=200)

    description = models.TextField(blank=True)

    activity_date = models.DateTimeField()

    completed = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title