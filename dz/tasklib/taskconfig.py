NR_PIP_REQUIREMENTS_FILENAME = 'noderabbit_requirements.txt'
NR_PTH_FILENAME = 'noderabbit.pth'

NR_BUNDLE_BUCKET = "nr-bundles"

NR_CUSTOMER_DIR = "/cust"

TEST_REPO_DIR = "/usr/local/noderabbit/test-repos"
TEST_REPO_URL_PREFIX = "test://"

DATABASE_SUPERUSER = {
    "username": "nrweb",
    "initial_db": "template1",
}

APPSERVERS = [ 'localhost' ]

# if you're unable to create databases as user "nrweb", then you need to run these commands
# $ psql -U postgres
# postgres=# alter role nrweb superuser createdb createrole;
# ALTER ROLE
