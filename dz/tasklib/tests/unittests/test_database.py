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


class PostGisTestCase(DZTestCase):

    def setUp(self):
        super(PostGisTestCase, self).setUp()
        self.app_id = "test_pgis_%d" % random.randint(100, 1000)
        self.dbinfo = database.get_or_create_database(self.app_id)
        conn_string = (("dbname=%(db_name)s user=%(username)s "
                        "password=%(password)s host=%(host)s") %
                       self.dbinfo)
        self.conn = psycopg2.connect(conn_string)
        self.conn.set_isolation_level(
            psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

    def tearDown(self):
        super(PostGisTestCase, self).tearDown()
        self.conn.close()
        database.drop_database(self.dbinfo.db_name)
        database.drop_user(self.dbinfo.username)

    def test_create_postgis(self):
        database.enable_postgis(self.app_id)
        cur = self.conn.cursor()
        cur.execute("select 3+3;")
        self.assertEqual(cur.fetchone()[0], 6)

        cur.execute("select postgis_lib_version();")
        self.assertEqual(cur.fetchone()[0], "1.5.1")
