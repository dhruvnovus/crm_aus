"""
WSGI config for crm project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
import sys

# Monkey patch gevent for async support (required when using gevent workers)
# Only apply monkey patching in production (when using gunicorn with gevent workers)
# Skip monkey patching when running development server (runserver) to avoid threading issues
is_development_server = (
    len(sys.argv) > 1 and 'runserver' in sys.argv[1]
) or (
    len(sys.argv) > 0 and 'manage.py' in sys.argv[0] and any('runserver' in arg for arg in sys.argv)
)

if not is_development_server:
    try:
        from gevent import monkey
        # Apply monkey patching early, before any other imports
        monkey.patch_all()
    except ImportError:
        # gevent not installed, skip monkey patching
        pass

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm.settings')

application = get_wsgi_application()
