"""Hand-rolled request validation (no extra dependency needed)."""

from decimal import Decimal, InvalidOperation
from typing import Any

from app.utils.errors import ValidationError

EMAIL_MIN_LEN = 5


def require_json(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object.")
    return payload


def validate_email(value: Any) -> str:
    if not isinstance(value, str) or len(value) < EMAIL_MIN_LEN:
        raise ValidationError("A valid 'customer_email' is required.")
    value = value.strip()
    local, sep, domain = value.partition("@")
    if not sep or not local or "." not in domain or domain.startswith("."):
        raise ValidationError(f"'{value}' is not a valid email address.")
    return value


def validate_price(value: Any) -> Decimal:
    try:
        price = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("'price' must be a number.") from None
    if price < 0:
        raise ValidationError("'price' cannot be negative.")
    if price > Decimal("99999999.99"):
        raise ValidationError("'price' exceeds the maximum allowed value.")
    return price.quantize(Decimal("0.01"))


def validate_stock(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("'stock_quantity' must be an integer.")
    if value < 0:
        raise ValidationError("'stock_quantity' cannot be negative.")
    return value


def validate_product_payload(payload: dict, partial: bool = False) -> dict:
    """Validate create (partial=False) or update (partial=True) payloads."""
    payload = require_json(payload)
    data: dict[str, Any] = {}

    if not partial or "name" in payload:
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValidationError("'name' is required and must be a non-empty string.")
        if len(name.strip()) > 255:
            raise ValidationError("'name' must be 255 characters or fewer.")
        data["name"] = name.strip()

    if not partial or "category" in payload:
        category = payload.get("category")
        if not isinstance(category, str) or not category.strip():
            raise ValidationError("'category' is required and must be a string.")
        if len(category.strip()) > 100:
            raise ValidationError("'category' must be 100 characters or fewer.")
        data["category"] = category.strip()

    if not partial or "price" in payload:
        if "price" not in payload:
            raise ValidationError("'price' is required.")
        data["price"] = validate_price(payload.get("price"))

    if "stock_quantity" in payload:
        data["stock_quantity"] = validate_stock(payload.get("stock_quantity"))
    elif not partial:
        data["stock_quantity"] = 0

    if "description" in payload:
        description = payload.get("description")
        if description is not None and not isinstance(description, str):
            raise ValidationError("'description' must be a string.")
        data["description"] = description

    if partial and not data:
        raise ValidationError("No valid fields supplied for update.")

    return data


def validate_order_payload(payload: dict) -> dict:
    payload = require_json(payload)

    email = validate_email(payload.get("customer_email"))

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValidationError("'items' must be a non-empty array.")
    if len(items) > 50:
        raise ValidationError("An order cannot contain more than 50 line items.")

    # Merge duplicate product ids so stock maths stays correct.
    merged: dict[int, int] = {}
    for index, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise ValidationError(f"items[{index}] must be an object.")

        product_id = raw.get("product_id")
        if isinstance(product_id, bool) or not isinstance(product_id, int) or product_id <= 0:
            raise ValidationError(f"items[{index}].product_id must be a positive integer.")

        quantity = raw.get("quantity")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValidationError(f"items[{index}].quantity must be a positive integer.")
        if quantity > 1000:
            raise ValidationError(f"items[{index}].quantity exceeds the per-line limit of 1000.")

        merged[product_id] = merged.get(product_id, 0) + quantity

    return {
        "customer_email": email,
        "items": [{"product_id": pid, "quantity": qty} for pid, qty in merged.items()],
    }


def validate_pagination(args, default_size: int, max_size: int) -> tuple[int, int]:
    try:
        page = int(args.get("page", 1))
        limit = int(args.get("limit", default_size))
    except (TypeError, ValueError):
        raise ValidationError("'page' and 'limit' must be integers.") from None

    if page < 1:
        raise ValidationError("'page' must be 1 or greater.")
    if limit < 1:
        raise ValidationError("'limit' must be 1 or greater.")
    if limit > max_size:
        raise ValidationError(f"'limit' cannot exceed {max_size}.")
    return page, limit
