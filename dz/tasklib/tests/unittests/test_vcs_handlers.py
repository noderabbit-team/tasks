from dz.tasklib.tests.dztestcase import (DZTestCase,
                                         requires_internet)
from dz.tasklib import vcs_handlers
import os


class VCSHandlersTestCase(DZTestCase):
    def test_init(self):
        self.assertTrue(len(vcs_handlers.REGISTERED_HANDLERS) > 0)
        for vcs_type in "git", "hg":
            self.assertTrue(vcs_type in vcs_handlers.REGISTERED_HANDLERS)

    def test_registration(self):
        class Dummy(vcs_handlers.BaseVCSHandler):
            vcs_type = "dummy"

        self.assertFalse("dummy" in vcs_handlers.REGISTERED_HANDLERS)
        vcs_handlers.register_handler(Dummy)
        self.assertTrue("dummy" in vcs_handlers.REGISTERED_HANDLERS)
        for handler in vcs_handlers.REGISTERED_HANDLERS.values():
            self.assertTrue(isinstance(handler, vcs_handlers.BaseVCSHandler),
                            type(handler))


class VCSHandlersRemoteTests(DZTestCase):
    def setUp(self):
        self.current_dir = os.getcwd()
        self.co_dir = self.makeDir()
        os.chdir(self.co_dir)
        super(VCSHandlersRemoteTests, self).setUp()

    def tearDown(self):
        os.chdir(self.current_dir)
        super(VCSHandlersRemoteTests, self).tearDown()

    def _test_with_remote(self, repo_type, repo_url):
        handler = vcs_handlers.get_handler(repo_type)
        logs = []

        def logger(msg):
            print "VCS HANDLER LOGGED: %s" % msg
            logs.append(msg)

        self.assertEqual(handler.canonicalize_url(
            handler.get_current_checkout_source_url()), None)
        handler.fresh_clone(repo_url, logger)
        self.assertEqual(handler.canonicalize_url(
            handler.get_current_checkout_source_url()),
                         handler.canonicalize_url(repo_url))
        handler.update_checkout(logger)

        revision_info = handler.get_revision_info(".")
        self.assertTrue(revision_info,
                        "Revision info expected; got %r" % revision_info)
        #print "GOT REV INFO: %r" % revision_info

    @requires_internet
    def test_remote_svn(self):
        return self._test_with_remote(
            "svn", "https://svn.github.com/shimon/djangotutorial.git")
    # was http://django-atompub.googlecode.com/svn/trunk/ but it turns
    # out github provides svn service conveniently

    @requires_internet
    def test_remote_hg_https(self):
        return self._test_with_remote(
            "hg", "https://bitbucket.org/shimon/djangotutorial")

    @requires_internet
    def test_remote_hg_ssh(self):
        return self._test_with_remote(
            "hg", "ssh://hg@bitbucket.org/shimon/djangotutorial")

    @requires_internet
    def test_remote_git_https(self):
        return self._test_with_remote(
            "git", "https://shimon@github.com/shimon/djangotutorial.git")

    @requires_internet
    def test_remote_git_ssh(self):
        return self._test_with_remote(
            "git", "git@github.com:shimon/djangotutorial.git")

    @requires_internet
    def test_remote_git_git_read_only(self):
        return self._test_with_remote(
            "git", "git://github.com/shimon/djangotutorial.git")
