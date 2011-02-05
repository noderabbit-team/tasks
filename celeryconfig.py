BROKER_HOST = "localhost"
BROKER_PORT = 5672
BROKER_USER = "myuser"
BROKER_PASSWORD = "mypassword"

CELERY_RESULT_BACKEND = "amqp"
CELERY_IMPORTS = ("tasks", )
