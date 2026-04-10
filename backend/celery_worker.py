from app import create_app
from app.tasks import celery_app

flask_app = create_app()
flask_app.app_context().push()
