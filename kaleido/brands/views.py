from django.contrib import messages
from django.shortcuts import render, redirect
from .models import ContactMessage

# Create your views here.
def home(request):
    if request.method == 'POST':
        ContactMessage.objects.create(
            name=request.POST.get('name', '').strip(),
            email=request.POST.get('email', '').strip(),
            phone=request.POST.get('phone', '').strip(),
            company=request.POST.get('company', '').strip(),
            message=request.POST.get('message', '').strip(),
        )
        messages.success(request, 'Thank you. Your message has been received.')
        return redirect('brands:home')

    return render(request, 'brands/home.html')