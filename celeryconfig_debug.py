from celeryconfig import *


BROKER_HOST = "localhost"
BROKER_PORT = 5672
BROKER_USER = "zoom"
BROKER_PASSWORD = "zoom"
#BROKER_VHOST = "rabbit"

CELERY_IMPORTS = ("tasks", )

