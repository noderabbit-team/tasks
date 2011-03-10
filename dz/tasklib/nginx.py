"""
Generate a new nginx site configuration file for the given app. Will
replace any existing configuration file and kick nginx.
"""

import os
import shutil

from dz.tasklib import (taskconfig,
                        utils)


def _get_nginx_conffile(app_id):
    return os.path.join(taskconfig.NGINX_SITES_ENABLED_DIR,
                        app_id)


def update_local_proxy_config(app_id, bundle_name,
                              appservers, virtual_hostnames, site_media_map):
    site_conf_filename = _get_nginx_conffile(app_id)

    if len(appservers) == 0:
        raise utils.InfrastructureException((
                "No appserver URLs provided for nginx config update to %s. "
                "At least one upstream is required.") % app_id)

    app_dir, bundle_dir = utils.app_and_bundle_dirs(app_id, bundle_name)

    sme = [dict(url_path=url_path,
                bundle_dir=bundle_dir,
                file_path=file_path,
                alias_dest=os.path.join(bundle_dir,
                                        "user-repo",
                                        file_path.lstrip("/")),
                ) for url_path, file_path in site_media_map.items()]

    # NOTE THE SLASHES::::
    # location /static/ {
    #     alias /tmp/tmpR_1dI5/test001/bundle_test001_2011-03-09-03.52.55/user-src/static/;
    # }

    utils.render_tpl_to_file("nginx/site.conf",
                             site_conf_filename,
                             app_id=app_id,
                             appservers=[dict(
                # (instance_id, node_name, host_ip, host_port)
                instance_id=a[0],
                node_name=a[1],
                host_ip=a[2],
                host_port=a[3],
                )
                                         for a in appservers],
                             virtual_hostnames=virtual_hostnames,
                             site_media_entries=sme)

    utils.local_privileged(["kick_nginx"])


def remove_local_proxy_config(app_id):
    site_conf_filename = _get_nginx_conffile(app_id)

    if not os.path.isfile(site_conf_filename):
        raise utils.InfrastructureException((
                "Requested remove_local_proxy_config for app %s, but that "
                "app is not currently proxied from this nginx instance.")
                                            % app_id)

    app_dir, _ = utils.app_and_bundle_dirs(app_id)
    shutil.rmtree(app_dir, ignore_errors=True)

    os.remove(site_conf_filename)
    utils.local_privileged(["kick_nginx"])
