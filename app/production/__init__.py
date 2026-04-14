from flask import Blueprint
production_bp = Blueprint('production', __name__, template_folder='../templates/production')
from app.production import routes
