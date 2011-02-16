import sys
import shutil
import tempfile
import unittest
from os import path

from dz.tasklib import taskconfig
from dz.tasklib import utils


class UtilsTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_run(self):
        """
        Tests our small wrapper around fabric's `run`
        """
        cmd = 'echo "foo"'
        out = utils.local(cmd, capture=True)
        self.assertEqual(out, 'foo')

    def test_make_virtualenv(self):
        """
        Creating a virtualenv
        """
        utils.make_virtualenv(path.join(self.dir, 'vm'))
        self.assertTrue(path.exists(path.join(self.dir, 'vm', 'bin', 'python')))

    def test_install_requirements(self):
        """
        Tests that we can install pip requirements
        """
        utils.make_virtualenv(path.join(self.dir))
        utils.install_requirements(['importlib'], self.dir)
        fpath = path.join(self.dir, taskconfig.NR_PIP_REQUIREMENTS_FILENAME)
        self.assertTrue(path.exists(fpath))
        contents = open(fpath, 'r').read()
        self.assertEquals(contents, 'importlib')

    def test_add_to_pth(self):
        """
        Add a file to our pth file in site-packages
        """
        utils.make_virtualenv(self.dir)
        utils.add_to_pth(['/foo'], self.dir)
        pthfname = path.join(utils.get_site_packages(self.dir), taskconfig.NR_PTH_FILENAME)
        pthfile = open(pthfname, 'r')
        self.assertEqual('/foo', pthfile.read())

    def test_add_to_pth_relative(self):
        """
        Add relative paths to pth file
        """
        utils.make_virtualenv(self.dir)
        utils.add_to_pth(['foo', 'bar'], self.dir, relative=True)
        pthfname = path.join(utils.get_site_packages(self.dir), taskconfig.NR_PTH_FILENAME)
        contents = open(pthfname, 'r').read()
        self.assertTrue(path.join(self.dir, 'foo') in contents, contents)
        self.assertTrue(path.join(self.dir, 'bar') in contents, contents)

    def test_render_tpl_to_file(self):
        """
        Render a template to a file.
        """
        tpl_path = path.join(self.dir, 'tpl')
        content = utils.render_tpl_to_file('bundle/settings.py.tmpl',
                                           tpl_path,
                                           dz_settings='foo')
        read = open(tpl_path, 'r').read()
        self.assertEqual(content, read)
        self.assertTrue('foo' in read)

    def tearDown(self):
        shutil.rmtree(self.dir)

