import os
import shutil
import datetime
import ConfigParser

import taskconfig
import utils

import tempfile
import subprocess

from boto.s3.connection import S3Connection


def parse_zoombuild(buildcfg):
    """
    Parse and validate a :file:`zoombuild.cfg`.

    A example can be found in ``tests/fixtures/app/zoombuild.cfg``.

    :param buildcfg: Absolute path to config file
    """
    config = ConfigParser.RawConfigParser()
    config.read(buildcfg)

    required_settings = [
        #'base_python_package',
        'django_settings_module',
        'site_media_map',
        'additional_python_path_dirs',
        'pip_reqs',
        ]

    result = {}

    try:
        for s in required_settings:
            result[s] = config.get('project', s)

    except ConfigParser.NoSectionError:
        raise ValueError("Sorry, couldn't find %r in 'project'." % buildcfg)

    return result


def bundle_app(app_id):
    """
    Task: Bundle an app with ``app_id`` found in ``custdir``

    :param custdir: Absolute path to the base customer directory
    :param app_id: A path such that ``os.path.join(custdir, app_id)`` is a
        valid directory.
    """

    appdir = os.path.join(taskconfig.NR_CUSTOMER_DIR, app_id)
    appsrcdir = os.path.join(appdir, "src")
    buildconfig = os.path.join(appdir, "zoombuild.cfg")

    assert os.path.isdir(taskconfig.NR_CUSTOMER_DIR),\
           "Expected custdir %r to be a directory, but it isn't." % (
        taskconfig.NR_CUSTOMER_DIR)

    err_msg = ("Expected to find customer source in directory %r," % appsrcdir,
               "but that isn't a directory.")
    assert os.path.isdir(appdir), err_msg

    assert os.path.isfile(buildconfig),\
           "Expected zoombuild.cfg file in %r, but no dice." % buildconfig

    # parse the zoombuild.cfg file
    buildconfig_info = parse_zoombuild(buildconfig)

    err_msg = ("File %r doesn't look like a valid" % buildconfig,
               "zoombuild.cfg format file.")
    assert buildconfig_info, err_msg

    # generate a bundle name and directory
    bundle_name = "bundle_%s_%s" % (
        app_id,
        datetime.datetime.utcnow().strftime("%Y-%m-%d-%H.%M.%S"))
    bundle_dir = os.path.join(appdir, bundle_name)

    # make virtualenv
    utils.make_virtualenv(bundle_dir)

    # archive a copy of the build parameters
    shutil.copyfile(buildconfig,
                    os.path.join(bundle_dir,
                                 taskconfig.NR_PIP_REQUIREMENTS_FILENAME))

    # Write install requirements
    utils.install_requirements(buildconfig_info["pip_reqs"], bundle_dir)

    # Copy in user code and add to pth
    to_src = os.path.join(bundle_dir, 'user-src')
    shutil.copytree(appsrcdir, to_src)
    utils.add_to_pth(
        buildconfig_info["additional_python_path_dirs"].splitlines(),
        bundle_dir, relative=to_src)

    # Copy static directories to a better location
    for line in buildconfig_info["site_media_map"].splitlines():
        static, _ = line.strip().split()
        from_static = os.path.join(appsrcdir, static)
        to_static = os.path.join(bundle_dir, static)
        if os.path.isdir(from_static):
            shutil.copytree(from_static, to_static)

    # Add settings file
    utils.render_tpl_to_file(
        'bundle/settings.py.tmpl',
        os.path.join(bundle_dir, 'dz_settings.py'),
        dz_settings=buildconfig_info["django_settings_module"])

    return bundle_name


def zip_and_upload_bundle(app_id, bundle_name):
    """
    Task: Zip up the bundle and upload it to S3
    :param custdir: Absolute path to the base customer directory
    :param app_id: A path such that ``os.path.join(custdir, app_id)`` is a
                   valid directory.
    """
    connection = S3Connection()
    archive_file_path = tempfile.mktemp(suffix=".tgz")

    app_dir = os.path.join(taskconfig.NR_CUSTOMER_DIR, app_id)

    try:
        current_dir = os.getcwd()
        os.chdir(app_dir)

        try:
            p = subprocess.Popen(
                ["tar", "czf", archive_file_path, bundle_name],
                env=dict(PWD=app_dir),
                close_fds=True)
            os.waitpid(p.pid, 0)
        finally:
            os.chdir(current_dir)

        bucket = connection.get_bucket(taskconfig.NR_BUNDLE_BUCKET)
        key = bucket.new_key(bundle_name + ".tgz")
        key.set_contents_from_file(
            open(archive_file_path), policy="private")

    finally:
        if os.path.exists(archive_file_path):
            os.remove(archive_file_path)

    return bundle_name + ".tgz"
