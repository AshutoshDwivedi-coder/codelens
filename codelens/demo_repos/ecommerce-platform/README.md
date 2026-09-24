# ShopFlow E-Commerce & Checkout Engine

High-performance e-commerce backend platform handling shopping carts, inventory reservations, Stripe payment webhooks, and order fulfillment workflows.

## Key Features

- **Stripe Webhook Processing**: Verifies cryptographic webhook signatures and triggers asynchronous payment fulfillment.
- **Atomic Inventory Reservations**: Locks product SKU quantities during checkout using Redis distributed locks to prevent overselling.
- **Dynamic Discount Engine**: Calculates tiered promotional discount codes, coupon stacking, and regional sales tax.
- **Order State Machine**: Enforces strict transitions from `PENDING` -> `PAID` -> `PROCESSING` -> `SHIPPED` -> `DELIVERED`.
- **Cart Abandonment Tracking**: Detects idle shopping carts after 2 hours and queues customer recovery notifications.

## System Architecture & Modules

- `api/checkout.py`: Checkout session initialization and inventory locking.
- `services/payment.py`: Stripe payment intent creation and signature verification.
- `services/cart.py`: Shopping cart calculation, coupon discounts, and tax computation.
- `models/order.py`: Order entity schema, line items, and state machine transitions.
- `services/inventory.py`: Redis distributed locking for warehouse SKU reservations.

## Questions to Ask this Codebase

- Where is the Stripe webhook signature verification handled in `services/payment.py`?
- How does atomic inventory reservation prevent overselling in `services/inventory.py`?
- How does the cart apply coupon discounts and calculate taxes in `services/cart.py`?
- Where is the checkout session initialized in `api/checkout.py`?
- How does the order state machine transition orders in `models/order.py`?
- How are abandoned cart recovery notifications scheduled?
