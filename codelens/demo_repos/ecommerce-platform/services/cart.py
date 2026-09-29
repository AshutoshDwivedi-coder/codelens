"""
services/cart.py - Shopping cart calculation, coupon discounts, and tax computation.
"""


def apply_coupon_discount(subtotal_cents: int, coupon_code: str | None) -> int:
    """Apply tiered promotional coupon codes to a cart subtotal."""
    if not coupon_code:
        return 0
    code = coupon_code.upper()
    if code == "SAVE10":
        return int(subtotal_cents * 0.10)
    if code == "SAVE20":
        return int(subtotal_cents * 0.20)
    return 0


def calculate_sales_tax(subtotal_cents: int, region: str = "US-CA") -> int:
    """Calculate regional sales tax for the discounted cart subtotal."""
    rates = {"US-CA": 0.0725, "US-NY": 0.08, "US-TX": 0.0625}
    rate = rates.get(region, 0.05)
    return int(subtotal_cents * rate)


def calculate_cart_total(cart_items: list[dict], coupon_code: str | None = None, region: str = "US-CA") -> dict:
    """Compute cart subtotal, coupon discounts, tax, and grand total."""
    subtotal = sum(int(i["unit_price_cents"]) * int(i["quantity"]) for i in cart_items)
    discount = apply_coupon_discount(subtotal, coupon_code)
    taxable = max(subtotal - discount, 0)
    tax = calculate_sales_tax(taxable, region)
    return {
        "subtotal_cents": subtotal,
        "discount_cents": discount,
        "tax_cents": tax,
        "total_cents": taxable + tax,
    }
