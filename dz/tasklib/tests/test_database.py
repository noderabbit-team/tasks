import random
import subprocess

from dz.tasklib.tests.dztestcase import DZTestCase
from dz.tasklib import database


def _can_access_db(dbinfo):
    """Test whether the given user can access the database."""

    if dbinfo.password is not None:
        cmd = ("PGUSER=%s PGPASSWD=%s psql %s -c " +
               "\"select 'that worked'\"") % (
            dbinfo.username, dbinfo.password, dbinfo.db_name)
    else:
        cmd = ("PGUSER=%s psql %s -c " +
               "\"select 'that worked'\"") % (
            dbinfo.username, dbinfo.db_name)

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

    def test_databaseinfo(self):
        """
        Test the DatabaseInfo class.
        """
        di = database.DatabaseInfo(host="host", db_name="mydb", password="123",
                                   username="user")
        self.assertEqual(di.host, "host")
        self.assertEqual(di.username, "user")
        self.assertEqual(di.password, "123")
        self.assertEqual(di.db_name, "mydb")

    def test_get_or_create_and_drop(self):
        """
        Create a new database, then drop it.
        """

        database.lock_down_public_permissions()

        app_id = "test_%d" % random.randint(100, 1000)
        dbinfo = database.get_or_create_database(app_id)

        for attr in ("just_created", "host", "db_name", "username",
                     "password"):
            self.assertTrue(getattr(dbinfo, attr))

        self.assertTrue(_can_access_db(dbinfo),
                        "Ensure new database can be accessed.")

        cust_nrweb_dbinfo = database.DatabaseInfo(host=dbinfo.host,
                                             db_name="nrweb",
                                             username=dbinfo.username,
                                             password=dbinfo.password)
        self.assertTrue(not _can_access_db(cust_nrweb_dbinfo),
                        "Ensure cust user CANNOT access nrweb.")

        nrweb_nrweb_dbinfo = database.DatabaseInfo(host=dbinfo.host,
                                                   db_name="nrweb",
                                                   username="nrweb",
                                                   # assume pg_hba trusts me
                                                   password="") 
        self.assertTrue(_can_access_db(nrweb_nrweb_dbinfo),
                        "Ensure nrweb can access nrweb.")

        database.drop_database(dbinfo.db_name)
        database.drop_user(dbinfo.username)

        self.assertTrue(not _can_access_db(dbinfo),
                        "Ensure dropped database can no longer be accessed.")
