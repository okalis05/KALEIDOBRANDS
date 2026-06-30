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

    def __str__(self):
        return f"{self.name} - {self.product_interest}"