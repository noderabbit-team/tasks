"""
Manage databases for customer projects in our shared PostgreSQL cluster.
See: http://wiki.postgresql.org/wiki/Shared_Database_Hosting
"""

from dz.tasklib import taskconfig
from dz.tasklib import utils

import psycopg2
import random
import string

PASSWORD_CHARS = list(string.digits + string.ascii_letters)
PASSWORD_LENGTH = 30


def _get_conn():
    """Get a database connection, using the existing one if exists."""
    if not hasattr(_get_conn, "_conn"):
        _get_conn._conn = psycopg2.connect(
            "dbname=%(initial_db)s user=%(username)s" %
            taskconfig.DATABASE_SUPERUSER)
        _get_conn._conn.set_isolation_level(
            psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

    return _get_conn._conn


def _get_cur_conn_as_superuser():
    """Get a cursor and connection object as DB superuser (usually
    postgres)."""
    conn = _get_conn()
    cur = conn.cursor()

    return (cur, conn)


def _sql_as_superuser(sql):
    """Run some SQL code as the superuser."""
    (cur, conn) = _get_cur_conn_as_superuser()
    cur.execute(sql)
    cur.close()
    #conn.close()


def get_or_create_database(app_id):
    """
    Get or create a database and username for a customer application.

    :param app_id: app_id of the application. Currently this is used as the
    dbname and username, but those labels may change in the future.

    :returns: A tuple (created, db_host, db_name, db_username, db_password).
              If created is False, db_password will be None.
    """
    db_host = "localhost"
    db_name = app_id
    db_username = app_id
    db_password = None
    created = False

    (cur, conn) = _get_cur_conn_as_superuser()

    try:
        cur.execute("CREATE DATABASE %s" % db_name)
    except psycopg2.ProgrammingError:
        pass
    else:
        created = True
        db_password = ""
        for _ in xrange(PASSWORD_LENGTH):
            db_password += random.choice(PASSWORD_CHARS)

        cur.execute("""CREATE USER %s WITH NOSUPERUSER NOCREATEDB
                       NOCREATEROLE PASSWORD '%s'""" % (
                db_username, db_password))

    cur.close()
    #conn.close()

    return (created, db_host, db_name, db_username, db_password)


def lock_down_public_permissions():
    """
    Update PostgreSQL security settings to limit access by regular users to
    other users' databases, including our nrweb database.
    """

    _sql_as_superuser("""
REVOKE ALL ON DATABASE template1 FROM public;
REVOKE ALL ON SCHEMA public FROM public;
GRANT ALL ON SCHEMA public TO postgres;

REVOKE ALL ON DATABASE nrweb FROM public;
GRANT ALL ON DATABASE nrweb TO nrweb;
""")


def drop_database(database):
    """
    Drop the provided database.
    """
    print "Dropping database: %s" % database
    _sql_as_superuser("DROP DATABASE %s;" % database)


def drop_user(username):
    """
    Drop the provided user.
    """
    print "Dropping user: %s" % username
    _sql_as_superuser("DROP USER %s;" % username)
