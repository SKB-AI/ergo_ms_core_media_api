import os

from django.core.asgi import get_asgi_application

from media_server.deploy import get_settings_module

os.environ.setdefault('DJANGO_SETTINGS_MODULE', get_settings_module())

application = get_asgi_application()
