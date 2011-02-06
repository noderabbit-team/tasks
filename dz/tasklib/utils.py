import os
import sys
from fabric.api import local as fab_local
from fabric.state import connections
from jinja2 import Template, PackageLoader, Environment
import taskconfig


tpl_env = Environment(loader=PackageLoader('dz.tasklib'))


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
    local("%s install -q -r %s" % (pip, fname))

def add_to_pth(paths, vpath, relative=False):
    """
    Add a list of ``paths`` to our ``pth`` file for virtualenv found at ``venv``.

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
    pthfname = os.path.join(get_site_packages(vpath), taskconfig.NR_PTH_FILENAME)
    pthfile = open(pthfname, 'a')
    pthfile.writelines(paths)

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

