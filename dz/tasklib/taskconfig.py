import os

from dz.tasklib.taskconfig_django import (DJANGO_VERSIONS,
                                          DJANGO_VERSION_DEFAULT,
                                          DJANGO_VERSIONS_CHOICES,
                                          DJANGO_TARBALLS_DIR,
                                          #PYTHON_VERSIONS,
                                          #PYTHON_VERSION_DEFAULT,
                                          )

NR_PIP_REQUIREMENTS_FILENAME = 'noderabbit_requirements.txt'
NR_PTH_FILENAME = 'noderabbit.pth'

STAGING = True
if STAGING:
    NR_BUNDLE_BUCKET = "nr-bundle-bucket-staging"
else:
    NR_BUNDLE_BUCKET = "nr-bundle-bucket"

NR_CUSTOMER_DIR = "/cust"

PROJECT_SYSID_FORMAT = "p%08d"

# format for the vhost entry that each project gets by default,
# based on the sysid string for that project.
CANONICAL_VIRTUAL_HOST_FORMAT = "%s.djangozoom.net"
CUSTOMER_DNS_ROOT_DOMAIN = "djangozoom.net"

TEST_REPO_DIR = "/usr/local/noderabbit/test-repos"
TEST_REPO_URL_PREFIX = "test://"

NODE_META_DATA_DIR = "/usr/local/noderabbit/node_meta"

DATABASE_SUPERUSER = {
    "username": "nrweb",
    "initial_db": "nrweb",
    # The initial_db mustn't be template1, because that is used internally
    # by postgresql when creating a database. having an open connection to
    # template1 therefore stops DB creation.
}

# note: for each hostname below, make sure you have your celeryd listening
# on a queue called appserver:<hostname>, e.g.
# celeryd --concurrency=2 -Q appserver,appserver:localhost
APPSERVERS = ['localhost']

# if you're unable to create databases as user "nrweb", then you need to run
# these commands:
# $ psql -U postgres
# postgres=# alter role nrweb superuser createdb createrole;
# ALTER ROLE

SUPERVISOR_APP_CONF_DIR = "/etc/supervisor/conf.d"
APP_SERVICE_START_PORT = 10000
APP_SERVICE_MAX_PORT = 25000

NGINX_SITES_ENABLED_DIR = "/etc/nginx/sites-enabled"
NGINX_REMOVE_OLD_BUNDLES_ON_UPDATE = True

PRIVILEGED_PROGRAMS_PATH = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    "privileged-bin")

DEFAULT_BUNDLE_STORAGE_ENGINE = "bundle_storage"  # override to use
                                                  # "bundle_storage_local"
                                                  # in development

DZ_ADMIN_MEDIA = {
    "url_path": "/_dz/admin_media/",
    "bundle_file_path":
        "lib/python2.6/site-packages/django/contrib/admin/media",
    }

LOG_DIR_SUPERVISOR = "/var/log/supervisor"

# How long should the celery broadcast timeout be for log requests?
LOGS_CELERY_BCAST_TIMEOUT = 1

try:
    from local_taskconfig import *
except ImportError:
    pass
