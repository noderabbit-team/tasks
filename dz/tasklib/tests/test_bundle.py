import os
import random
import shutil
import string
import tarfile
import logging
from StringIO import StringIO

from mocker import ANY, MATCH

from boto.s3.connection import S3Connection
from os import path
from datetime import datetime

from dz.tasklib import (taskconfig,
                        utils,
                        bundle,
                        check_repo,
                        bundle_storage)
from dz.tasklib.tests.stub_zoomdb import StubZoomDB
from dz.tasklib.tests.dztestcase import DZTestCase


class TasksTestCase(DZTestCase):

    def setUp(self):
        self.customer_directory = self.makeDir()
        self.app_dir = self.makeDir(dirname=self.customer_directory)
        self.dir = self.makeDir(dirname=self.app_dir)

    def capture_logging(self, log_name, level=logging.ERROR):
        output = StringIO()
        logger = logging.getLogger(log_name)
        logger.handlers = []
        handler = logging.StreamHandler(output)
        handler.setLevel(level)
        logger.addHandler(handler)
        logger.setLevel(level)
        return output

    def test_upload_bundle(self):
        """Archive and upload a bundle."""
        self.capture_logging("boto")
        self.patch(taskconfig, "NR_CUSTOMER_DIR", self.customer_directory)

        # add some random files and directories
        for i in range(5):
            self.makeDir(dirname=self.dir)

        for i in range(20):
            dirname = os.path.join(self.dir,
                                   random.choice(os.listdir(self.dir)))
            self.makeFile(
                content="".join(random.sample(string.printable, 99)),
                dirname=dirname)

        key_name = bundle.zip_and_upload_bundle(
            os.path.basename(self.app_dir),
            os.path.basename(self.dir),
            bundle_storage_engine=bundle_storage)

        s3 = S3Connection()
        bucket = s3.get_bucket(
            taskconfig.NR_BUNDLE_BUCKET)
        fh = open(self.makeFile(), "w")

        key = bucket.get_key(key_name)

        self.assertTrue(key is not None)

        key.get_file(fh)
        key.delete()
        fh.flush()

        tar = tarfile.TarFile.gzopen(fh.name)
        names = tar.getnames()
        entries = []
        for root, dirs, files in os.walk(self.app_dir):
            for f in files:
                entries.append(os.path.join(root, f)[len(self.app_dir) + 1:])
            for d in dirs:
                entries.append(os.path.join(root, d)[len(self.app_dir) + 1:])

        names.sort()
        entries.sort()
        self.assertEqual(names, entries)

    def test_build_bundle(self):
        """
        Build a bundle!
        """
        self.patch(taskconfig, "NR_CUSTOMER_DIR", self.dir)

        install_requirements = self.mocker.replace(
            "dz.tasklib.utils.install_requirements")
        install_requirements(ANY, MATCH(os.path.isdir))
        self.mocker.replay()

        here = path.abspath(path.split(__file__)[0])
        src = path.join(here, 'fixtures', 'app')
        dest = path.join(self.dir, 'app')
        shutil.copytree(src, dest)
        utils.local('(cd %s; git init; git add -A; git commit -m test)' %
                    path.join(dest, 'src'))

        (bundle_name, code_revision) = bundle.bundle_app('app')
        bundle_dir = path.join(self.dir, 'app', bundle_name)
        now = datetime.utcnow()
        # Made a datestamp'd bundle app directory
        self.assertTrue(bundle_name.startswith('bundle_app_%d' % now.year))
        self.assertTrue(code_revision.startswith("commit "))
        self.assertTrue(path.isdir(bundle_dir))
        self.assertTrue(path.isfile(path.join(bundle_dir, "zoombuild.cfg")))
        self.assertTrue(path.isdir(path.join(bundle_dir, "user-src")))

        # test the user-repo link is right
        self.assertTrue(path.islink(path.join(bundle_dir, "user-repo")))
        # the app fixture has a base_python_package of mysite, so:
        self.assertFalse(path.isfile(path.join(bundle_dir,
                                               "user-src",
                                               "urls.py")))
        self.assertTrue(path.isfile(path.join(bundle_dir,
                                              "user-src",
                                              "mysite",
                                              "urls.py")))
        self.assertTrue(path.isfile(path.join(bundle_dir,
                                              "user-repo",
                                              "urls.py")))

        # don't include the python executable
        self.assertFalse(path.isfile(path.join(bundle_dir, "bin", "python")))

        # Moved the app src/ directory into user-src, respecting base package
        listdir_fixture = os.listdir(path.join(src, 'src'))
        # except special ignored files:
        if ".git" in listdir_fixture:
            listdir_fixture.remove(".git")
        base_package_as_path = "mysite"
        user_src_base_dir = path.join(bundle_dir, 'user-src',
                                      base_package_as_path)
        # ensure base_python_path is represented
        self.assertTrue(path.isdir(user_src_base_dir))
        listdir_usersrc = os.listdir(user_src_base_dir)

        listdir_fixture.sort()
        listdir_usersrc.sort()
        self.assertEqual(listdir_fixture, listdir_usersrc)
        # Added something to the path
        pth_file = path.join(utils.get_site_packages(bundle_dir),
                             taskconfig.NR_PTH_FILENAME)
        pth_contents = [pthline.strip() for pthline in \
                            open(pth_file, 'r').readlines()]
        # Copied dirs
        self.assertTrue(path.isdir(path.join(user_src_base_dir, 'polls')))
        self.assertTrue(path.isdir(path.join(user_src_base_dir, 'templates')))
        # Ensure .pth file content looks right
        self.assertTrue(path.join(user_src_base_dir, 'mysite_pth_add') in \
                            pth_contents)
        self.assertTrue(path.join(bundle_dir, 'user-src') in pth_contents)
        self.assertTrue(user_src_base_dir in pth_contents)
        self.assertEqual(len(pth_contents), 3)

        # Added our settings file
        settings = path.join(bundle_dir, 'dz_settings.py')
        # Imported from their settings file
        self.assertTrue(path.isfile(settings))
        line = open(settings, 'r').readline()
        self.assertTrue('mysite.settings' in line)

    def test_check_repo(self):
        """
        Check repo and make guesses!
        """
        self.patch(taskconfig, "NR_CUSTOMER_DIR", self.dir)

        zoomdb = StubZoomDB()
        app_id = "p001"
        here = path.abspath(path.split(__file__)[0])
        tarball_path = path.join(here, 'fixtures', 'repo.tar.gz')
        tmp_repo_dir = self.makeDir()
        utils.local("tar xvzf %s -C %s" % (tarball_path, tmp_repo_dir))
        src_url = path.join(tmp_repo_dir, "repo")
        check_repo.check_repo(zoomdb, app_id, src_url)

        src_dir = path.join(self.dir, app_id, "src")

        self.assertTrue(path.isdir(src_dir),
                        "src dir does not exist")

        self.assertTrue(path.isdir(path.join(src_dir,
                                             ".git")),
                        "no .git dir inside src dir")

        self.assertEqual(len(zoomdb.config_guesses), 4)

        def is_one_expected_guess(g):
            return (g["field"] == "additional_python_path_dirs"
                    and g["value"] == "version2\nversion2/voo2do")

        self.assertEqual(len(filter(is_one_expected_guess,
                                    zoomdb.config_guesses)), 1)
