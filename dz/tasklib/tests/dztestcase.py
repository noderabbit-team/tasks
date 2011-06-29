import sys
from functools import update_wrapper
from dz.tasklib import utils

from mocker import MockerTestCase

import os
import pwd
import time
import urllib
import httplib


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
        utils.chown_to_me(path)

    def _eventually_load(self, loader, desc, pagetext_fragment=None):
        load_attempts = 0

        while True:
            if load_attempts >= 10:
                self.fail("Could not load %s after %d attempts." % (
                        desc, load_attempts))
            try:
                pagetext = loader()
                if pagetext_fragment is None:
                    return pagetext

                self.assertTrue(pagetext_fragment in pagetext)
                break

            except Exception, e:
                load_attempts += 1
                print "[attempt %d] Couldn't load %s: %s" % (
                    load_attempts, desc, str(e))
                time.sleep(0.25)

    def check_can_eventually_load(self, url, pagetext_fragment=None):
        """
        Check that the given URL can be loaded, within a reasonable number
        of attempts, and that pagetext_fragment appears in the response.

        If pagetext_fragment is None, then instead of testing that the
        fragment exists in the page, we simply return the page contents once
        loaded. (We fail only if the page does not load within the allowed
        number of attempts.)
        """

        def loader():
            return urllib.urlopen(url).read()

        return self._eventually_load(loader, "URL %s" % url, pagetext_fragment)

    def check_can_eventually_load_custom(self, connection_host, urlpath,
                                         http_host, pagetext_fragment=None):
        def loader():
            conn = httplib.HTTPConnection(connection_host)
            conn.putrequest("GET", urlpath, skip_host=True)
            conn.putheader("Host", http_host)
            conn.endheaders()
            res = conn.getresponse()
            res_src = res.read()
            return res_src

        return self._eventually_load(
            loader,
            "URL %s from host %s on %s" % (urlpath,
                                           http_host,
                                           connection_host),
            pagetext_fragment)

    def get_fixture_path(self, *fixturepaths):
        """
        Get the absolute path the supplied fixture file/dir path.
        """
        here = os.path.abspath(os.path.split(__file__)[0])
        return os.path.join(here, "fixtures", *fixturepaths)


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
