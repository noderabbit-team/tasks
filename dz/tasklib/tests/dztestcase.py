import sys
from functools import update_wrapper
from dz.tasklib import utils

from mocker import MockerTestCase

import os
import pwd


_missing = object()


class DZTestCase(MockerTestCase):
    """
    Base TestCase class for DjangoZoom tests. Put reusable test stuff in here.
    """

    def patch(self, ob, attr, value):
        """Patch a specific object attribute for the duration of a test."""
        old_value = getattr(ob, attr, _missing)
        setattr(ob, attr, value)

        def restore():
            if old_value is _missing:
                delattr(ob, attr)
            else:
                setattr(ob, attr, old_value)

        self.addCleanup(restore)

    def assertFileOwnedBy(self, filename, username, msg=None):
        """
        Assert that the owner of <filename> is <username>.
        """
        file_owner_name = pwd.getpwuid(os.stat(filename).st_uid).pw_name
        if not msg:
            msg = ("File %s should be owned by %r, but is actually owned by "
                   "%r.") % (filename,
                             username,
                             file_owner_name)
        self.assertEqual(file_owner_name, username, msg)

    def chown_to_me(self, path):
        username = pwd.getpwuid(os.geteuid()).pw_name
        utils.local_privileged(["project_chown", username, path])


def requires_internet(test_func):
    """
    Decorator that denotes a test requires internet connectivity to
    complete, and should not run in airplane mode (i.e. if the environment
    variable "AIRPLANE_MODE" is set to a true value.
    """
    def wrapper(*args, **kwargs):
        if os.environ.get("AIRPLANE_MODE"):
            sys.stderr.write("\n  (Skipping because AIRPLANE_MODE is set: "
                             "%s.%s)\n" % (test_func.__module__,
                                           test_func.__name__))
            return

        return test_func(*args, **kwargs)

    update_wrapper(wrapper, test_func)
    return wrapper
