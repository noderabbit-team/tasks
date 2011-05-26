import os
import random
import shutil
import string
import tarfile
import logging
from StringIO import StringIO

# from mocker import ANY, MATCH

from boto.s3.connection import S3Connection
from os import path
from datetime import datetime

from dz.tasklib import (taskconfig,
                        utils,
                        bundle,
                        check_repo,
                        bundle_storage,
                        bundle_storage_local,
                        userenv)
from dz.tasklib.tests.stub_zoomdb import StubZoomDB
from dz.tasklib.tests.dztestcase import DZTestCase, requires_internet


class TasksTestCase(DZTestCase):

    def setUp(self):
        self.customer_directory = self.makeDir()
        self.app_dir = self.makeDir(dirname=self.customer_directory)
        self.dir = self.makeDir(dirname=self.app_dir)

    def tearDown(self):
        # chown everything under self.customer_directory to me
        # so i can delete it
        self.chown_to_me(self.customer_directory)

    def capture_logging(self, log_name, level=logging.ERROR):
        output = StringIO()
        logger = logging.getLogger(log_name)
        logger.handlers = []
        handler = logging.StreamHandler(output)
        handler.setLevel(level)
        logger.addHandler(handler)
        logger.setLevel(level)
        return output

    def _prep_build_test_bundle(self, **kwargs):
        self.patch(taskconfig, "NR_CUSTOMER_DIR", self.dir)

        # install_requirements = self.mocker.replace(
        #     "dz.tasklib.utils.install_requirements")
        # install_requirements(["Django==1.2.5"], MATCH(os.path.isdir),
        #                      logsuffix="-django")
        # install_requirements(ANY, MATCH(os.path.isdir))
        # self.mocker.replay()

        here = path.abspath(path.split(__file__)[0])
        src = path.join(here, '../fixtures', 'app')
        dest = path.join(self.dir, 'app')

        if not os.path.isdir(dest):
            shutil.copytree(src, dest)
            utils.local('(cd %s; git init; git add -A; git commit -m test)' %
                        path.join(dest, 'src'))

        return bundle.bundle_app('app', **kwargs)

    def test_bundle_app_return_ue(self):
        """
        Test that bundle.bundle_app's return_ue parameter works.
        """
        (bundle_name, code_revision) = self._prep_build_test_bundle()
        (bundle_name, code_revision, ue) = self._prep_build_test_bundle(
            return_ue=True)

        self.assertTrue(isinstance(ue, userenv.UserEnv))

    @requires_internet
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

    @requires_internet
    def test_build_bundle(self):
        """
        Build a bundle!
        """
        (bundle_name, code_revision) = self._prep_build_test_bundle()
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
        here = path.abspath(path.split(__file__)[0])
        src = path.join(here, '../fixtures', 'app')
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

        ### UPDATE PERMS
        # This is just so we can look into all the files that just got created.
        self.chown_to_me(bundle_dir)

        # Added our settings file
        settings = path.join(bundle_dir, 'dz_settings.py')
        # Imported from their settings file
        self.assertTrue(path.isfile(settings))
        lines = [x.strip() for x in open(settings, 'r').readlines()]
        self.assertTrue('from mysite.settings import *' in lines)
        self.assertTrue("ADMIN_MEDIA_PREFIX = '%s'" % (
                taskconfig.DZ_ADMIN_MEDIA["url_path"]) in lines)

        # ensure we've predefined and redefined our settings
        settings_override_line = "DATABASE_ENGINE = 'postgresql_psycopg2'"
        import_line = "from mysite.settings import *"

        # check that things are in there before we try to check their
        # ordering
        self.assertTrue(settings_override_line in lines, lines)
        self.assertTrue(import_line in lines, lines)

        try:
            first_settings = lines.index(settings_override_line)
            first_import = lines.index(import_line, first_settings)
            last_settings = lines.index(settings_override_line, first_import)
        except ValueError:
            print "Couldn't find something I expected in dz_settings."
            raise

        self.assertTrue(first_settings < first_import < last_settings)

    def test_build_and_upload(self):
        """
        Test that I can do a build and then upload the result. This test that
        ownership settings are workable to get the bundle saved into storage
        even when built within a userenv.
        """
        (bundle_name, code_revision) = self._prep_build_test_bundle()

        bundle_storage_file = path.join(taskconfig.NR_CUSTOMER_DIR,
                                        "bundle_storage_local",
                                        bundle_name + ".tgz")

        self.assertFalse(path.isfile(bundle_storage_file))
        bundle_file_name = bundle.zip_and_upload_bundle(
            'app', bundle_name, bundle_storage_engine=bundle_storage_local)
        self.assertTrue(path.isfile(bundle_storage_file))
        bundle_storage_local.delete(bundle_file_name)
        self.assertFalse(path.isfile(bundle_storage_file))

    def test_build_and_upload_with_delete(self):
        """
        Test that I can pass delete_after_upload to
        bundle.zip_and_upload_bundle and have it delete the bundle directory
        after a successful upload.
        """
        (bundle_name, code_revision) = self._prep_build_test_bundle()
        bundle_dir = path.join(self.dir, 'app', bundle_name)
        self.assertTrue(path.isdir(bundle_dir))
        bundle_file_name = bundle.zip_and_upload_bundle(
            'app', bundle_name, bundle_storage_engine=bundle_storage_local)
        # still there
        self.assertTrue(path.isdir(bundle_dir))
        # delete uploaded bundle
        bundle_storage_local.delete(bundle_file_name)
        # still there
        self.assertTrue(path.isdir(bundle_dir))
        # ok now upload with delete
        bundle_file_name = bundle.zip_and_upload_bundle(
            'app', bundle_name, bundle_storage_engine=bundle_storage_local,
            delete_after_upload=True)
        # Now it's gone!
        self.assertFalse(path.isdir(bundle_dir))
        # delete uploaded bundle
        bundle_storage_local.delete(bundle_file_name)

    def test_check_repo(self):
        """
        Check repo and make guesses!
        """
        self.patch(taskconfig, "NR_CUSTOMER_DIR", self.dir)

        zoomdb = StubZoomDB()
        app_id = "p001"
        here = path.abspath(path.split(__file__)[0])
        tarball_path = path.join(here, '../fixtures', 'repo.tar.gz')
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

        self.assertEqual(len(zoomdb.config_guesses), 5)

        def has_one_guess(field, value):
            matches = [g for g in zoomdb.config_guesses
                       if g["field"] == field and g["value"] == value]

            return len(matches) == 1

        self.assertTrue(has_one_guess("additional_python_path_dirs",
                                      "version2\nversion2/voo2do"))

        self.assertTrue(has_one_guess(
            "requirements_file_names",
            "\n".join(["requirements.txt",
                       "version2/voo2do/requirements/base.txt"])))

    def test_delete_bundles(self):
        """
        Test the job to delete a specific bundle.
        """
        zoomdb = StubZoomDB()
        (bundle_name, code_revision) = self._prep_build_test_bundle()
        db_bundle = zoomdb.add_bundle(bundle_name, code_revision)

        bundle_storage_file = path.join(taskconfig.NR_CUSTOMER_DIR,
                                        "bundle_storage_local",
                                        bundle_name + ".tgz")

        bundle_file_name = bundle.zip_and_upload_bundle(
            'app', bundle_name, bundle_storage_engine=bundle_storage_local)
        self.assertTrue(path.isfile(bundle_storage_file))

        bundle.delete_bundles(zoomdb, "app", [db_bundle.id],
                              bundle_storage_engine=bundle_storage_local)

        self.assertFalse(path.isfile(bundle_storage_file))
