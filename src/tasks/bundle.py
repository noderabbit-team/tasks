import os
import datetime
import ConfigParser

import utils


def parse_zoombuild(buildcfg):
    """
    Parse and validate a :file:`zoombuild.cfg`.

    A example can be found in ``tests/fixtures/app/zoomconfig.cfg``.

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

def bundle_app(custdir, app_id):
    """
    Task: Bundle an app with ``app_id`` found in ``custdir``

    :param custdir: Absolute path to the base customer directory
    :param app_id: A path such that ``os.path.join(custdir, app_id)`` is a
        valid directory.
    """
    appdir = os.path.join(custdir, app_id)
    appsrcdir = os.path.join(appdir, "src")
    buildconfig = os.path.join(appdir, "zoombuild.cfg")

    assert os.path.isdir(custdir),\
           "Expected custdir %r to be a directory, but it isn't." % custdir

    assert os.path.isdir(appdir),\
           "Expected to find customer source in directory %r, but that isn't a directory." % appsrcdir

    assert os.path.isfile(buildconfig),\
           "Expected zoombuild.cfg file in %r, but no dice." % buildconfig

    # parse the zoombuild.cfg file
    buildconfig_info = parse_zoombuild(buildconfig)

    assert buildconfig_info,\
           "File %r doesn't look like a valid zoombuild.cfg format file." % buildconfig

    # generate a bundle name and directory
    bundle_name = "bundle_%s_%s" % (app_id,
                                    datetime.datetime.utcnow().strftime("%Y-%m-%d-%H.%M.%S"))
    bundle_dir = os.path.join(appdir, bundle_name)

    # make virtualenv
    utils.make_virtualenv(bundle_dir)

    # archive a copy of the build parameters
    os.system("cp %s %s" % (buildconfig, bundle_dir))

    # Write install requirements
    utils.install_requirements(buildconfig_info["pip_reqs"], bundle_dir)

    # Copy in user code and add to pth
    from_src = os.path.join(bundle_dir, '../src')
    to_src = os.path.join(bundle_dir, 'user-src')
    utils.local('cp --archive %s %s' % (from_src, to_src))
    utils.add_to_pth(buildconfig_info["additional_python_path_dirs"].splitlines(),
                     bundle_dir, relative=to_src)

    # Add settings file
    utils.render_tpl_to_file('bundle/settings.py.tmpl',
                             os.path.join(bundle_dir, 'dz_settings.py'),
                             dz_settings=buildconfig_info["django_settings_module"])

    return bundle_name

