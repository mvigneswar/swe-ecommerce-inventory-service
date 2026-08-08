"""UI routes serving the visual dashboard (HTML console)."""

from flask import Blueprint, render_template

ui_bp = Blueprint("ui", __name__)


@ui_bp.get("/dashboard")
def dashboard():
    """Serve the single-page visual dashboard at /dashboard."""
    return render_template("dashboard.html")
