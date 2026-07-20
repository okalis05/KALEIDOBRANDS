import logging

logger = logging.getLogger(__name__)


def send_refund_approved_notification(
    refund_request,
    **kwargs,
):
    logger.info(
        "Refund approved notification queued for %s.",
        refund_request.refund_number,
    )


def send_refund_rejected_notification(
    refund_request,
    **kwargs,
):
    logger.info(
        "Refund rejected notification queued for %s.",
        refund_request.refund_number,
    )


def send_refund_completed_notification(
    refund_request,
    refund_transaction=None,
    **kwargs,
):
    logger.info(
        "Refund completed notification queued for %s.",
        refund_request.refund_number,
    )


def send_refund_failed_notification(
    refund_request,
    error_message="",
    **kwargs,
):
    logger.error(
        "Refund failed notification queued for %s: %s",
        refund_request.refund_number,
        error_message,
    )