import os
import random
import shutil
import string
import tarfile
import logging
from StringIO import StringIO

from mocker import MockerTestCase, ANY, MATCH

from boto.s3.connection import S3Connection
from os import path
from datetime import datetime

from dz.tasklib import taskconfig
from dz.tasklib import utils
from dz.tasklib import bundle
from dz.tasklib import check_repo

_missing = object()


class TasksTestCase(MockerTestCase):

    def setUp(self):
        self.customer_directory = self.makeDir()
        self.app_dir = self.makeDir(dirname=self.customer_directory)
        self.dir = self.makeDir(dirname=self.app_dir)

    def patch(self, ob, attr, value):
        old_value = getattr(ob, attr, _missing)
        setattr(ob, attr, value)

        def restore():
            if old_value is _missing:
                delattr(ob, attr)
            else:
                setattr(ob, attr, old_value)

        self.addCleanup(restore)

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
            os.path.basename(self.dir))

        s3 = S3Connection()
        bucket = s3.get_bucket(
            taskconfig.NR_BUNDLE_BUCKET)
        fh = open(self.makeFile(), "w")

        key = bucket.get_key(key_name)
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

        bundle_name = bundle.bundle_app('app')
        bundle_dir = path.join(self.dir, 'app', bundle_name)
        now = datetime.utcnow()
        # Made a datestamp'd bundle app directory
        self.assertTrue(bundle_name.startswith('bundle_app_%d' % now.year))
        self.assertTrue(path.isdir(bundle_dir))
        # Moved the app src/ directory into user-src
        listdir_fixture = os.listdir(path.join(src, 'src'))
        listdir_usersrc = os.listdir(path.join(bundle_dir, 'user-src'))

        listdir_fixture.sort()
        listdir_usersrc.sort()
        self.assertEqual(listdir_fixture, listdir_usersrc)
        # Added something to the path
        pth_file = path.join(utils.get_site_packages(bundle_dir),
                             taskconfig.NR_PTH_FILENAME)
        pth_content = open(pth_file, 'r').read()
        # Copied static files
        self.assertTrue(path.isdir(path.join(bundle_dir, 'static')))
        self.assertTrue(path.isdir(path.join(bundle_dir, 'foo')))
        # Moved the user's src directory
        self.assertEqual(pth_content, path.join(bundle_dir, 'user-src',
                                                'mysite_pth_add'))

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

        from dz.tasklib.db import ZoomDatabase

        class StubZoomDB(ZoomDatabase):
            def __init__(self):
                self.logs = []
                self.config_guesses = []

            def log(self, msg, logtype="i"):
                self.logs.append((msg, logtype))

            def add_config_guess(self, field, value, is_primary, basis):
                self.config_guesses.append(dict(
                        field=field, value=value, is_primary=is_primary,
                        basis=basis))

        zoomdb = StubZoomDB()
        app_id = "p001"
        src_url = "test://voo2do"

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
