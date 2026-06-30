from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import render, redirect

from .models import ContactMessage, QuoteRequest


def send_business_email(subject, body, reply_to_email=None, receiver=None):
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[receiver or settings.CONTACT_RECEIVER_EMAIL],
        fail_silently=False,
        reply_to=[reply_to_email] if reply_to_email else None,
    )


def home(request):
    if request.method == "POST":
        form_type = request.POST.get("form_type", "contact")

        if form_type == "contact":
            contact = ContactMessage.objects.create(
                name=request.POST.get("name", "").strip(),
                email=request.POST.get("email", "").strip(),
                phone=request.POST.get("phone", "").strip(),
                company=request.POST.get("company", "").strip(),
                subject=request.POST.get("subject", "").strip(),
                message=request.POST.get("message", "").strip(),
            )

            body = f"""
New KaleidoBrands Contact Message

Name: {contact.name}
Email: {contact.email}
Phone: {contact.phone}
Company: {contact.company}
Subject: {contact.subject}

Message:
{contact.message}
"""

            send_business_email(
                subject="New Website Contact - KaleidoBrands",
                body=body,
                reply_to_email=contact.email,
                receiver="helpdesk@kaleidobrands.com",
            )

            messages.success(request, "Thank you. Your message has been sent.")
            return redirect("brands:home")

        if form_type == "quote":
            quote = QuoteRequest.objects.create(
                name=request.POST.get("name", "").strip(),
                email=request.POST.get("email", "").strip(),
                phone=request.POST.get("phone", "").strip(),
                company=request.POST.get("company", "").strip(),
                product_interest=request.POST.get("product_interest", "").strip(),
                quantity=request.POST.get("quantity") or None,
                budget=request.POST.get("budget", "").strip(),
                deadline=request.POST.get("deadline") or None,
                colors=request.POST.get("colors", "").strip(),
                decoration=request.POST.get("decoration", "").strip(),
                logo=request.FILES.get("logo"),
                artwork=request.FILES.get("artwork"),
                message=request.POST.get("message", "").strip(),
            )

            body = f"""
New KaleidoBrands Quote Request

Name: {quote.name}
Email: {quote.email}
Phone: {quote.phone}
Company: {quote.company}
Product Interest: {quote.product_interest}
Quantity: {quote.quantity}
Budget: {quote.budget}
Deadline: {quote.deadline}
Colors: {quote.colors}
Decoration: {quote.decoration}
Logo Uploaded: {"Yes" if quote.logo else "No"}
Artwork Uploaded: {"Yes" if quote.artwork else "No"}

Project Details:
{quote.message}
"""

            send_business_email(
                subject="New Quote Request - KaleidoBrands",
                body=body,
                reply_to_email=quote.email,
                receiver="sales@kaleidobrands.com",
            )

            messages.success(request, "Thank you. Your quote request has been sent.")
            return redirect("brands:home")

    return render(request, "brands/home.html")