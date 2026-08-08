"""HTTP layer for the product catalog."""

from flask import Blueprint, current_app, request

from app.controllers import product_controller as ctrl
from app.schemas.validators import validate_pagination, validate_product_payload

product_bp = Blueprint("products", __name__, url_prefix="/api/products")


@product_bp.get("")
def get_products():
    """
    List products (paginated, cache-aside via Redis).
    ---
    parameters:
      - in: query
        name: page
        type: integer
        required: false
        default: 1
      - in: query
        name: page_size
        type: integer
        required: false
        default: 20
      - in: query
        name: category
        type: string
        required: false
      - in: query
        name: search
        type: string
        required: false
    responses:
      200:
        description: A page of products. meta.cached / meta.response_time_ms show cache behaviour.
        schema:
          type: object
          properties:
            success: {type: boolean}
            data:
              type: array
              items:
                type: object
                properties:
                  id: {type: integer}
                  name: {type: string}
                  category: {type: string}
                  price: {type: number}
                  stock_quantity: {type: integer}
            meta:
              type: object
              properties:
                cached: {type: boolean}
                response_time_ms: {type: number}
                pagination:
                  type: object
                  properties:
                    page: {type: integer}
                    limit: {type: integer}
                    total: {type: integer}
                    pages: {type: integer}
    """
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
    """
    Create a product.
    ---
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [name, category, price]
          properties:
            name: {type: string, example: "Mechanical Keyboard"}
            category: {type: string, example: "Peripherals"}
            price: {type: number, example: 299.99}
            stock_quantity: {type: integer, example: 50}
            description: {type: string, example: "Hot-swappable"}
    responses:
      201:
        description: Product created.
    """
    data = validate_product_payload(request.get_json(silent=True))
    return ctrl.create_product(data)


@product_bp.put("/<int:product_id>")
def put_product(product_id: int):
    """
    Update a product (partial update supported).
    ---
    parameters:
      - in: path
        name: product_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            name: {type: string}
            category: {type: string}
            price: {type: number}
            stock_quantity: {type: integer}
            description: {type: string}
    responses:
      200:
        description: Product updated.
      404:
        description: Product not found.
    """
    data = validate_product_payload(request.get_json(silent=True), partial=True)
    return ctrl.update_product(product_id, data)


@product_bp.delete("/<int:product_id>")
def remove_product(product_id: int):
    return ctrl.delete_product(product_id)
