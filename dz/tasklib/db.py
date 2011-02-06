from datetime import datetime
from sqlalchemy.ext.sqlsoup import SqlSoup


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
