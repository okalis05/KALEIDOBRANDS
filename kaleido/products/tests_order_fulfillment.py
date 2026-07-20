from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase

from customers.models import Order
from products.models import (
    Supplier,
    SupplierPurchaseOrder,
)
from products.services.order_fulfillment import (
    determine_customer_order_status,
    synchronize_customer_order_from_purchase_orders,
)


User = get_user_model()


class OrderFulfillmentSynchronizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="fulfillment-test",
            email="customer@example.com",
            password="test-password",
        )

        self.supplier_one = Supplier.objects.create(
            name="Supplier One",
            slug="supplier-one",
            email="supplier-one@example.com",
        )

        self.supplier_two = Supplier.objects.create(
            name="Supplier Two",
            slug="supplier-two",
            email="supplier-two@example.com",
        )


        self.order = Order.objects.create(
            customer=self.user,
            order_number="KB-FULFILL-001",
            payment_status="paid",
            status="pending",
        )

        self.po_one = SupplierPurchaseOrder.objects.create(
            supplier=self.supplier_one,
            customer_order=self.order,
            po_number="KB-PO-FULFILL-001",
            status="draft",
        )

        self.po_two = SupplierPurchaseOrder.objects.create(
            supplier=self.supplier_two,
            customer_order=self.order,
            po_number="KB-PO-FULFILL-002",
            status="draft",
        )

    def test_no_purchase_orders_returns_none(self):
        order_without_purchase_orders = Order.objects.create(
            customer=self.user,
            order_number="KB-FULFILL-EMPTY",
            payment_status="paid",
            status="pending",
        )

        result = determine_customer_order_status(
            order_without_purchase_orders
        )

        self.assertIsNone(result)

    def test_draft_purchase_orders_keep_order_pending(self):
        result = determine_customer_order_status(
            self.order
        )

        self.assertEqual(result, "pending")

    def test_all_sent_purchase_orders_approve_order(self):
        self.po_one.status = "sent"
        self.po_one.save(update_fields=["status"])

        self.po_two.status = "sent"
        self.po_two.save(update_fields=["status"])

        synchronize_customer_order_from_purchase_orders(
            self.order
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            "approved",
        )

    def test_mixed_sent_and_confirmed_approve_order(self):
        self.po_one.status = "sent"
        self.po_one.save(update_fields=["status"])

        self.po_two.status = "confirmed"
        self.po_two.save(update_fields=["status"])

        synchronize_customer_order_from_purchase_orders(
            self.order
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            "approved",
        )

    def test_all_production_or_later_set_order_to_production(self):
        self.po_one.status = "in_production"
        self.po_one.save(update_fields=["status"])

        self.po_two.status = "shipped"
        self.po_two.save(update_fields=["status"])

        synchronize_customer_order_from_purchase_orders(
            self.order
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            "production",
        )

    def test_one_shipped_supplier_does_not_ship_entire_order(self):
        self.po_one.status = "shipped"
        self.po_one.save(update_fields=["status"])

        self.po_two.status = "in_production"
        self.po_two.save(update_fields=["status"])

        synchronize_customer_order_from_purchase_orders(
            self.order
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            "production",
        )

    def test_all_shipped_or_received_set_order_to_shipped(self):
        self.po_one.status = "shipped"
        self.po_one.save(update_fields=["status"])

        self.po_two.status = "received"
        self.po_two.save(update_fields=["status"])

        synchronize_customer_order_from_purchase_orders(
            self.order
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            "shipped",
        )

    def test_all_received_set_order_to_delivered(self):
        self.po_one.status = "received"
        self.po_one.save(update_fields=["status"])

        self.po_two.status = "received"
        self.po_two.save(update_fields=["status"])

        synchronize_customer_order_from_purchase_orders(
            self.order
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            "delivered",
        )

    def test_cancelled_purchase_order_does_not_block_shipping(self):
        self.po_one.status = "shipped"
        self.po_one.save(update_fields=["status"])

        self.po_two.status = "cancelled"
        self.po_two.save(update_fields=["status"])

        synchronize_customer_order_from_purchase_orders(
            self.order
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            "shipped",
        )

    def test_all_cancelled_purchase_orders_cancel_order(self):
        self.po_one.status = "cancelled"
        self.po_one.save(update_fields=["status"])

        self.po_two.status = "cancelled"
        self.po_two.save(update_fields=["status"])

        synchronize_customer_order_from_purchase_orders(
            self.order
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            "cancelled",
        )

    def test_status_does_not_move_backward(self):
        self.order.status = "shipped"
        self.order.save(update_fields=["status"])

        self.po_one.status = "sent"
        self.po_one.save(update_fields=["status"])

        self.po_two.status = "confirmed"
        self.po_two.save(update_fields=["status"])

        synchronize_customer_order_from_purchase_orders(
            self.order
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            "shipped",
        )

    def test_tracking_information_is_copied(self):
        self.po_one.status = "shipped"
        self.po_one.tracking_number = "TRACK-123"
        self.po_one.tracking_url = (
            "https://tracking.example.com/TRACK-123"
        )
        self.po_one.save(
            update_fields=[
                "status",
                "tracking_number",
                "tracking_url",
            ]
        )

        self.po_two.status = "received"
        self.po_two.save(update_fields=["status"])

        synchronize_customer_order_from_purchase_orders(
            self.order
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.tracking_number,
            "TRACK-123",
        )

        self.assertEqual(
            self.order.tracking_url,
            "https://tracking.example.com/TRACK-123",
        )

        self.assertEqual(
            self.order.carrier,
            "Supplier Carrier",
        )

    def test_estimated_ship_date_is_copied(self):
        self.po_one.status = "shipped"
        self.po_one.estimated_ship_date = date(
            2026,
            8,
            10,
        )
        self.po_one.save(
            update_fields=[
                "status",
                "estimated_ship_date",
            ]
        )

        self.po_two.status = "shipped"
        self.po_two.estimated_ship_date = date(
            2026,
            8,
            14,
        )
        self.po_two.save(
            update_fields=[
                "status",
                "estimated_ship_date",
            ]
        )

        synchronize_customer_order_from_purchase_orders(
            self.order
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.estimated_delivery,
            date(2026, 8, 14),
        )

    def test_shipping_email_is_sent_once(self):
        self.po_one.status = "shipped"
        self.po_one.save(update_fields=["status"])

        self.po_two.status = "shipped"
        self.po_two.save(update_fields=["status"])

        with self.settings(
            EMAIL_BACKEND=(
                "django.core.mail.backends.locmem.EmailBackend"
            )
        ):
            synchronize_customer_order_from_purchase_orders(
                self.order
            )

            self.order.refresh_from_db()

            self.assertEqual(len(mail.outbox), 1)
            self.assertTrue(
                self.order.shipping_email_sent
            )

            synchronize_customer_order_from_purchase_orders(
                self.order
            )

            self.assertEqual(len(mail.outbox), 1)

    @patch(
        "products.services.order_fulfillment."
        "EmailMessage.send"
    )
    def test_shipping_email_failure_does_not_break_sync(
        self,
        mocked_send,
    ):
        mocked_send.side_effect = Exception(
            "Mail server unavailable"
        )

        self.po_one.status = "shipped"
        self.po_one.save(update_fields=["status"])

        self.po_two.status = "shipped"
        self.po_two.save(update_fields=["status"])

        synchronize_customer_order_from_purchase_orders(
            self.order
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            "shipped",
        )
