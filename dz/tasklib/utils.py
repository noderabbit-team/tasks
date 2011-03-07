import os
import subprocess
import sys
from fabric.api import local as fab_local
from fabric.state import connections
from jinja2 import PackageLoader, Environment
import taskconfig


tpl_env = Environment(loader=PackageLoader('dz.tasklib'))


class InfrastructureException(Exception):
    """
    Exception indicating a problem in DjangoZoom's infrastructure, probably
    preventing the user from completing a successful deployment. :(
    """
    pass


class ExternalServiceException(Exception):
    """
    Exception indicating a problem outside of DjangoZoom, such as failure
    to fetch an externally-hosted required module.
    """
    pass


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


def subproc(command, null_stdin=True):
    """
    Run a command locally, using the subprocess module and optionally
    providing a closed stdin filehandle.

    Unlike the fabric-based `local` function also in this module, subproc()
    will capture both stdout and stderr, and will not issue a warning or
    error if the underlying command fails. Therefore, you probably want to
    use check p.returncode to verify the command exited successfully.

    :returns: stdout, stderr, p: output strings and Popen obj of the command.
    """
    p_args = dict(shell=isinstance(command, basestring),
                  stdout=subprocess.PIPE,
                  stderr=subprocess.PIPE)

    if null_stdin:
        p_args["stdin"] = open("/dev/null")

    p = subprocess.Popen(command, **p_args)
    (stdout, stderr) = p.communicate()

    return stdout, stderr, p


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

    :param path: The full path to the virtualenv directory
    """
    # specifying the system python means it's OK if we're running inside a
    # virtualenv ourselves.
    local("virtualenv  --python=/usr/bin/python %s" % path)


def install_requirements(reqs, path):
    """
    Given a ``path`` to a virtualenv, install the given ``reqs``.

    :param reqs: A list of pip requirements
    :param path: A path to a virtualenv
    """
    fname = os.path.join(path, taskconfig.NR_PIP_REQUIREMENTS_FILENAME)
    reqfile = open(fname, "w")
    reqfile.writelines(reqs)
    reqfile.close()
    pip = os.path.join(path, 'bin', 'pip')

    # TODO: add at some point:  --log=<somepath>
    output, stderr, p = subproc("%s install -r %s" % (pip, fname))
    if p.returncode != 0:
        raise ExternalServiceException((
                "Error attempting to install requirements %r. "
                "Pip output:\n %s\n%s") % (reqs, output, stderr))

    print "=== output from pip ==="
    print output
    print "=== end of output from pip ==="


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
    """
    tpl = tpl_env.get_template(template)
    content = tpl.render(**kwargs)
    f = open(path, 'w')
    f.write(content)
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


def local_privileged(cmdargs):
    assert isinstance(cmdargs, list)
    privileged_program = cmdargs.pop(0)
    assert "/" not in privileged_program, ("Privileged programs can only "
                                           "be run from the designated "
                                           "directory. Paths are not allowed.")

    privileged_program_path = os.path.join(taskconfig.PRIVILEGED_PROGRAMS_PATH,
                                           privileged_program)

    fullcmd = ["sudo", privileged_program_path] + cmdargs
    print "Running local_privileged command: %r" % fullcmd
    stdout, stderr, p = subproc(fullcmd, null_stdin=True)
    return stdout
