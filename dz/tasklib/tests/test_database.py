import random
import subprocess

from dz.tasklib.tests.dztestcase import DZTestCase
from dz.tasklib import database


def _can_access_db(database, username, password=None):
    """Test whether the given user can access the database."""

    if password is not None:
        cmd = ("PGUSER=%s PGPASSWD=%s psql %s -c " +
               "\"select 'that worked'\"") % (
            username, password, database)
    else:
        cmd = ("PGUSER=%s psql %s -c " +
               "\"select 'that worked'\"") % (
            username, database)

    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    (stdout, stderr) = p.communicate()

    if p.returncode != 0:
        # Don't actually print this; sometimes we want this to fail
        #print("psql attempt didn't work, exited status %d" % p.returncode)
        return False

    assert "that worked" in stdout, ("If psql didn't exit, then this " +
                                     "should always succeed")

    return True


class DatabaseTasksTestCase(DZTestCase):

    def test_get_or_create_and_drop(self):
        """
        Create a new database, then drop it.
        """

        database.lock_down_public_permissions()

        app_id = "test_%d" % random.randint(100, 1000)
        (created, db_host, db_name, db_username, db_password) = \
            database.get_or_create_database(app_id)

        for resultpart in (created, db_host, db_name, db_username):
            self.assertTrue(created)
            self.assertTrue(db_host)
            self.assertTrue(db_name)
            self.assertTrue(db_username)

        self.assertTrue(_can_access_db(db_name, db_username, db_password),
                        "Ensure new database can be accessed.")

        self.assertTrue(not _can_access_db("nrweb", db_username, db_password),
                        "Ensure cust user CANNOT access nrweb.")

        self.assertTrue(_can_access_db("nrweb", "nrweb"),
                        "Ensure nrweb can access nrweb.")

        database.drop_database(db_name)
        database.drop_user(db_username)

        self.assertTrue(not _can_access_db(db_name, db_username, db_password),
                        "Ensure dropped database can no longer be accessed.")
