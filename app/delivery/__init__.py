from flask import Blueprint
delivery_bp = Blueprint('delivery', __name__, template_folder='../templates/delivery')
from app.delivery import routes
