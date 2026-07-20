import random
import string


def generate_ticket_number():

    while True:

        value = "KB-TKT-" + "".join(
            random.choices(
                string.ascii_uppercase + string.digits,
                k=8,
            )
        )

        from customers.models import SupportTicket

        if not SupportTicket.objects.filter(
            ticket_number=value
        ).exists():
            return value