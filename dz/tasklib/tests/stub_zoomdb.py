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


class StubZoomDB(ZoomDatabase):
    def __init__(self):
        self.logs = []
        self.config_guesses = []
        self.project = MockProject()
        self.is_flushed = False

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
