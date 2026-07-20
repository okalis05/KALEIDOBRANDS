from django.contrib import admin
from .models import Supplier

# Register your models here.
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "supplier_code",
        "api_enabled",
        "active",
        "last_sync",
    )

    search_fields = (
        "name",
        "supplier_code",
    )

    list_filter = (
        "api_enabled",
        "active",
    )