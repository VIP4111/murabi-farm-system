from flask import Blueprint

warehouses_bp = Blueprint("warehouses", __name__, url_prefix="/warehouses")

from app.warehouses import routes  # noqa: E402,F401
