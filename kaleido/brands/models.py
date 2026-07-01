from django.db import models

# Create your models here!
class ContactMessage(models.Model):
    name = models.CharField(max_length=120)
    company = models.CharField(max_length=120, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    subject = models.CharField(max_length=180, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.email}"


class QuoteRequest(models.Model):
    name = models.CharField(max_length=120)
    company = models.CharField(max_length=120, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    product_interest = models.CharField(max_length=180)
    quantity = models.PositiveIntegerField(null=True, blank=True)
    budget = models.CharField(max_length=100, blank=True)
    deadline = models.DateField(null=True, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    logo = models.FileField(upload_to="quotes/logos/", blank=True, null=True)
    artwork = models.FileField(upload_to="quotes/artwork/", blank=True, null=True)
    colors = models.CharField(max_length=100, blank=True)
    decoration = models.CharField(max_length=50, blank=True)
    STATUS_CHOICES = [("new", "New"),("reviewing", "Reviewing"),("quoted", "Quoted"),("ordered", "Ordered"),("shipped", "Shipped")]
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="new")
    LEAD_SOURCE_CHOICES = [("website", "Website"),("google", "Google"),("facebook", "Facebook"), ("linkedin", "LinkedIn"), ("referral", "Referral"), ("repeat", "Returning Customer"), ("other", "Other")]
    estimated_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    lead_source = models.CharField(max_length=40, choices=LEAD_SOURCE_CHOICES, default="website")

    is_returning_customer = models.BooleanField(default=False)

    in_production = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} - {self.product_interest}"