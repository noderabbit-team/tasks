"""
Manage databases for customer projects in our shared PostgreSQL cluster.
See: http://wiki.postgresql.org/wiki/Shared_Database_Hosting
"""

from dz.tasklib import (taskconfig,
                        utils)

import psycopg2
import random
import string

PASSWORD_CHARS = list(string.digits + string.ascii_letters)
PASSWORD_LENGTH = 30


class DatabaseInfo(dict):
    """
    Class to hold database connection information. It's a dict subclass, so
    any serialization method should work OK.
    """
    def __init__(self, host, db_name, username, password=None,
                 just_created=False):
        self['host'] = host
        self['db_name'] = db_name
        self['username'] = username
        self['password'] = password
        self['just_created'] = just_created

    @property
    def host(self):
        return self['host']

    @property
    def db_name(self):
        return self['db_name']

    @property
    def username(self):
        return self['username']

    @property
    def password(self):
        return self['password']

    @property
    def just_created(self):
        return self['just_created']

    def __str__(self):
        return "Database info: %suser=%s password=%s dbname=%s host=%s" % (
            "newly created " if self.just_created else "",
            self.username, self.password, self.db_name, self.host)


def _get_conn():
    """
    Get a database connection, using the existing one if exists.

    TODO: clean this up so that the connection can get closed when we're
    done with it. Otherwise the connection to template1 stays open and
    prevents the creation of any additional databases!
    """
    if not(hasattr(_get_conn, "_conn")) or _get_conn._conn.closed:
        conn_string = ("dbname=%(initial_db)s user=%(username)s" %
                       taskconfig.DATABASE_SUPERUSER)

        print "DB Connection: %s" % conn_string

        if "password" in taskconfig.DATABASE_SUPERUSER:
            conn_string += (" password=%(password)s" %
                            taskconfig.DATABASE_SUPERUSER)

        _get_conn._conn = psycopg2.connect(conn_string)
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
    db_host = utils.get_internal_ip()
    db_name = app_id
    db_username = app_id
    db_password = None
    created = False

    (cur, conn) = _get_cur_conn_as_superuser()

    try:
        cur.execute("CREATE DATABASE %s" % db_name)

    except psycopg2.OperationalError, e:
        # database cannot be created, this is a problem. raise it.
        raise e

    except psycopg2.ProgrammingError, e:
        # database already exists, not a problem.
        print e

    else:
        created = True
        db_password = ""
        for _ in xrange(PASSWORD_LENGTH):
            db_password += random.choice(PASSWORD_CHARS)

        cur.execute("""CREATE USER %s WITH NOSUPERUSER NOCREATEDB
                       NOCREATEROLE PASSWORD '%s';
                    """ % (
                db_username, db_password))

    cur.close()
    #conn.close() #### TODO #### Need to actually call this. Otherwise
    # the connection sits around, and no new databases can be created
    # because the template1 connection remains open! Then you get:
    #
    # OperationalError: source database "template1" is being accessed by
    # other users
    #
    # This doesn't happen in testing because this module goes out of scope
    # but in production the connection just sits in celery! Maybe we should
    # use some sort of proper connection pool, but just disconnecting would
    # be a good start. :)

    dbi = DatabaseInfo(host=db_host,
                       db_name=db_name,
                       username=db_username,
                       password=db_password,
                       just_created=created)
    return dbi


def lock_down_public_permissions():
    """
    Update PostgreSQL security settings to limit access by regular users to
    other users' databases, including our nrweb database.
    """

    _sql_as_superuser("\n".join([
                "REVOKE ALL ON DATABASE template1 FROM public;",

                "GRANT ALL ON SCHEMA public TO PUBLIC;", 
                # actually we want each user to be able to create tables in
                # the public schema for any DB they can connect to.

                #"REVOKE ALL ON SCHEMA public FROM public;",
                #"GRANT ALL ON SCHEMA public TO postgres;",

                "REVOKE ALL ON DATABASE nrweb FROM public;",
                "GRANT ALL ON DATABASE nrweb TO nrweb;",
                ]))


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
