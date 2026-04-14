from flask import Blueprint
finance_bp = Blueprint('finance', __name__, template_folder='../templates/finance')
from app.finance import routes
