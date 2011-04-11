from dz.tasklib.zoomdb import ZoomDatabase
from dz.tasklib import taskconfig

class MockProject(object):
    owner = 0
    project_id = 1
    source_code_url = ""
    title = ""
    django_version = ""
    database_type = ""
    base_python_package = ""
    django_settings_module = ""
    site_media = ""
    additional_python_path_dirs = ""
    db_host = ""
    db_name = ""
    db_username = ""
    db_password = ""


class MockBundle(object):
    def __init__(self, bundle_name="bundle_test_deploy_app_2011-fixture"):
        self.bundle_name = bundle_name
        MockBundle.count += 1
        self.id = MockBundle.count
MockBundle.count = 0


class MockWorker(object):
    def __init__(self, bundle_id, instance_id, server_ip, server_port):
        MockWorker.count += 1
        self.id = MockWorker.count
        self.bundle_id = bundle_id
        self.server_instance_id = instance_id
        self.server_ip = server_ip
        self.server_port = server_port
MockWorker.count = 0


class StubZoomDB(ZoomDatabase):
    def __init__(self):
        self.logs = []
        self.config_guesses = []
        self.project = MockProject()
        self.is_flushed = False
        self.bundles = []
        self.workers = []
        self.test_vhosts = []
        self._job_id = 1

    def flush(self):
        self.is_flushed = True

    def log(self, msg, logtype="i"):
        self.logs.append((msg, logtype))
        print "ZoomDB Log (%s): %s" % (logtype, msg)

    def add_config_guess(self, field, value, is_primary, basis):
        self.config_guesses.append(dict(
                field=field, value=value, is_primary=is_primary,
                basis=basis))

    def get_project(self):
        return self.project

    def get_project_id(self):
        return self.project.project_id

    def add_bundle(self, bundle_name, code_revision=None):
        self.bundles.append((bundle_name, code_revision))
        return MockBundle()

    def get_bundle(self, bundle_id):
        if len(self.bundles):
            return MockBundle(bundle_name=self.bundles[0][0])
        else:
            return MockBundle()

    def get_all_bundles(self):
        return self.bundles

    def add_worker(self, bundle_id, instance_id, server_ip, server_port):
        self.workers.append(MockWorker(
                bundle_id, instance_id, server_ip, server_port))

    def get_project_workers(self):
        return self.workers

    def search_workers(self, bundle_ids=None, active=True):
        return self.workers

    def get_project_virtual_hosts(self):
        """Use special identifiers for test vhost names so we don't conflict
        with hosts that may already exist on the test system."""
        canonical_vhost_name = \
            taskconfig.CANONICAL_VIRTUAL_HOST_FORMAT % (
            taskconfig.PROJECT_SYSID_FORMAT % self.get_project_id())

        return ["test-%s" % canonical_vhost_name] + self.test_vhosts
