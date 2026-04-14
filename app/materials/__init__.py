from flask import Blueprint
materials_bp = Blueprint('materials', __name__, template_folder='../templates/materials')
from app.materials import routes
