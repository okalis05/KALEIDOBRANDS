# KaleidoBrands Payments

KaleidoBrands uses Stripe Checkout for card payments.

## Flow

1. Customer creates an order.
2. Customer clicks Pay Now.
3. Stripe Checkout opens.
4. Customer pays with card.
5. Stripe sends webhook to KaleidoBrands.
6. KaleidoBrands verifies webhook signature.
7. Order is marked paid.
8. Customer and Sales receive payment emails.

## Local Webhook Testing

Run Django:

```bash
python manage.py runserver