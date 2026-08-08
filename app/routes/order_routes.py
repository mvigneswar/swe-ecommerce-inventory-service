"""HTTP layer for orders."""

from flask import Blueprint, current_app, request

from app.controllers import order_controller as ctrl
from app.schemas.validators import validate_order_payload, validate_pagination

order_bp = Blueprint("orders", __name__, url_prefix="/api/orders")


@order_bp.post("")
def post_order():
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
    return ctrl.cancel_order(order_id)
