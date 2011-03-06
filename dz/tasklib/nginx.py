"""
Generate a new nginx site configuration file for the given app. Will
replace any existing configuration file and kick nginx.
"""

import os

from dz.tasklib import (taskconfig,
                        utils)


def _get_nginx_conffile(app_id):
    return os.path.join(taskconfig.NGINX_SITES_ENABLED_DIR,
                        app_id)


def update_local_proxy_config(app_id, appservers, virtual_hostnames):
    site_conf_filename = _get_nginx_conffile(app_id)

    if len(appservers) == 0:
        raise utils.InfrastructureException((
                "No appserver URLs provided for nginx config update to %s. "
                "At least one upstream is required.") % app_id)

    utils.render_tpl_to_file("nginx/site.conf",
                             site_conf_filename,
                             app_id=app_id,
                             appservers=[dict(host=a[0], port=a[1])
                                         for a in appservers],
                             virtual_hostnames=virtual_hostnames)

    utils.local_privileged(["kick_nginx"])


def remove_local_proxy_config(app_id):
    site_conf_filename = _get_nginx_conffile(app_id)

    if not os.path.isfile(site_conf_filename):
        raise utils.InfrastructureException((
                "Requested remove_local_proxy_config for app %s, but that "
                "app is not currently proxied from this nginx instance.")
                                            % app_id)

    os.remove(site_conf_filename)
    utils.local_privileged(["kick_nginx"])
