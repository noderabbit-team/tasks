import os
import shutil
import random
import subprocess
import sys

import psycopg2

from dz.tasklib.tests.dztestcase import DZTestCase
from dz.tasklib import (database,
                        taskconfig)


def _can_access_db(dbinfo, try_create=False):
    """Test whether the given user can access the database."""

    sql = "select 'that worked'"
    if try_create:
        sql = ("create table foo (bar integer); insert into foo values (1);" +
               sql + " from foo;")

    if dbinfo.password is not None:
        cmd = ("PGUSER=%s PGPASSWD=%s psql %s -c \"%s\"") % (
            dbinfo.username, dbinfo.password, dbinfo.db_name, sql)
    else:
        cmd = ("PGUSER=%s psql %s -c \"%s\"") % (
            dbinfo.username, dbinfo.db_name, sql)

    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    (stdout, stderr) = p.communicate()

    if p.returncode != 0:
        # Don't actually print this; sometimes we want this to fail
        # print(("psql attempt didn't work, exited status %d, " +
        #        "stdout=%r, stderr=%r") % (p.returncode, stdout, stderr))
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

        # make DatabaseInfo a dict subclass so it can be serialized
        self.assertTrue(isinstance(di, dict))

    def test_get_or_create_and_drop(self):
        """
        Create a new DB & user, ensure user can use only that DB, then drop.
        """

        database.lock_down_public_permissions()

        app_id = "test_%d" % random.randint(100, 1000)

        try:
            dbinfo = database.get_or_create_database(app_id)

            for attr in ("just_created", "host", "db_name", "username",
                         "password"):
                self.assertTrue(getattr(dbinfo, attr))

            self.assertTrue(_can_access_db(dbinfo, try_create=True),
                            "Ensure new database can be accessed.")

            cust_nrweb_dbinfo = database.DatabaseInfo(
                host=dbinfo.host, db_name="nrweb",
                username=dbinfo.username, password=dbinfo.password)
            self.assertTrue(not _can_access_db(cust_nrweb_dbinfo),
                            "Ensure cust user CANNOT access nrweb.")

            nrweb_nrweb_dbinfo = database.DatabaseInfo(
                host=dbinfo.host, db_name="nrweb",
                username="nrweb", password="")
            self.assertTrue(_can_access_db(nrweb_nrweb_dbinfo),
                            "Ensure nrweb can access nrweb.")

        finally:
            database.drop_database(dbinfo.db_name)
            database.drop_user(dbinfo.username)

        self.assertTrue(not _can_access_db(dbinfo),
                        "Ensure dropped database can no longer be accessed.")

    '''
    Shoot - I don't think we need this anymore.

    def test_create_twice(self):
        """
        Test creating a database and then immediately creating another in a
        separate module space, to ensure that there aren't lingering
        connections to the template1 db preventing progress.
        """
        here = os.path.abspath(os.path.split(__file__)[0])
        database_src = os.path.join(here, "..", "database.py")

        test_modules_dir = self.makeDir()
        database_1_file = os.path.join(test_modules_dir, "database_1.py")
        database_2_file = os.path.join(test_modules_dir, "database_2.py")

        shutil.copyfile(database_src, database_1_file)
        shutil.copyfile(database_src, database_2_file)

        sys.path.insert(0, test_modules_dir)

        import database_1
        import database_2

        self.assertTrue(database_1 is not database_2)
        self.assertTrue(database_1._get_conn is not database_2._get_conn)

        app_id_1 = "test_twice_1_%d" % random.randint(100, 1000)
        app_id_2 = "test_twice_2_%d" % random.randint(100, 1000)

        database_1.get_or_create_database(app_id_1)

        with self.assertRaises(psycopg2.OperationalError):
            database_2.get_or_create_database(app_id_2)

        for app_id in (app_id_1, app_id_2):
            try:
                database.drop_database(app_id)
                database.drop_user(app_id)
            except psycopg2.ProgrammingError:
                pass

        # now "fix" it
        orig_initial_db = taskconfig.DATABASE_SUPERUSER["initial_db"]
        taskconfig.DATABASE_SUPERUSER["initial_db"] = "nrweb"

        ### TODO: reload doesn't seem sufficient; try manually clearing conn
        database_1._get_conn().close()
        database_2._get_conn().close()

        database_1.get_or_create_database(app_id_1)
        database_2.get_or_create_database(app_id_2)
        '''
