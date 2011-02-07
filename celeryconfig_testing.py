"""
Settings used for automated testing of celery.
"""
from celeryconfig_debug import *

CELERY_IMPORTS = ("dz.tasklib.tests.tasks_for_testing",)
