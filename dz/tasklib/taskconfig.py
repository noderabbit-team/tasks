NR_PIP_REQUIREMENTS_FILENAME = 'noderabbit_requirements.txt'
NR_PTH_FILENAME = 'noderabbit.pth'

NR_BUNDLE_BUCKET = "nr-bundle-bucket"

NR_CUSTOMER_DIR = "/cust"

TEST_REPO_DIR = "/usr/local/noderabbit/test-repos"
TEST_REPO_URL_PREFIX = "test://"

DATABASE_SUPERUSER = {
    "username": "nrweb",
    "initial_db": "template1",
}

# note: for each hostname below, make sure you have your celeryd listening
# on a queue called appserver:<hostname>, e.g.
# celeryd --concurrency=2 -Q appserver,appserver:localhost
APPSERVERS = [ 'localhost' ]

# if you're unable to create databases as user "nrweb", then you need to run these commands
# $ psql -U postgres
# postgres=# alter role nrweb superuser createdb createrole;
# ALTER ROLE

SUPERVISOR_APP_CONF_DIR = "/etc/supervisor/conf.d"
APP_SERVICE_START_PORT = 10000
APP_SERVICE_MAX_PORT = 25000

DEFAULT_BUNDLE_STORAGE_ENGINE = "bundle_storage"  # override to use
                                                  # "bundle_storage_local"
                                                  # in development

try:
    from local_taskconfig import *
except ImportError:
    pass
