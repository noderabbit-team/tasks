import re
import shutil
import tempfile
from os import path

from dz.tasklib import taskconfig
from dz.tasklib import utils
from dz.tasklib.tests.dztestcase import DZTestCase


class UtilsTestCase(DZTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        here = path.abspath(path.split(__file__)[0])
        self.fixtures_dir = path.join(here, '../fixtures')
        self.test_req_tarball = path.join(self.fixtures_dir,
                                          "Django-1.2.5.tar.gz")

    def test_run(self):
        """
        Tests our small wrapper around fabric's `run`
        """
        cmd = 'echo "foo"'
        out = utils.local(cmd, capture=True)
        self.assertEqual(out, 'foo')

    def test_subproc(self):
        """
        Test our subproc() function, a convenience wrapper around
        subprocess.Popen.
        """
        stdout, stderr, p = utils.subproc("echo foo && false")
        self.assertEqual(stdout, "foo\n")
        self.assertEqual(stderr, "")
        self.assertEqual(p.returncode, 1)

    def test_subproc_null_stdin(self):
        """
        Test our subproc() function's null_stdin functionality using the `cat`
        command. Without a closed filehandle, this would wait indefinitely.
        """
        stdout, stderr, p = utils.subproc("cat")
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(p.returncode, 0)

    def test_subproc_passing_stdin(self):
        """
        Test our subproc() function's ability to take a provided string as
        stdin.
        """
        stdout, stderr, p = utils.subproc("cat", stdin_string="hello world")
        self.assertEqual(stdout, "hello world")
        self.assertEqual(stderr, "")
        self.assertEqual(p.returncode, 0)

    def test_make_virtualenv(self):
        """
        Creating a virtualenv
        """
        utils.make_virtualenv(path.join(self.dir, 'vm'))
        self.assertTrue(path.exists(path.join(
                    self.dir, 'vm', 'bin', 'python')))

    def test_install_requirements(self):
        """
        Tests that we can install pip requirements
        """
        utils.make_virtualenv(path.join(self.dir))
        utils.install_requirements([self.test_req_tarball], self.dir)
        fpath = path.join(self.dir, taskconfig.NR_PIP_REQUIREMENTS_FILENAME)
        logpath = path.join(self.dir, "dz-pip.log")
        self.assertTrue(path.exists(fpath))
        contents = open(fpath, 'r').read()
        self.assertEquals(contents.strip(), self.test_req_tarball)

        self.assertTrue(path.exists(logpath))
        log_contents = open(logpath, 'r').read()
        self.assertTrue("Successfully installed Django\n" in log_contents)

    def test_install_requirements_failure(self):
        """
        Tests pip failures don't cause the whole process to exit.
        """
        utils.make_virtualenv(path.join(self.dir))

        try:
            utils.install_requirements(['BULLSHIT_REQ'], self.dir)
        except utils.ExternalServiceException, e:
            self.assertTrue(("Could not find any downloads that satisfy "
                             "the requirement BULLSHIT-REQ") in e.message)
        else:
            self.fail("ExternalServiceException not raised")

    def test_install_multiple_requirements(self):
        """
        Tests that multiple requirements are properly installed and not
        concatenated onto one gigantic line.
        """
        utils.make_virtualenv(path.join(self.dir))
        utils.install_requirements([self.test_req_tarball,
                                    self.test_req_tarball,
                                    ], self.dir)
        fpath = path.join(self.dir, taskconfig.NR_PIP_REQUIREMENTS_FILENAME)
        logpath = path.join(self.dir, "dz-pip.log")
        self.assertTrue(path.exists(fpath))
        contents = open(fpath, 'r').read()
        self.assertEquals(contents.strip(), "\n".join([self.test_req_tarball,
                                                       self.test_req_tarball]))

        self.assertTrue(path.exists(logpath))
        log_contents = open(logpath, 'r').read()
        self.assertTrue("Successfully installed Django\n" in log_contents)

    def test_add_to_pth(self):
        """
        Add a file to our pth file in site-packages
        """
        utils.make_virtualenv(self.dir)
        utils.add_to_pth(['/foo'], self.dir)
        pthfname = path.join(utils.get_site_packages(self.dir),
                             taskconfig.NR_PTH_FILENAME)
        pthfile = open(pthfname, 'r')
        self.assertEqual('/foo', pthfile.read().strip())

    def test_add_to_pth_relative(self):
        """
        Add relative paths to pth file
        """
        utils.make_virtualenv(self.dir)
        utils.add_to_pth(['foo', 'bar'], self.dir, relative=True)
        pthfname = path.join(utils.get_site_packages(self.dir),
                             taskconfig.NR_PTH_FILENAME)
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

    def test_local_privileged(self):
        """Runs a privileged (setuid) external program.
        """
        result = utils.local_privileged(["whoami"])
        self.assertEqual("root\n", result)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_node_metadata(self):
        instance_id = utils.node_meta("instance_id")
        node_name = utils.node_meta("name")
        node_role = utils.node_meta("role")

        self.assertEqual(instance_id, "localhost")
        self.assertEqual(node_name, "localhost")
        self.assertEqual(node_role, "localhost")

        here = path.abspath(path.split(__file__)[0])
        test_fixture_meta = path.join(here, '../fixtures', 'node_meta')
        self.patch(taskconfig, "NODE_META_DATA_DIR", test_fixture_meta)

        self.assertEqual(utils.node_meta("instance_id"), "i-12345")
        self.assertEqual(utils.node_meta("name"), "myname")
        self.assertEqual(utils.node_meta("role"), "myrole")

    def test_get_internal_ip(self):
        """
        Test getting this computer's "internal" IP address.
        """
        self.assertTrue(utils.get_internal_ip() in ["127.0.0.1", "127.0.1.1"])
        self.assertTrue("\n" not in utils.get_internal_ip())
        # no crazy comcast dns masking html garbage, plz
        self.assertTrue("<" not in utils.get_internal_ip())

    def test_parse_zoombuild(self):
        here = path.abspath(path.split(__file__)[0])
        test_fixture_cfg = path.join(here, '../fixtures',
                                     'app', 'zoombuild.cfg')

        result = utils.parse_zoombuild(test_fixture_cfg)

        self.assertEqual(result["base_python_package"], "mysite")

    def test_parse_site_media_map(self):
        here = path.abspath(path.split(__file__)[0])
        test_fixture_cfg = path.join(here, '../fixtures',
                                     'app', 'zoombuild.cfg')
        zcfg = utils.parse_zoombuild(test_fixture_cfg)

        input_text = zcfg["site_media_map"]

        self.assertEqual(len(input_text.splitlines()), 2)
        self.assertTrue("static static" in input_text)
        self.assertTrue("foo {SITE_PACKAGES}/foo" in input_text)

        smm = utils.parse_site_media_map(input_text)
        self.assertTrue(isinstance(smm, dict))

        # each url path should start and end with a single slash
        for url_path in smm.keys():
            self.assertTrue(url_path.startswith("/"))
            self.assertTrue(url_path.endswith("/"))
            self.assertFalse(url_path.startswith("//"))
            self.assertFalse(url_path.endswith("//"))

        self.assertEqual(smm["/foo/"], "{SITE_PACKAGES}/foo")
        self.assertEqual(smm["/static/"], "static")
        self.assertEqual(len(smm), 2)

    def test_assemble_requirements(self):
        req_lines = utils.assemble_requirements()
        self.assertEqual(len(req_lines), 0)

        with self.assertRaises(AssertionError):
            # should crash if no basedir specified
            utils.assemble_requirements(files=["foo"])

        req_fixtures_dir = path.join(self.fixtures_dir, 'requirements')
        req_files = ["launchpad.txt", "project.txt"]
        req_lines = utils.assemble_requirements(
            basedir=req_fixtures_dir,
            files=req_files,
            lines=["somepkga", "somepkgb"])

        self.assertTrue("somepkga" in req_lines)
        self.assertTrue("somepkgb" in req_lines)
        # from project.txt:
        self.assertTrue("simplejson==2.1.1" in req_lines)
        # from base.txt:
        self.assertTrue("django-timezones==0.2.dev1" in req_lines)

        # test that a blank line yields no requirements
        self.assertEqual(len(utils.assemble_requirements(lines=[""])), 0)

        # test that invalid syntax raises an error
        with self.assertRaises(utils.ProjectConfigurationException):
            utils.assemble_requirements(lines=["<>"])

        # now test that duplicate requirements raise an error
        with self.assertRaises(utils.ProjectConfigurationException):
            utils.assemble_requirements(
            basedir=req_fixtures_dir,
            files=req_files,
            lines=["Django==0.96"])

        # now test that passing an "ignore" key prevents matching requirements
        # from entering the result. And also that it's case sensitive!
        req_lines = utils.assemble_requirements(
            basedir=req_fixtures_dir,
            files=req_files,
            ignore_keys=["DJANGO"])
        is_django = re.compile(r"^django\b", re.IGNORECASE)
        for line in req_lines:
            # have to do some special crap to avoid matching
            # django-debug-toolbar etc.
            self.assertFalse(
                is_django.match(line.replace("django-", "django_")),
                "Seems like django is in here: %s" % line)

        # and test we're not ignoring too much
        req_lines_unignored = utils.assemble_requirements(
            basedir=req_fixtures_dir,
            files=req_files,
            ignore_keys=None)
        self.assertEqual(len(req_lines) + 1, len(req_lines_unignored))

        # test that pointing at a nonexistent file raises a
        # ProjectConfigurationException
        with self.assertRaises(utils.ProjectConfigurationException):
            utils.assemble_requirements(
                basedir=req_fixtures_dir,
                files=['notafile'])

    def test_assemble_requirements_tricky(self):
        """
        Test assembling "tricky" requirements line:
        - URLs to tarballs (#65)
        - source eggs
        - --extra-index-url (#64)
        - etc.....
        """
        req_fixtures_dir = path.join(self.fixtures_dir, 'requirements')
        tricky_reqs = path.join(req_fixtures_dir, "tricky.txt")

        req_lines = utils.assemble_requirements(files=[tricky_reqs],
                                                basedir=req_fixtures_dir)

        lines_to_check = [
            "-e git+git://github.com/natea/feincms.git#egg=feincms",
            ("http://github.com/acdha/django-sugar/tarball/master"
             "#egg=django-sugar"),
            "--extra-index-url=http://dist.pinaxproject.com/dev/"]

        for line in lines_to_check:
            self.assertTrue(line in req_lines)

        self.assertTrue(len(lines_to_check) == len(req_lines))
