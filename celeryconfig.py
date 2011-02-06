BROKER_HOST = "ec2-72-44-42-23.compute-1.amazonaws.com"
#BROKER_PORT = 5672
BROKER_PORT = 4369
BROKER_USER = "nrweb"
BROKER_PASSWORD = "MiXNYPwsKbRkQCEU"

CELERY_RESULT_BACKEND = "database"
CELERY_RESULT_DBURI = "postgresql://nrweb:nrweb@/nrweb"
CELERY_IMPORTS = ("dz.tasks", )
