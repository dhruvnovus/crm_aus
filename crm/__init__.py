import pymysql
pymysql.install_as_MySQLdb()

# Start APScheduler when Django starts
# Only start in the main process to avoid multiple schedulers in multi-worker setups
import os
import sys
import logging
# Check if we're in the main process
# RUN_MAIN is set by Django's runserver, but we also check for other cases
is_main_process = (
    os.environ.get('RUN_MAIN') == 'true' or
    'runserver' in sys.argv or
    (len(sys.argv) > 0 and 'manage.py' in sys.argv[0] and 'runserver' in sys.argv)
)

if is_main_process:
    try:
        from .scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        logger = logging.getLogger("dea_crm")
        logger.warning(f"Could not start scheduler: {str(e)}")