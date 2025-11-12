"""
WSGI config for crm project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

# Monkey patch gevent for async support (required when using gevent workers)
# This must be done before importing Django
try:
    from gevent import monkey
    monkey.patch_all()
except ImportError:
    # gevent not installed, skip monkey patching
    pass

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm.settings')

application = get_wsgi_application()
