from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from customers.models import Order
from products.models import (
    Supplier,
    SupplierPurchaseOrder,
)
from products.services.supplier_tracking import (
    update_supplier_tracking,
)


User = get_user_model()


class SupplierTrackingSynchronizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="supplier-tracking-test",
            email="tracking-customer@example.com",
            password="test-password",
        )

        self.supplier_one = Supplier.objects.create(
            name="Tracking Supplier One",
            slug="tracking-supplier-one",
            email="supplier-one@example.com",
        )

        self.supplier_two = Supplier.objects.create(
            name="Tracking Supplier Two",
            slug="tracking-supplier-two",
            email="supplier-two@example.com",
        )

        self.order = Order.objects.create(
            customer=self.user,
            order_number="KB-TRACKING-001",
            payment_status="paid",
            status="production",
        )

        self.po_one = SupplierPurchaseOrder.objects.create(
            supplier=self.supplier_one,
            customer_order=self.order,
            po_number="KB-PO-TRACKING-001",
            status="in_production",
        )

        self.po_two = SupplierPurchaseOrder.objects.create(
            supplier=self.supplier_two,
            customer_order=self.order,
            po_number="KB-PO-TRACKING-002",
            status="in_production",
        )

    @patch(
        "products.services.supplier_tracking."
        "log_purchase_order_activity"
    )
    def test_tracking_information_is_saved(
        self,
        mock_log_activity,
    ):
        result = update_supplier_tracking(
            self.po_one,
            tracking_number="TRACK-1001",
            tracking_url=(
                "https://tracking.example.com/TRACK-1001"
            ),
            user=self.user,
        )

        result.refresh_from_db()

        self.assertEqual(
            result.tracking_number,
            "TRACK-1001",
        )

        self.assertEqual(
            result.tracking_url,
            "https://tracking.example.com/TRACK-1001",
        )

        mock_log_activity.assert_called_once()

    @patch(
        "products.services.supplier_tracking."
        "log_purchase_order_activity"
    )
    def test_tracking_update_creates_activity(
        self,
        mock_log_activity,
    ):
        update_supplier_tracking(
            self.po_one,
            tracking_number="TRACK-1002",
            user=self.user,
        )

        mock_log_activity.assert_called_once_with(
            self.po_one,
            action="tracking_updated",
            message=(
                "Supplier shipment tracking information "
                "was updated."
            ),
            previous_value="",
            new_value="TRACK-1002",
            user=self.user,
        )

    @patch(
        "products.services.supplier_tracking."
        "log_purchase_order_activity"
    )
    def test_duplicate_tracking_update_is_idempotent(
        self,
        mock_log_activity,
    ):
        self.po_one.tracking_number = "TRACK-1003"
        self.po_one.tracking_url = (
            "https://tracking.example.com/TRACK-1003"
        )
        self.po_one.save(
            update_fields=[
                "tracking_number",
                "tracking_url",
            ]
        )

        result = update_supplier_tracking(
            self.po_one,
            tracking_number="TRACK-1003",
            tracking_url=(
                "https://tracking.example.com/TRACK-1003"
            ),
            user=self.user,
        )

        result.refresh_from_db()

        self.assertEqual(
            result.tracking_number,
            "TRACK-1003",
        )

        mock_log_activity.assert_not_called()

    def test_estimated_ship_date_is_saved(self):
        result = update_supplier_tracking(
            self.po_one,
            estimated_ship_date=date(2026, 8, 20),
        )

        result.refresh_from_db()

        self.assertEqual(
            result.estimated_ship_date,
            date(2026, 8, 20),
        )

    def test_supplier_reference_is_saved(self):
        result = update_supplier_tracking(
            self.po_one,
            supplier_reference="SUPPLIER-SHIP-9001",
        )

        result.refresh_from_db()

        self.assertEqual(
            result.supplier_reference,
            "SUPPLIER-SHIP-9001",
        )

    @patch(
        "products.services.supplier_tracking."
        "update_purchase_order_status"
    )
    def test_shipped_event_uses_status_service(
        self,
        mock_update_status,
    ):
        mock_update_status.return_value = self.po_one

        update_supplier_tracking(
            self.po_one,
            tracking_number="TRACK-SHIPPED",
            shipment_status="shipped",
            user=self.user,
        )

        mock_update_status.assert_called_once_with(
            self.po_one,
            "shipped",
            user=self.user,
        )

    def test_shipped_event_sets_status_and_timestamp(self):
        result = update_supplier_tracking(
            self.po_one,
            tracking_number="TRACK-2001",
            shipment_status="shipped",
            user=self.user,
        )

        result.refresh_from_db()

        self.assertEqual(result.status, "shipped")
        self.assertIsNotNone(result.shipped_at)

    def test_received_event_sets_status_and_timestamp(self):
        self.po_one.status = "shipped"
        self.po_one.save(
            update_fields=["status"]
        )

        result = update_supplier_tracking(
            self.po_one,
            shipment_status="received",
            user=self.user,
        )

        result.refresh_from_db()

        self.assertEqual(result.status, "received")
        self.assertIsNotNone(result.received_at)

    def test_one_shipped_po_does_not_ship_customer_order(self):
        update_supplier_tracking(
            self.po_one,
            tracking_number="TRACK-PARTIAL",
            shipment_status="shipped",
            user=self.user,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            "production",
        )

    def test_all_shipped_purchase_orders_ship_customer_order(
        self,
    ):
        update_supplier_tracking(
            self.po_one,
            tracking_number="TRACK-ONE",
            shipment_status="shipped",
            user=self.user,
        )

        update_supplier_tracking(
            self.po_two,
            tracking_number="TRACK-TWO",
            shipment_status="shipped",
            user=self.user,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            "shipped",
        )

    def test_all_received_purchase_orders_deliver_order(self):
        self.po_one.status = "shipped"
        self.po_one.save(update_fields=["status"])

        self.po_two.status = "shipped"
        self.po_two.save(update_fields=["status"])

        update_supplier_tracking(
            self.po_one,
            shipment_status="received",
            user=self.user,
        )

        update_supplier_tracking(
            self.po_two,
            shipment_status="received",
            user=self.user,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            "delivered",
        )

    def test_tracking_is_copied_to_customer_order(self):
        self.po_two.status = "shipped"
        self.po_two.save(update_fields=["status"])

        update_supplier_tracking(
            self.po_one,
            tracking_number="TRACK-CUSTOMER-100",
            tracking_url=(
                "https://tracking.example.com/"
                "TRACK-CUSTOMER-100"
            ),
            shipment_status="shipped",
            user=self.user,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.tracking_number,
            "TRACK-CUSTOMER-100",
        )

        self.assertEqual(
            self.order.tracking_url,
            (
                "https://tracking.example.com/"
                "TRACK-CUSTOMER-100"
            ),
        )

    @patch(
        "products.services.supplier_tracking."
        "update_purchase_order_status"
    )
    def test_duplicate_status_event_is_not_transitioned_again(
        self,
        mock_update_status,
    ):
        self.po_one.status = "shipped"
        self.po_one.save(update_fields=["status"])

        update_supplier_tracking(
            self.po_one,
            shipment_status="shipped",
            user=self.user,
        )

        mock_update_status.assert_not_called()

    def test_invalid_supplier_status_is_rejected(self):
        with self.assertRaises(ValidationError):
            update_supplier_tracking(
                self.po_one,
                shipment_status="in_production",
                user=self.user,
            )

        self.po_one.refresh_from_db()

        self.assertEqual(
            self.po_one.status,
            "in_production",
        )

    def test_received_event_cannot_skip_shipped_status(self):
        with self.assertRaises(ValidationError):
            update_supplier_tracking(
                self.po_one,
                shipment_status="received",
                user=self.user,
            )

        self.po_one.refresh_from_db()

        self.assertEqual(
            self.po_one.status,
            "in_production",
        )

    def test_out_of_order_shipped_event_is_rejected(self):
        self.po_one.status = "received"
        self.po_one.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            update_supplier_tracking(
                self.po_one,
                shipment_status="shipped",
                user=self.user,
            )

        self.po_one.refresh_from_db()

        self.assertEqual(
            self.po_one.status,
            "received",
        )

    @patch(
        "products.services.supplier_tracking."
        "synchronize_customer_order_from_purchase_orders"
    )
    def test_tracking_only_update_synchronizes_order(
        self,
        mock_synchronize,
    ):
        update_supplier_tracking(
            self.po_one,
            tracking_number="TRACK-ONLY",
            user=self.user,
        )

        mock_synchronize.assert_called_once_with(
            self.order
        )

    @patch(
        "products.services.supplier_tracking."
        "synchronize_customer_order_from_purchase_orders"
    )
    def test_exact_duplicate_event_skips_synchronization(
        self,
        mock_synchronize,
    ):
        self.po_one.tracking_number = "TRACK-DUPLICATE"
        self.po_one.save(
            update_fields=["tracking_number"]
        )

        update_supplier_tracking(
            self.po_one,
            tracking_number="TRACK-DUPLICATE",
            user=self.user,
        )

        mock_synchronize.assert_not_called()