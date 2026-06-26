from django.contrib import admin
from .models import ContactMessage


# Register your models here.
@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'company', 'created_at')
    search_fields = ('name', 'email', 'phone', 'company', 'message')
    list_filter = ('created_at',)