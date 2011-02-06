BROKER_HOST = "localhost"
BROKER_PORT = 5672
BROKER_USER = "djz"
BROKER_PASSWORD = "djz"
BROKER_VHOST = "djz"

CELERY_RESULT_BACKEND = "database"
CELERY_RESULT_DBURI = "postgresql://nrweb:nrweb@/nrweb"

CELERY_IMPORTS = ("dz.tasks", )
