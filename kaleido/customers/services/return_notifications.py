from django.conf import settings
from django.core.mail import EmailMessage


def return_staff_email():
    return getattr(
        settings,
        "RETURN_NOTIFICATION_EMAIL",
        getattr(
            settings,
            "SUPPORT_NOTIFICATION_EMAIL",
            "sales@kaleidobrands.com",
        ),
    )


def send_return_email(
    *,
    subject,
    body,
    recipients,
):
    recipients = [
        recipient
        for recipient in recipients
        if recipient
    ]

    if not recipients:
        return False

    try:
        sent = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        ).send(fail_silently=False)
    except Exception:
        return False

    return bool(sent)


def customer_name(customer):
    return (
        customer.get_full_name()
        or customer.username
        or "Customer"
    )


def notify_return_created(
    return_request,
    *,
    request=None,
):
    customer = return_request.customer

    customer_url = ""

    if request:
        customer_url = request.build_absolute_uri(
            f"/customers/returns/{return_request.id}/"
        )

    customer_body = f"""
Hello {customer_name(customer)},

Your KaleidoBrands request has been received.

Request: {return_request.request_number}
Type: {return_request.get_request_type_display()}
Reason: {return_request.get_reason_display()}
Status: {return_request.get_status_display()}
Order: {return_request.order.order_number}

{customer_url}

Thank you,
KaleidoBrands Customer Care
"""

    staff_body = f"""
A new return or replacement request was submitted.

Request: {return_request.request_number}
Customer: {customer_name(customer)}
Customer Email: {customer.email or "Not provided"}
Order: {return_request.order.order_number}
Type: {return_request.get_request_type_display()}
Reason: {return_request.get_reason_display()}
Priority Review Required: Yes

Customer Notes:
{return_request.customer_notes}
"""

    send_return_email(
        subject=(
            f"Request Received - "
            f"{return_request.request_number}"
        ),
        body=customer_body,
        recipients=[customer.email],
    )

    return send_return_email(
        subject=(
            f"New Return Request - "
            f"{return_request.request_number}"
        ),
        body=staff_body,
        recipients=[return_staff_email()],
    )


def notify_return_status_changed(
    return_request,
    *,
    previous_status,
    request=None,
):
    customer = return_request.customer

    if not customer.email:
        return False

    customer_url = ""

    if request:
        customer_url = request.build_absolute_uri(
            f"/customers/returns/{return_request.id}/"
        )

    body = f"""
Hello {customer_name(customer)},

Your KaleidoBrands request has been updated.

Request: {return_request.request_number}
Previous Status: {previous_status.replace("_", " ").title()}
Current Status: {return_request.get_status_display()}
Resolution: {return_request.get_resolution_display()}

RMA Number: {return_request.rma_number or "Not issued"}

{customer_url}

Thank you,
KaleidoBrands Customer Care
"""

    return send_return_email(
        subject=(
            f"Request Updated - "
            f"{return_request.request_number}"
        ),
        body=body,
        recipients=[customer.email],
    )


def notify_return_message(
    return_request,
    return_message,
    *,
    to_customer,
    request=None,
):
    if to_customer:
        recipient = return_request.customer.email

        if not recipient:
            return False

        url = ""

        if request:
            url = request.build_absolute_uri(
                f"/customers/returns/{return_request.id}/"
            )

        body = f"""
Hello {customer_name(return_request.customer)},

KaleidoBrands Customer Care added a message to your request.

Request: {return_request.request_number}

Message:
{return_message.message}

{url}
"""

        return send_return_email(
            subject=(
                f"Return Request Message - "
                f"{return_request.request_number}"
            ),
            body=body,
            recipients=[recipient],
        )

    recipients = [return_staff_email()]

    if (
        return_request.assigned_to
        and return_request.assigned_to.email
    ):
        recipients.append(
            return_request.assigned_to.email
        )

    body = f"""
A customer added a message to a return request.

Request: {return_request.request_number}
Customer: {customer_name(return_request.customer)}
Order: {return_request.order.order_number}

Message:
{return_message.message}
"""

    return send_return_email(
        subject=(
            f"Customer Return Reply - "
            f"{return_request.request_number}"
        ),
        body=body,
        recipients=list(dict.fromkeys(recipients)),
    )