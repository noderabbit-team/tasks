from dz.tasklib.zoomdb import ZoomDatabase


class MockProject(object):
    owner = 0
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
    def __init__(self):
        MockBundle.count += 1
        self.id = MockBundle.count
MockBundle.count = 0


class StubZoomDB(ZoomDatabase):
    def __init__(self):
        self.logs = []
        self.config_guesses = []
        self.project = MockProject()
        self.is_flushed = False
        self.bundles = []
        self.workers = []

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

    def add_bundle(self, bundle_name, code_revision=None):
        self.bundles.append((bundle_name, code_revision))
        return MockBundle()

    def get_all_bundles(self):
        return self.bundles

    def add_worker(self, bundle_id, instance_id, server_ip, server_port):
        self.workers.append((bundle_id, instance_id, server_ip, server_port))

    def get_project_workers(self):
        return self.workers
