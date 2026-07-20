from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from .models import Supplier


# Create your views here.
@staff_member_required
def dashboard(request):

    suppliers = Supplier.objects.all()

    return render(
        request,
        "supplier/dashboard.html",
        {
            "suppliers": suppliers,
        },
    )