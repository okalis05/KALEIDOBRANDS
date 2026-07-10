from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone

from customers.models import CRMActivity


class Command(BaseCommand):
    help = "Send CRM follow-up reminder emails for upcoming activities."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Look ahead this many hours for upcoming CRM activities.",
        )

        parser.add_argument(
            "--to",
            type=str,
            default="sales@kaleidobrands.com",
            help="Email recipient for CRM reminders.",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        recipient = options["to"]

        now = timezone.now()
        end = now + timezone.timedelta(hours=hours)

        activities = CRMActivity.objects.filter(
            completed=False,
            activity_date__gte=now,
            activity_date__lte=end,
        ).select_related("lead").order_by("activity_date")

        if not activities.exists():
            self.stdout.write(
                self.style.SUCCESS("No upcoming CRM follow-ups found.")
            )
            return

        lines = []

        for activity in activities:
            lines.append(
                f"""
Follow-Up: {activity.title}
Company: {activity.lead.company}
Contact: {activity.lead.contact_name}
Email: {activity.lead.email}
Phone: {activity.lead.phone}
Date: {activity.activity_date}
Lead Status: {activity.lead.get_status_display()}
Notes: {activity.description or "N/A"}
"""
            )

        body = f"""
KaleidoBrands CRM Follow-Up Reminder

Upcoming activities in the next {hours} hours:

{''.join(lines)}
"""

        email = EmailMessage(
            subject=f"KaleidoBrands CRM Follow-Ups - Next {hours} Hours",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )

        email.send(fail_silently=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"CRM follow-up reminder sent to {recipient}. Activities: {activities.count()}"
            )
        )