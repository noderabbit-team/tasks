from datetime import datetime
from sqlalchemy.ext.sqlsoup import SqlSoup
from dz.tasklib import (utils,
                        taskconfig)


class ZoomDatabase(object):
    """
    Database access layer for jobs to interact with djangozoom.
    """
    LOG_INFO = "i"
    LOG_WARN = "w"
    LOG_ERROR = "e"
    LOG_STEP_BEGIN = "sb"
    LOG_STEP_END = "se"
    LOG_JOB_BEGIN = "jb"
    LOG_JOB_END = "je"

    VALID_LOG = (LOG_INFO, LOG_WARN, LOG_ERROR, LOG_STEP_BEGIN, LOG_STEP_END,
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

    def flush(self):
        """
        Flush any changes sqlsoup has accumulated (write updates to the DB).
        """
        self._soup.flush()

    def add_bundle(self, bundle_name, code_revision=None):
        """
        Store the app's bundle location (assuming this zoomdb's job has an
        associated project).

        :param bundle_name: The name of the application bundle.
        :param code_revision: The code revision the bundle was created from.
        """

        if code_revision is None:
            code_revision = ""

        CODE_REVISION_FIELD_LENGTH = 512
        if len(code_revision) > CODE_REVISION_FIELD_LENGTH:
            code_revision = (code_revision[0:(CODE_REVISION_FIELD_LENGTH - 3)]
                             + "...")

        bundle = self._soup.dz2_appbundle.insert(
            project_id=self.get_project_id(),
            bundle_name=bundle_name,
            code_revision=code_revision,
            creation_date=datetime.utcnow())
        self._soup.session.commit()
        return bundle

    def get_bundle(self, bundle_id):
        """Retrieve a bundle by database id.
        """
        return self._soup.dz2_appbundle.filter(
            self._soup.dz2_appbundle.id == bundle_id).one()
        self._soup.session.commit()

    def get_all_bundles(self):
        """Get a list of all app_bundles for the current job's project."""
        return list(self._soup.dz2_appbundle.filter(
                self._soup.dz2_appbundle.project_id == self.get_project_id()))

    def add_worker(
        self, bundle_id, instance_id, server_ip, server_port):
        """Record a worker added for an application.

        :param app_db_id: Application/Project database id
        :param bundle_id: The bundle database id, that the worker is running.
        :param instance_id: The ec2 instance id of the server.
        :param server_ip: The server ip address.
        :param server_port: The port on the server, the app is listening on.
        """
        worker = self._soup.dz2_appserverdeployment.insert(
            project_id=self.get_project_id(),
            bundle_id=bundle_id,
            server_instance_id=instance_id,
            server_ip=server_ip,
            server_port=server_port,
            creation_date=datetime.utcnow())
        self._soup.session.commit()
        return worker

    def search_workers(self, bundle_ids=None, active=True):
        """
        Get workers in this job's project matching the supplied criteria.

        :param bundle_ids: Bundle DB ids to match; if None, any bundles in
                             the app are included.
        :param active: If True (the default, limit results to currently
                       active workers.
        """
        asd = self._soup.dz2_appserverdeployment
        #bundle = self._soup.dz2_appbundle
        qs = asd.filter(asd.project_id == self.get_project_id())

# # same thing, but spelled out entirely explicitly
# # including the association table.
# session.query(Article).join(
#     (article_keywords,
#     Articles.id==article_keywords.c.article_id),
#     (Keyword, Keyword.id==article_keywords.c.keyword_id)
#     )

        # if bundle_names:
        #     qs = qs.join((bundle,
        #                   asd.bundle_id == bundle.id)).filter(
        #         bundle.bundle_name._in(bundle_names))
        # SR 3/4/11: for some reason the above doesn't work. Fuck it,
        # i'll filter in Python. Sorry.

        if active is not None:
            if active:
                qs = qs.filter(asd.deactivation_date == None)
            else:
                qs = qs.filter(asd.deactivation_date != None)

        result = list(qs)

        if bundle_ids:
            result = filter(lambda b: b.bundle_id in bundle_ids, result)

        return result

    def get_project_workers(self):
        """Get all AppServerDeployments for this job's project.
        Note that this includes inactive deployments."""
        return list(self._soup.dz2_appserverdeployment.filter(
                self._soup.dz2_appserverdeployment.project_id ==
                self.get_project_id()))

    def get_project_worker_by_id(self, deployment_id):
        """Get an AppServerDeployment record matching the given id."""
        return self._soup.dz2_appserverdeployment.filter(
            self._soup.dz2_appserverdeployment.project_id ==
            self.get_project_id()).filter(
            self._soup.dz2_appserverdeployment.id ==
            deployment_id).one()

    def get_job(self):
        """Get the Job row."""
        if not hasattr(self, "_job"):
            self._job = self._soup.dz2_job.filter(
                self._soup.dz2_job.id == self._job_id).one()
        return self._job

    def get_job_id(self):
        """Get my job ID."""
        return self._job_id

    def get_project(self):
        """Get the project row."""
        if not hasattr(self, "_project"):
            j = self.get_job()
            self._project = self._soup.dz2_project.filter(
                self._soup.dz2_project.id == j.project_id).one()
        return self._project

    def get_project_id(self):
        """Get the project_id associated with this zoomdb's job."""
        return self.get_job().project_id

    def add_config_guess(self, field, value, is_primary, basis):
        """Add a config guess for the user to review/confirm."""
        self._soup.dz2_configguess.insert(
            project_id=self.get_project_id(),
            field=field,
            value=value,
            is_primary=is_primary,
            basis=basis)
        self._soup.session.commit()

    def get_project_virtual_hosts(self):
        """Get virtual hostname strings for this project. Always includes at
        least the one canonical vhost name."""
        canonical_vhost_name = \
            taskconfig.CANONICAL_VIRTUAL_HOST_FORMAT % (
            taskconfig.PROJECT_SYSID_FORMAT % self.get_project_id())

        result = [canonical_vhost_name]

        project = self.get_project()
        if project.hostname_slug:
            result.append("%s.%s" % (project.hostname_slug,
                                     taskconfig.CUSTOMER_DNS_ROOT_DOMAIN))

        # query the DB for matching VirtualHostname records
        vhosts = self._soup.dz2_virtualhostname.filter(
            self._soup.dz2_virtualhostname.project_id ==
            self.get_project_id())

        for vh in vhosts:
            if vh.is_wildcard:
                result.append("*.%s" % vh.hostname)
            result.append(vh.hostname)

        return result

    def mark_postgis_enabled(self):
        project = self.get_project()
        project.database_type = "postgresql-gis"
        self._soup.session.commit()
