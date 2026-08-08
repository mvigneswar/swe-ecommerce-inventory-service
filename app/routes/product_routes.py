"""HTTP layer for the product catalog."""

from flask import Blueprint, current_app, request

from app.controllers import product_controller as ctrl
from app.schemas.validators import validate_pagination, validate_product_payload

product_bp = Blueprint("products", __name__, url_prefix="/api/products")


@product_bp.get("")
def get_products():
    page, limit = validate_pagination(
        request.args,
        current_app.config["DEFAULT_PAGE_SIZE"],
        current_app.config["MAX_PAGE_SIZE"],
    )
    return ctrl.list_products(
        category=request.args.get("category"),
        search=request.args.get("search"),
        page=page,
        limit=limit,
    )


@product_bp.get("/categories")
def get_categories():
    return ctrl.list_categories()


@product_bp.get("/<int:product_id>")
def get_product(product_id: int):
    return ctrl.get_product(product_id)


@product_bp.post("")
def post_product():
    data = validate_product_payload(request.get_json(silent=True))
    return ctrl.create_product(data)


@product_bp.put("/<int:product_id>")
def put_product(product_id: int):
    data = validate_product_payload(request.get_json(silent=True), partial=True)
    return ctrl.update_product(product_id, data)


@product_bp.delete("/<int:product_id>")
def remove_product(product_id: int):
    return ctrl.delete_product(product_id)
