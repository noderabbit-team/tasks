"""
Settings to use celery in a debug environment.  To set this up:

sudo apt-get install rabbitmq-server
sudo rabbitmqctl delete_user guest   # so as to remove the default login
sudo rabbitmqctl add_user zoom zoom
sudo rabbitmqctl add_vhost djangozoom
sudo rabbitmqctl set_permissions -p djangozoom zoom ".*" ".*" ".*"

To use this settings file, set the env var CELERY_CONFIG_MODULE to
"celeryconfig_debug".

If you get this DB error while running celeryd:

ProgrammingError: (ProgrammingError) relation "task_id_sequence" does not exist

Then you probably have a version mismatch between the celery that created
your DB tables and the one you're now using. The simple solution to this is
to drop the celery tables and let the version you're using re-create them on
demand. To do that, go into psql and run to following SQL commands:

DROP TABLE celery_taskmeta;
DROP SEQUENCE celery_taskmeta_id_seq;
DROP TABLE celery_tasksetmeta;
DROP SEQUENCE celery_tasksetmeta_id_seq;
"""

from celeryconfig_base import *

BROKER_HOST = "localhost"
#BROKER_PORT = 5672
BROKER_USER = "zoom"
BROKER_PASSWORD = "zoom"
BROKER_VHOST = "djangozoom"

CELERY_IMPORTS = ("dz.tasks", )

# local unauthenticated DB
CELERY_RESULT_DBURI = "postgresql+psycopg2://nrweb:nrweb@/nrweb"
