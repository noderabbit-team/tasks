from fabric.api import local as fab_local
from fabric.state import connections
from jinja2 import PackageLoader, Environment
from StringIO import StringIO  # important: cStringIO causes weird parse errors
import os
import pwd
import socket
import subprocess
import sys
import ConfigParser

import taskconfig

from pip.req import parse_requirements, InstallRequirement, RequirementSet
from pip.exceptions import InstallationError
from pip.locations import build_prefix, src_prefix

# some functions have been moved to utils_essentials in order to allow them
# to be used with no dependencies outside stdlib.
from utils_essentials import (ExternalServiceException,
                              subproc,
                              local_privileged)

tpl_env = Environment(loader=PackageLoader('dz.tasklib'))


class InfrastructureException(Exception):
    """
    Exception indicating a problem in DjangoZoom's infrastructure, probably
    preventing the user from completing a successful deployment. :(
    """


class ProjectConfigurationException(Exception):
    """
    Exception indicating a problem resulting from misconfiguration by the
    end user.
    """


def local(command, capture=True):
    """
    Run a command locally.

    :param command: The command to run
    :param capture: Return the command's output?
    """
    out = fab_local(command, capture)

    for key in connections.keys():
        connections[key].close()
        del connections[key]

    return out


def get_site_packages(vpath):
    """
    Get the path to ``site-packages`` directory for the given virtualenv

    :param vpath: absolute path to virtualenv root
    """
    major, minor = sys.version_info[0:2]
    return os.path.join(vpath, 'lib', 'python%d.%d' % (major, minor),
                        'site-packages')


def make_virtualenv(path):
    """
    Generate a virtual env

    NOTE: installing distribute requires access to PyPI! That sucks.

    :param path: The full path to the virtualenv directory
    """
    # specifying the system python means it's OK if we're running inside a
    # virtualenv ourselves.
    local("virtualenv  --python=/usr/bin/python %s" % path)


def install_requirements(reqs, path, logsuffix=None, env=None):
    """
    Given a ``path`` to a virtualenv, install the given ``reqs``.

    :param reqs: A list of pip requirements
    :param path: A path to a virtualenv
    :param env: A UserEnv object
    """
    fname = os.path.join(path, taskconfig.NR_PIP_REQUIREMENTS_FILENAME)
    if env:
        reqfile = env.open(fname, "w")
    else:
        reqfile = open(fname, "w")

    reqfile.writelines([r.strip() + "\n" for r in reqs])
    reqfile.close()
    pip = os.path.join(path, 'bin', 'pip')

    logfile = os.path.join(path, "dz-pip%s.log" % (logsuffix or ""))

    # run pip, store log in the target environment for debugging
    # see http://jacobian.org/writing/when-pypi-goes-down/ for info about PyPi mirrors
    #  --use-mirrors  ## removed because the ubuntu pip doesn't support this
    # test to see if --download-cache is supported in the version of pip that we have installed
    #output, stderr, p = subproc("%s install --download-cache=~/.pip-cache --log=%s -r %s" % (
    #        pip, logfile, fname))

    pipcmd = [pip, "install", "--log=%s" % logfile, "-r", fname]

    # USERENV NEEDS TO INCLUDE /cust/appid dir
    if env:
        output, stderr, p = env.subproc(pipcmd)
    else:
        output, stderr, p = subproc(pipcmd)

    if p.returncode != 0:
        raise ExternalServiceException((
                "Error attempting to install requirements %r. "
                "Pip output:\n %s\n%s") % (reqs, output, stderr))

    print "=== output from pip ==="
    print output
    print "=== end of output from pip ==="


def assemble_requirements(lines=None, files=None, basedir=None,
                          ignore_keys=None, env=None):
    """
    Assemble a list of requirements lines based on the provided files
    (relative to the provided base directory) and the provided lines.
    """
    args_ok = not(files) or basedir

    assert args_ok, ("If the files parameter is provided to "
                     "assemble_requirements, the basedir "
                     "parameter must also be provided.")

    if env:
        # have pip's code pull from within the env
        env.monkeypatch_pip_util_get_file_content()

    class FakePipOptions(object):
        skip_requirements_regex = None
        default_vcs = None

    class FakePipFinder(object):
        def __init__(self):
            self.DEFAULT_INDEXES = object()
            self.find_links = []
            self.index_urls = [] # [self.DEFAULT_INDEXES]
            # TODO: if self.DEFAULT_INDEXES is not in index_urls,
            # treat the first entry as --index-url instead of --extra-index-url
    finder = FakePipFinder()

    monolithic_reqs = []

    for filename in (files or []):
        try:
            filepath = os.path.join(basedir, filename)
            file_reqs = list(parse_requirements(filepath,
                                                comes_from=filename,
                                                finder=finder,
                                                options=FakePipOptions()))
        except IOError, e:
            raise ProjectConfigurationException(
                "Couldn't read requirements from your repo in file %s:\n%s" % (
                    filename, str(e)))

        for req in file_reqs:
            req.comes_from = req.comes_from.replace(basedir, "<repo>")
            monolithic_reqs.append(req)

    if lines:
        for line in lines:
            if not line.strip():
                continue  # skip blank lines
            try:
                req = InstallRequirement.from_line(
                    line,
                    comes_from="<djangozoom-web>")
                monolithic_reqs.append(req)
            except InstallationError, e:
                raise ProjectConfigurationException(
                    "The requirement line %r cannot be installed: %s" % (
                        line, str(e)))
            except ValueError, e:
                raise ProjectConfigurationException(
                    "The requirement line %r is invalid: %s" % (
                        line, str(e)))

    if env:
        # unpatch
        env.undo_monkeypatch_pip_util_get_file_content()

    result = []

    trial_requirementset = RequirementSet(
        build_dir=build_prefix, src_dir=src_prefix, download_dir=None)

    ignore_set = set([i.lower() for i in (ignore_keys or [])])

    for r in monolithic_reqs:
        if r.req:
            if r.req.key.lower() in ignore_set:
                continue

            if r.editable:
                req_line = "-e %s" % r.url
            else:
                req_line = str(r.req)
            result.append(req_line)
            # adding reqs to a reqset gives us pip's duplication-determination
            # abilities!
            try:
                trial_requirementset.add_requirement(r)
            except InstallationError, e:
                raise ProjectConfigurationException(
                    "The requirement %s is not acceptable to pip: %s" % (
                        str(r), str(e)))
        else:
            if not r.url:
                raise ProjectConfigurationException(
                    "Unexpected requirement entry has neither .req nor "
                    ".url: %r (%s)" % (r, r))
            else:
                result.append(str(r.url))

    pip_finder_options = []

    # find-links tells pip to crawl links under a page.
    for link in finder.find_links:
        pip_finder_options.append("--find-links=%s" % link)

    # extra-index-url tells pip to check this index in addition to pypi.
    for url in finder.index_urls:
        pip_finder_options.append("--extra-index-url=%s" % url)

    return pip_finder_options + result


def add_to_pth(paths, vpath, relative=False):
    """
    Add a list of ``paths`` to our ``pth`` file for virtualenv found at
    ``venv``.

    :param paths: absolute paths to add to pth file
    :param vpath: absolute path to virtualenv root
    :param relative: if True, entries in ``paths`` should be relative to
        supplied ``vpath``. If another value, relative to that value.
    """
    if relative is True:
        paths = [os.path.join(vpath, p) for p in paths]
    elif relative is not False:
        paths = [os.path.join(relative, p) for p in paths]

    major, minor = sys.version_info[0:2]
    pthfname = os.path.join(get_site_packages(vpath),
                            taskconfig.NR_PTH_FILENAME)
    pthfile = open(pthfname, 'a')
    pthfile.writelines([p.rstrip("\n") + "\n" for p in paths])


def render_tpl_to_file(template, path, **kwargs):
    """
    Render a ``template`` to a file at ``path`` with context ``**kwargs``.

    :param template: Template name; relative path
    :param path: Absolute path to file
    :param env: A UserEnv object to use if not calling open() directly
    """
    tpl = tpl_env.get_template(template)

    if "env" in kwargs:
        env = kwargs.pop("env")
    else:
        env = None

    content = tpl.render(**kwargs)

    if env:
        f = env.open(path, 'w')
    else:
        f = open(path, 'w')

    f.write(content)
    f.close()

    return content


def run_steps(zoomdb, opts, steps):
    cur_dir = os.getcwd()

    for i, stepfn in enumerate(steps):
        nicename = " ".join(stepfn.__name__.split("_")).title()

        zoomdb.log(nicename, zoomdb.LOG_STEP_BEGIN)

        try:
            stepfn(zoomdb, opts)
        finally:
            os.chdir(cur_dir)

        zoomdb.log(nicename, zoomdb.LOG_STEP_END)


def _is_running_on_ec2():
    """Make a guess at whether we're running on ec2."""
    if not hasattr(_is_running_on_ec2, "_cached"):
        kernel_version = local("uname -r")
        _is_running_on_ec2._cached = "virtual" in kernel_version
    return _is_running_on_ec2._cached


def node_meta(field):
    try:
        f = file(os.path.join(taskconfig.NODE_META_DATA_DIR, field))
        value = f.read().strip()
        f.close()
        return value
    except Exception, e:
        if _is_running_on_ec2():
            raise InfrastructureException(
                "Unknown metadata requested: %s.\nException: %s" % (
                    field, str(e)))
        else:
            # we're running on a test system.
            print "(Not on a VM; faking metadata for %s...)" % field
            if field == "name":
                return socket.gethostname()
            return "localhost"


def get_internal_ip():
    """
    Get my "internal" IP, meaning the IP which the frontend proxy should use
    when referring to an appserver. There are multiple ways to do this but
    the pure-python approach seems to work well on EC2 as well as on local
    dev boxes.
    """
    return socket.gethostbyname(socket.gethostname())


def _parse_zoombuild_from_configparser(config):
    """
    Test for validity and extract a configuration dict from a ConfigParser
    object that has already been initialized.
    """
    required_settings = [
        'base_python_package',
        'django_settings_module',
        'site_media_map',
        'additional_python_path_dirs',
        #'pip_reqs',
        'requirements_files',
        'extra_requirements',
        'django_version',
        'database_type',
        ]

    result = {}

    try:
        for s in required_settings:
            result[s] = config.get('project', s)

    except ConfigParser.NoSectionError:
        raise ValueError("Sorry, couldn't find %r in 'project'." % s)

    return result


def parse_zoombuild(buildcfg):
    """
    Parse and validate a :file:`zoombuild.cfg`.

    A example can be found in ``tests/fixtures/app/zoombuild.cfg``.

    :param buildcfg: Absolute path to config file
    """
    config = ConfigParser.RawConfigParser()
    config.read(buildcfg)
    return _parse_zoombuild_from_configparser(config)


def parse_zoombuild_string(buildcfg_string):
    """
    Like parse_zoombuild, but takes a string config input instead of a file
    path.
    """
    buildcfg_fp = StringIO(buildcfg_string)
    config = ConfigParser.RawConfigParser()
    config.readfp(buildcfg_fp)
    return _parse_zoombuild_from_configparser(config)


def get_and_extract_bundle(bundle_name, app_dir, bundle_storage_engine):
    """
    Get a bundle from the provided bundle_storage_engine, and extract it
    into app_dir (creating if neccessary).
    """
    bundletgz = bundle_storage_engine.get(bundle_name + ".tgz")
    if not os.path.isdir(app_dir):
        os.makedirs(app_dir)
    current_dir = os.getcwd()
    os.chdir(app_dir)

    try:
        p = subprocess.Popen(["tar", "xzf", bundletgz], close_fds=True)
        os.waitpid(p.pid, 0)
    finally:
        os.chdir(current_dir)

    os.remove(bundletgz)


def app_and_bundle_dirs(app_id, bundle_name=None):
    """Given an app_id and bundle name, return the app directory and bundle
    directory as a tuple."""

    if bundle_name is None:
        bundle_name = "_"

    app_dir = os.path.join(taskconfig.NR_CUSTOMER_DIR, app_id)
    bundle_dir = os.path.join(app_dir, bundle_name)
    return app_dir, bundle_dir


def parse_site_media_map(site_media_map_text):
    """Given a site_media_map entry, parse the results into a dict mapping
    {url_path: file_path}."""

    def _normalize_url_path(url):
        url = url.strip("/")
        if not url:
            return "/"
        else:
            return "/" + url + "/"

    result = {}

    for line in site_media_map_text.splitlines():
        line = line.strip()
        if not line:
            continue
        url_path, file_path = line.split(None, 1)
        result[_normalize_url_path(url_path)] = file_path

    return result


def chown_to_me(path):
    username = pwd.getpwuid(os.geteuid()).pw_name
    local_privileged(["project_chown", username, path])
