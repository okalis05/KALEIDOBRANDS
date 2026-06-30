from django.contrib import admin
from .models import ContactMessage, QuoteRequest


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "company", "subject", "created_at")
    search_fields = ("name", "email", "phone", "company", "subject", "message")
    list_filter = ("created_at",)


@admin.register(QuoteRequest)
class QuoteRequestAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "company", "product_interest", "quantity", "created_at")
    search_fields = ("name", "email", "phone", "company", "product_interest", "message")
    list_filter = ("created_at",)