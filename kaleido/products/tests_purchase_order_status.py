from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from products.models import (
    Supplier,
    SupplierPurchaseOrder,
)
from products.services.purchase_order_status import (
    update_purchase_order_status,
    validate_purchase_order_transition,
)


User = get_user_model()


class PurchaseOrderStatusValidationTests(TestCase):
    def test_same_status_is_valid(self):
        validate_purchase_order_transition(
            "draft",
            "draft",
        )

    def test_draft_can_transition_to_ready(self):
        validate_purchase_order_transition(
            "draft",
            "ready",
        )

    def test_draft_can_transition_directly_to_sent(self):
        validate_purchase_order_transition(
            "draft",
            "sent",
        )

    def test_sent_can_transition_directly_to_production(self):
        validate_purchase_order_transition(
            "sent",
            "in_production",
        )

    def test_received_is_terminal(self):
        with self.assertRaises(ValidationError):
            validate_purchase_order_transition(
                "received",
                "shipped",
            )

    def test_cancelled_is_terminal(self):
        with self.assertRaises(ValidationError):
            validate_purchase_order_transition(
                "cancelled",
                "ready",
            )

    def test_invalid_backward_transition_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_purchase_order_transition(
                "shipped",
                "in_production",
            )

    def test_unknown_status_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_purchase_order_transition(
                "draft",
                "unknown",
            )


class PurchaseOrderStatusUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="po-status-test",
            email="po-status@example.com",
            password="test-password",
        )

        self.supplier = Supplier.objects.create(
            name="PO Status Supplier",
            slug="po-status-supplier",
            email="supplier@example.com",
        )

        self.purchase_order = (
            SupplierPurchaseOrder.objects.create(
                supplier=self.supplier,
                po_number="KB-PO-STATUS-001",
                status="draft",
                created_by=self.user,
            )
        )

    @patch(
        "products.services.purchase_order_status."
        "log_purchase_order_activity"
    )
    def test_status_is_updated(
        self,
        mock_log_activity,
    ):
        result = update_purchase_order_status(
            self.purchase_order,
            "ready",
            user=self.user,
        )

        result.refresh_from_db()

        self.assertEqual(result.status, "ready")
        mock_log_activity.assert_called_once()

    @patch(
        "products.services.purchase_order_status."
        "log_purchase_order_activity"
    )
    def test_same_status_is_idempotent(
        self,
        mock_log_activity,
    ):
        result = update_purchase_order_status(
            self.purchase_order,
            "draft",
            user=self.user,
        )

        result.refresh_from_db()

        self.assertEqual(result.status, "draft")
        mock_log_activity.assert_not_called()

    @patch(
        "products.services.purchase_order_status."
        "log_purchase_order_activity"
    )
    def test_sent_sets_sent_at(
        self,
        mock_log_activity,
    ):
        result = update_purchase_order_status(
            self.purchase_order,
            "sent",
            user=self.user,
        )

        result.refresh_from_db()

        self.assertEqual(result.status, "sent")
        self.assertIsNotNone(result.sent_at)

    @patch(
        "products.services.purchase_order_status."
        "log_purchase_order_activity"
    )
    def test_confirmed_sets_confirmed_at(
        self,
        mock_log_activity,
    ):
        self.purchase_order.status = "sent"
        self.purchase_order.save(
            update_fields=["status", "updated_at"]
        )

        result = update_purchase_order_status(
            self.purchase_order,
            "confirmed",
            user=self.user,
        )

        result.refresh_from_db()

        self.assertEqual(result.status, "confirmed")
        self.assertIsNotNone(result.confirmed_at)

    @patch(
        "products.services.purchase_order_status."
        "log_purchase_order_activity"
    )
    def test_in_production_sets_production_timestamp(
        self,
        mock_log_activity,
    ):
        self.purchase_order.status = "confirmed"
        self.purchase_order.save(
            update_fields=["status", "updated_at"]
        )

        result = update_purchase_order_status(
            self.purchase_order,
            "in_production",
            user=self.user,
        )

        result.refresh_from_db()

        self.assertEqual(
            result.status,
            "in_production",
        )

        self.assertIsNotNone(
            result.production_started_at
        )

    @patch(
        "products.services.purchase_order_status."
        "log_purchase_order_activity"
    )
    def test_shipped_sets_shipped_at(
        self,
        mock_log_activity,
    ):
        self.purchase_order.status = "in_production"
        self.purchase_order.save(
            update_fields=["status", "updated_at"]
        )

        result = update_purchase_order_status(
            self.purchase_order,
            "shipped",
            user=self.user,
        )

        result.refresh_from_db()

        self.assertEqual(result.status, "shipped")
        self.assertIsNotNone(result.shipped_at)

    @patch(
        "products.services.purchase_order_status."
        "log_purchase_order_activity"
    )
    def test_received_sets_received_at(
        self,
        mock_log_activity,
    ):
        self.purchase_order.status = "shipped"
        self.purchase_order.save(
            update_fields=["status", "updated_at"]
        )

        result = update_purchase_order_status(
            self.purchase_order,
            "received",
            user=self.user,
        )

        result.refresh_from_db()

        self.assertEqual(result.status, "received")
        self.assertIsNotNone(result.received_at)

    @patch(
        "products.services.purchase_order_status."
        "log_purchase_order_activity"
    )
    def test_activity_contains_transition_values(
        self,
        mock_log_activity,
    ):
        update_purchase_order_status(
            self.purchase_order,
            "ready",
            user=self.user,
        )

        mock_log_activity.assert_called_once_with(
            self.purchase_order,
            action="status_changed",
            message="Purchase order status updated.",
            previous_value="draft",
            new_value="ready",
            user=self.user,
        )

    def test_invalid_transition_does_not_change_status(self):
        self.purchase_order.status = "received"
        self.purchase_order.save(
            update_fields=["status", "updated_at"]
        )

        with self.assertRaises(ValidationError):
            update_purchase_order_status(
                self.purchase_order,
                "shipped",
                user=self.user,
            )

        self.purchase_order.refresh_from_db()

        self.assertEqual(
            self.purchase_order.status,
            "received",
        )

    @patch(
        "products.services.purchase_order_status."
        "synchronize_customer_order_from_purchase_orders"
    )
    def test_no_customer_order_skips_synchronization(
        self,
        mock_synchronize,
    ):
        update_purchase_order_status(
            self.purchase_order,
            "ready",
            user=self.user,
        )

        mock_synchronize.assert_not_called()