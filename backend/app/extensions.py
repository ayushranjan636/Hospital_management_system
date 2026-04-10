"""Initialize Flask extensions"""

from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_caching import Cache
from flask_mail import Mail


# Database
db = SQLAlchemy()

# Authentication (JWT tokens)
jwt = JWTManager()

# Caching with SimpleCache
cache = Cache(config={"CACHE_TYPE": "SimpleCache"})

# Email sending
mail = Mail()
