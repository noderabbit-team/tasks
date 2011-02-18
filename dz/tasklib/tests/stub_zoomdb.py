from dz.tasklib.db import ZoomDatabase

class StubZoomDB(ZoomDatabase):
    def __init__(self):
        self.logs = []
        self.config_guesses = []

    def log(self, msg, logtype="i"):
        self.logs.append((msg, logtype))
        print "ZoomDB Log (%s): %s" % (logtype, msg)

    def add_config_guess(self, field, value, is_primary, basis):
        self.config_guesses.append(dict(
                field=field, value=value, is_primary=is_primary,
                basis=basis))
