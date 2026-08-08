"""HTTP layer for orders."""

from flask import Blueprint, current_app, request

from app.controllers import order_controller as ctrl
from app.schemas.validators import validate_order_payload, validate_pagination

order_bp = Blueprint("orders", __name__, url_prefix="/api/orders")


@order_bp.post("")
def post_order():
    """
    Place an order (atomic stock decrement, deadlock-guarded).
    ---
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [customer_email, items]
          properties:
            customer_email: {type: string, example: "you@test.com"}
            items:
              type: array
              items:
                type: object
                required: [product_id, quantity]
                properties:
                  product_id: {type: integer, example: 1}
                  quantity: {type: integer, example: 2}
    responses:
      201:
        description: Order placed; stock decremented atomically.
      409:
        description: Insufficient stock or lock contention.
    """
    data = validate_order_payload(request.get_json(silent=True))
    return ctrl.create_order(data)


@order_bp.get("")
def get_orders():
    page, limit = validate_pagination(
        request.args,
        current_app.config["DEFAULT_PAGE_SIZE"],
        current_app.config["MAX_PAGE_SIZE"],
    )
    return ctrl.list_orders(email=request.args.get("email"), page=page, limit=limit)


@order_bp.get("/<int:order_id>")
def get_order(order_id: int):
    return ctrl.get_order(order_id)


@order_bp.post("/<int:order_id>/cancel")
def cancel_order(order_id: int):
    """
    Cancel an order and restore stock.
    ---
    parameters:
      - in: path
        name: order_id
        example: 1
        required: true
        type: integer
    responses:
      200:
        description: Order cancelled, stock restored.
      409:
        description: Order already cancelled.
    """
    return ctrl.cancel_order(order_id)
