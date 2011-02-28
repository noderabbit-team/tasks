from datetime import datetime
from sqlalchemy.ext.sqlsoup import SqlSoup
from dz.tasklib import utils
import traceback

class ZoomDatabase(object):
    """
    Database access layer for jobs to interact with djangozoom.
    """
    LOG_INFO = "i"
    LOG_ERROR = "e"
    LOG_STEP_BEGIN = "sb"
    LOG_STEP_END = "se"
    LOG_JOB_BEGIN = "jb"
    LOG_JOB_END = "je"

    VALID_LOG = (LOG_INFO, LOG_ERROR, LOG_STEP_BEGIN, LOG_STEP_END,
                 LOG_JOB_BEGIN, LOG_JOB_END)

    def __init__(self, db, job_id):
        self._db = db
        self._soup = SqlSoup(db)
        self._job_id = job_id

    def log(self, message, log_type=LOG_INFO):
        """Log a message against this job to the database for the UI.

        :param message: A string to log
        :param log_type: An ad hoc string denoting one of the log types.
                         Symbolic names are available on this class.
        """
        if not log_type in self.VALID_LOG:
            raise ValueError("Invalid log type %r" % log_type)

        self._soup.dz2_log.insert(
            job_id=self._job_id,
            logtype=log_type,
            message=message,
            timestamp=datetime.utcnow())
        self._soup.session.commit()

    def logsys(self, cmd, null_stdin=True):
        """Run the provided command (using utils.subproc) and log the
        results. Intended for use from tasks only.

        If cmd is a string, it will be run through a shell. Otherwise,
        it is assumed to be a list and not run in shell mode.

        If null_stdin is true (the default), pass in a pre-closed FH as the
        subprocess' stdin. That'll mean that when the subprocess tries to
        read from stdin, it will get an EOF and possibly fail. That sounds
        bad, but is actually what we want because we can't be there to type
        a password or answer some prompt, and it's better to fail rapidly
        with logging than to get hung waiting for a nonpresent user to type
        something.
        """

        print "* logsys running command: %r" % cmd

        stdout, stderr, p = utils.subproc(cmd, null_stdin=null_stdin)

        print "* logsys completed command: %r" % cmd
        print "* logsys STDOUT: %r" % stdout
        print "* logsys STDERR: %r" % stderr
        print "* logsys return code: %r" % p.returncode
        print "* logsys closed file handles."

        msg = "Executed: %r\n== STDOUT ==\n%r== STDERR ==\n%r\n== end ==" % (
            cmd, stdout, stderr)
        self.log(msg)

    def add_bundle(
        self, app_db_id, bundle_name, bundle_location, code_revision=None):
        """ Store the app's bundle location.

        :param app_db_id: The application/project database primary key.
        :param bundle_name: The name of the application bundle.
        :param bundle_location: The S3 location of the bundle.
        :param code_revision: The code revision the bundle was created from.
        """
        self._soup.dz2_appbundle.insert(
            project_id=app_db_id,
            bundle_name=bundle_name,
            bundle_location=bundle_location,
            code_revision=code_revision,
            creation_date=datetime.utcnow())
        self._soup.session.commit()

    def get_bundle(self, bundle_id):
        """Retrieve a bundle by database id.
        """
        return self._soup.dz2_appbundle.filter(
            self._soup.dz2_appbundle.id == bundle_id).one()
        self._soup.session.commit()

    def add_worker(
        self, app_db_id, bundle_id, instance_id, server_ip, server_port):
        """Record a worker added for an application.

        :param app_db_id: Application/Project database id
        :param bundle_id: The bundle database id, that the worker is running.
        :param instance_id: The ec2 instance id of the server.
        :param server_ip: The server ip address.
        :param server_port: The port on the server, the app is listening on.
        """
        self._soup.dz2_appserverdeployment.insert(
            project_id=app_db_id,
            bundle_id=bundle_id,
            server_instance_id=instance_id,
            server_ip=server_ip,
            server_port=server_port,
            creation_date=datetime.utcnow())
        self._soup.session.commit()

    def get_job(self):
        """Get the Job row."""
        if not hasattr(self, "_job"):
            self._job = self._soup.dz2_job.filter(
                self._soup.dz2_job.id == self._job_id).one()
        return self._job

    def add_config_guess(self, field, value, is_primary, basis):
        """Add a config guess for the user to review/confirm."""
        self._soup.dz2_configguess.insert(
            project_id=self.get_job().project_id,
            field=field,
            value=value,
            is_primary=is_primary,
            basis=basis)
        self._soup.session.commit()
