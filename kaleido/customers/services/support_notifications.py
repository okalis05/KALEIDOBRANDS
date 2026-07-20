from django.conf import settings
import logging

from django.conf import settings
from django.core.mail import EmailMessage


def support_staff_email():
    return getattr(
        settings,
        "SUPPORT_NOTIFICATION_EMAIL",
        getattr(
            settings,
            "CONTACT_RECEIVER_EMAIL",
            "sales@kaleidobrands.com",
        ),
    )


def customer_display_name(customer):
    return (
        customer.get_full_name()
        or customer.username
        or "Customer"
    )


def ticket_url(request, ticket, *, staff=False):
    if not request:
        return ""

    if staff:
        path = (
            f"/customers/staff/support/"
            f"{ticket.id}/"
        )
    else:
        path = (
            f"/customers/support/"
            f"{ticket.id}/"
        )

    return request.build_absolute_uri(path)


def send_email(
    *,
    subject,
    body,
    recipients,
    fail_silently=True,
):
    recipients = [
        email
        for email in recipients
        if email
    ]

    if not recipients:
        return False

    try:
        sent = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        ).send(
            fail_silently=fail_silently
        )
    except Exception:
        return False

    return bool(sent)


def notify_customer_ticket_created(
    ticket,
    *,
    request=None,
):
    customer = ticket.customer

    if not customer.email:
        return False

    body = f"""
Hello {customer_display_name(customer)},

Your KaleidoBrands support request has been received.

Ticket: {ticket.ticket_number}
Subject: {ticket.subject}
Category: {ticket.get_category_display()}
Priority: {ticket.get_priority_display()}
Status: {ticket.get_status_display()}

Our support team will review your request.

{ticket_url(request, ticket)}

Thank you,
KaleidoBrands Support
"""

    return send_email(
        subject=(
            f"Support Ticket Received - "
            f"{ticket.ticket_number}"
        ),
        body=body,
        recipients=[customer.email],
    )


def notify_staff_ticket_created(
    ticket,
    *,
    request=None,
):
    customer = ticket.customer

    body = f"""
A new KaleidoBrands support ticket was created.

Ticket: {ticket.ticket_number}
Customer: {customer_display_name(customer)}
Customer Email: {customer.email or "Not provided"}
Subject: {ticket.subject}
Category: {ticket.get_category_display()}
Priority: {ticket.get_priority_display()}
Status: {ticket.get_status_display()}

Description:
{ticket.description}

{ticket_url(request, ticket, staff=True)}
"""

    return send_email(
        subject=(
            f"New Support Ticket - "
            f"{ticket.ticket_number}"
        ),
        body=body,
        recipients=[support_staff_email()],
    )


def notify_staff_customer_replied(
    ticket,
    ticket_message,
    *,
    request=None,
):
    body = f"""
A customer replied to a support ticket.

Ticket: {ticket.ticket_number}
Customer: {customer_display_name(ticket.customer)}
Subject: {ticket.subject}
Status: {ticket.get_status_display()}

Reply:
{ticket_message.message}

{ticket_url(request, ticket, staff=True)}
"""

    recipients = [support_staff_email()]

    if (
        ticket.assigned_to
        and ticket.assigned_to.email
        and ticket.assigned_to.email not in recipients
    ):
        recipients.append(
            ticket.assigned_to.email
        )

    return send_email(
        subject=(
            f"Customer Reply - "
            f"{ticket.ticket_number}"
        ),
        body=body,
        recipients=recipients,
    )


def notify_customer_staff_replied(
    ticket,
    ticket_message,
    *,
    request=None,
):
    customer = ticket.customer

    if not customer.email:
        return False

    body = f"""
Hello {customer_display_name(customer)},

KaleidoBrands Support replied to your ticket.

Ticket: {ticket.ticket_number}
Subject: {ticket.subject}
Status: {ticket.get_status_display()}

Reply:
{ticket_message.message}

{ticket_url(request, ticket)}

Thank you,
KaleidoBrands Support
"""

    return send_email(
        subject=(
            f"Support Reply - "
            f"{ticket.ticket_number}"
        ),
        body=body,
        recipients=[customer.email],
    )


def notify_customer_ticket_status(
    ticket,
    *,
    previous_status,
    request=None,
):
    customer = ticket.customer

    if not customer.email:
        return False

    body = f"""
Hello {customer_display_name(customer)},

The status of your KaleidoBrands support ticket changed.

Ticket: {ticket.ticket_number}
Subject: {ticket.subject}
Previous Status: {previous_status.replace("_", " ").title()}
Current Status: {ticket.get_status_display()}

{ticket_url(request, ticket)}

Thank you,
KaleidoBrands Support
"""

    return send_email(
        subject=(
            f"Support Ticket Updated - "
            f"{ticket.ticket_number}"
        ),
        body=body,
        recipients=[customer.email],
    )