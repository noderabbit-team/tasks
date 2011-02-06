import os
import sys
import shutil
import tempfile
import unittest
from os import path
from datetime import datetime

import taskconfig
import utils
from tasks import bundle


class TasksTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_build_bundle(self):
        """
        Build a bundle!
        """
        here = path.abspath(path.split(__file__)[0])
        src = path.join(here, 'fixtures', 'app')
        dest = path.join(self.dir, 'app')
        shutil.copytree(src, dest)

        bundle_name = bundle.bundle_app(self.dir, 'app')
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

    def tearDown(self):
        shutil.rmtree(self.dir)

