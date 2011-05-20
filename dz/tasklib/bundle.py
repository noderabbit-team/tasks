import os
import shutil
import datetime
import tempfile
import subprocess

from dz.tasklib import (taskconfig,
                        bundle_storage,
                        bundle_storage_local,
                        utils,
                        userenv)


def _ignore_vcs_files(srcdir, names):
    """Ignore function for shutil.copytree, which ensures we don't copy
    version control system files - these don't need to be in the bundles."""
    return [n for n in names if n in (".git", ".svn")]


def bundle_app(app_id, force_bundle_name=None, return_ue=False):
    """
    Task: Bundle an app with ``app_id`` found in ``custdir``

    :param custdir: Absolute path to the base customer directory
    :param app_id: A path such that ``os.path.join(custdir, app_id)`` is a
        valid directory.
    :param force_bundle_name: Optional name for the bundle. If absent, name
        will be auto-generated based on the app name and current date/time.
    :param return_ue: If true, returns the UserEnv object used to build
        the bundle.

    :returns: (bundle_name, code_revision, userenv) if ``return_ue`` is True
        otherwise returns (bundle_name, code_revision)
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
    buildconfig_info = utils.parse_zoombuild(buildconfig)

    err_msg = ("File %r doesn't look like a valid" % buildconfig,
               "zoombuild.cfg format file.")
    assert buildconfig_info, err_msg

    # generate a bundle name and directory
    if force_bundle_name:
        bundle_name = force_bundle_name
    else:
        bundle_name = "bundle_%s_%s" % (
            app_id,
            datetime.datetime.utcnow().strftime("%Y-%m-%d-%H.%M.%S"))

    bundle_dir = os.path.join(appdir, bundle_name)

    # make virtualenv
    utils.make_virtualenv(bundle_dir)

    # archive a copy of the build parameters
    shutil.copyfile(buildconfig,
                    os.path.join(bundle_dir,
                                 "zoombuild.cfg"))

    # Check what version of the code we've got
    code_revision, stderr, p = utils.subproc("(cd %s; git log -n 1)" %
                                             appsrcdir)

    # Copy in user code and add to pth
    to_src = os.path.join(bundle_dir, 'user-src')

    # if there is a base python package, copy user's code under there.
    if buildconfig_info["base_python_package"]:
        bpp_as_path = buildconfig_info["base_python_package"].replace(
            ".", "/")
        to_src = os.path.join(to_src, bpp_as_path)
    else:
        bpp_as_path = None

    # Add in a symlink pointing to the actual repo, so that we can
    # find static files later
    repo_link = os.path.join(bundle_dir, 'user-repo')
    if bpp_as_path:
        repo_link_src = os.path.join('user-src', bpp_as_path)
    else:
        repo_link_src = 'user-src'
    os.symlink(repo_link_src, repo_link)

    # Do the shutil.copytree inside a try/except block so that we can
    # identify bad symlinks. According to http://bugs.python.org/issue6547,
    # bad symlinks will cause an shutil.Error to be raised only at the
    # end of the copy process, so other files are copied correctly.
    # Therefore it is OK to simply warn about any bad links but otherwise
    # assume that things were copied over OK.
    try:
        shutil.copytree(appsrcdir, to_src, ignore=_ignore_vcs_files)
    except shutil.Error, e:
        for src, dst, error in e.args[0]:
            if not os.path.islink(src):
                raise
            else:
                linkto = os.readlink(src)
                if os.path.exists(linkto):
                    raise
                else:
                    ### TODO: communicate this warning to end-user via
                    ### zoomdb.log
                    print("*** Warning: invalid symlink found in " +
                          "project: %s -> %s, but %s doesn't exist." % (
                            src, linkto, linkto))

    utils.add_to_pth(
        buildconfig_info["additional_python_path_dirs"].splitlines(),
        bundle_dir, relative=to_src)

    # add the user-src directory itself to the path
    utils.add_to_pth(['user-src'], bundle_dir, relative=True)

    # if the app has a base python package, add that too
    if bpp_as_path:
        utils.add_to_pth([os.path.join('user-src', bpp_as_path)],
                         bundle_dir, relative=True)

    # First install the selected Django version based on zoombuild.cfg,
    # and use a local tarball if possible.
    djver = taskconfig.DJANGO_VERSIONS[buildconfig_info['django_version']]
    ver_tarball = os.path.join(taskconfig.DJANGO_TARBALLS_DIR,
                               djver["tarball"])

    if os.path.isfile(ver_tarball):
        django_req = ver_tarball
    else:
        django_req = djver["pip_line"]
    utils.install_requirements([django_req], bundle_dir,
                               logsuffix="-django")

    # This is where we've finished running code we trust (virtualenv, django,
    # etc) and switch to running code provided or pointed to by the user. So
    # let's chown everything to the app user.
    utils.local_privileged(["project_chown",
                            app_id,
                            bundle_dir])

    # and let's create the userenv!
    ue = userenv.UserEnv(app_id)

    # install user-provided requirements
    reqs = utils.assemble_requirements(
        files=[l.strip() for l in
               buildconfig_info["requirements_files"].splitlines()],
        lines=[l.strip() for l in
               buildconfig_info["extra_requirements"].splitlines()],
        basedir=repo_link,
        ignore_keys="django",
        env=ue)

    utils.install_requirements(reqs, bundle_dir, env=ue)

    # Remove the python executable, we don't use it
    ue.remove(os.path.join(bundle_dir, "bin", "python"))
    #os.remove(os.path.join(bundle_dir, "bin", "python"))

    # Add settings file
    utils.render_tpl_to_file(
        'bundle/settings.py.tmpl',
        os.path.join(bundle_dir, 'dz_settings.py'),
        env=ue,
        dz_settings=buildconfig_info["django_settings_module"],
        admin_media_prefix=taskconfig.DZ_ADMIN_MEDIA["url_path"])

    if return_ue:
        return bundle_name, code_revision, ue
    else:
        return bundle_name, code_revision


def zip_and_upload_bundle(app_id, bundle_name,
                          bundle_storage_engine=None):
    """
    Task: Zip up the bundle and upload it to S3
    :param custdir: Absolute path to the base customer directory
    :param app_id: A path such that ``os.path.join(custdir, app_id)`` is a
                   valid directory.
    """

    if bundle_storage_engine is None:
        if taskconfig.DEFAULT_BUNDLE_STORAGE_ENGINE == "bundle_storage_local":
            bundle_storage_engine = bundle_storage_local
        else:
            bundle_storage_engine = bundle_storage

    archive_file_path = tempfile.mktemp(suffix=".tgz")

    app_dir = os.path.join(taskconfig.NR_CUSTOMER_DIR, app_id)
    bundle_dir = os.path.join(app_dir, bundle_name)

    try:
        current_dir = os.getcwd()

        # change ownership in app_dir before upload
        # because it was built inside a container
        utils.chown_to_me(bundle_dir)

        os.chdir(app_dir)

        try:
            p = subprocess.Popen(
                ["tar", "czf", archive_file_path, bundle_name],
                env=dict(PWD=app_dir),
                close_fds=True)
            os.waitpid(p.pid, 0)
        finally:
            os.chdir(current_dir)

        bundle_storage_engine.put(bundle_name + ".tgz",
                                  archive_file_path)

    finally:
        if os.path.exists(archive_file_path):
            os.remove(archive_file_path)

    return bundle_name + ".tgz"
