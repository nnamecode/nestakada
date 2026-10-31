import os
from django.core.wsgi import get_wsgi_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE','estakada.settings.local_http')
application = get_wsgi_application()
