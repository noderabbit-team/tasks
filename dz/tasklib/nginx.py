"""
Generate a new nginx site configuration file for the given app. Will
replace any existing configuration file and kick nginx.
"""

import os
import shutil

from dz.tasklib import (taskconfig,
                        bundle,
                        deploy,
                        utils)

SKIP_BUNDLE_INSTALL = object()


def _get_nginx_conffile(app_id):
    return os.path.join(taskconfig.NGINX_SITES_ENABLED_DIR,
                        app_id)


def update_local_proxy_config(app_id, bundle_name,
                              appservers, virtual_hostnames, site_media_map,
                              bundle_storage_engine=None,
                              remove_other_bundles=True):

    bundle_storage_engine = bundle.get_bundle_storage_engine(
        bundle_storage_engine)

    site_conf_filename = _get_nginx_conffile(app_id)

    if len(appservers) == 0:
        raise utils.InfrastructureException((
                "No appserver URLs provided for nginx config update to %s. "
                "At least one upstream is required.") % app_id)

    app_dir, bundle_dir = utils.app_and_bundle_dirs(app_id, bundle_name)

    # We need to make sure this bundle's static is installed locally, so we
    # can serve its static media.
    if bundle_storage_engine is not SKIP_BUNDLE_INSTALL:
        deploy.install_app_bundle_static(
            app_id, bundle_name,
            bundle_storage_engine,
            remove_other_bundles=remove_other_bundles)
    file_path_vars = {
        "{SITE_PACKAGES}": os.path.join(bundle_dir,
                                        "lib/python2.6/site-packages"),
        "{SRC_PACKAGES}": os.path.join(bundle_dir, "src"),
        }
    default_file_path_base = os.path.join(bundle_dir, "user-repo")

    def _make_full_path(original_file_path):
        for varname, pathbase in file_path_vars.items():
            if original_file_path.startswith(varname):
                rest = original_file_path[len(varname):]
                rest = rest.lstrip("/")
                return os.path.join(pathbase, rest)

        return os.path.join(default_file_path_base,
                            original_file_path)

    sme = [dict(url_path=url_path,
                alias_dest=_make_full_path(file_path.strip('/')),
                ) for url_path, file_path in site_media_map.items()]
    sme.append(dict(url_path=taskconfig.DZ_ADMIN_MEDIA["url_path"],
                    alias_dest=os.path.join(
                bundle_dir,
                taskconfig.DZ_ADMIN_MEDIA["bundle_file_path"])))

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
            "app is not currently proxied from this nginx instance (%s). "
            "No site configuration file in %s.")
                                            % (app_id,
                                               utils.node_meta("name"),
                                               site_conf_filename))

    app_dir, _ = utils.app_and_bundle_dirs(app_id)
    shutil.rmtree(app_dir, ignore_errors=True)

    os.remove(site_conf_filename)
    utils.local_privileged(["kick_nginx"])


def find_deployments(zoomdb, opts):
    deployments = zoomdb.search_workers()
    opts["APPSERVERS"] = deployments


def update_proxy_configuration(zoomdb, opts):
    if len(opts["APPSERVERS"]) == 0:
        zoomdb.log("This project has not yet been deployed. Your hostnames "
                   "will become available at your first deployment.")

    else:
        virtual_hostnames = zoomdb.get_project_virtual_hosts()
        zoomdb.log("Your project will be accessible via the following "
                   "hostnames: " + ", ".join(virtual_hostnames))

        bundle_ids = set([d.bundle_id for d in opts["APPSERVERS"]])
        max_bundle_id = max(bundle_ids)

        bundle = zoomdb.get_bundle(max_bundle_id)

        if len(bundle_ids) > 1:
            zoomdb.log("Multiple active bundles appear to be deployed; "
                       "pointing hostnames at bundle %d (%s)." % (
                           bundle.id, bundle.bundle_name),
                       log_type=zoomdb.LOG_WARN)
        ### TODO: ACTUALLY DEPLOY bundle, not full list of deployments!!!!!!

        # deployments must be in (instance_id, node_name, host_ip, host_port)
        # format, but node_name is not actually used so it's OK we ignore it.

        # deployments = [(d.server_instance_id,
        #                 "NODE_NAME_IGNORED",
        #                 d.server_ip, d.server_port)
        #                for d in opts["APPSERVERS"]]
        deployments = [(d.server_instance_id,
                        "NODE_NAME_IGNORED",
                        d.server_ip, d.server_port)
                       for d in opts["APPSERVERS"]
                       if d.bundle_id == max_bundle_id]

        args = [opts["APP_ID"],
                bundle.bundle_name,
                deployments,
                virtual_hostnames,
                opts["SITE_MEDIA_MAP"]]

        import dz.tasks.nginx  # local import to avoid circularity

        if opts["USE_SUBTASKS"]:
            res = dz.tasks.nginx.update_proxy_conf.apply_async(
                args=[zoomdb._job_id] + args)
            res.wait()
        else:
            update_local_proxy_config(*args)

        zoomdb.log("Updated proxy server configuration. Your project is now "
                   "available from the following URLs: " +
                   ", ".join(virtual_hostnames))


def update_hostnames(zoomdb, app_id, zoombuild_cfg_content, use_subtasks=True):
    zcfg = utils.parse_zoombuild_string(zoombuild_cfg_content)
    site_media_map = utils.parse_site_media_map(zcfg.get("site_media_map", ""))

    opts = {"APP_ID": app_id,
            "SITE_MEDIA_MAP": site_media_map,
            "USE_SUBTASKS": use_subtasks}
    utils.run_steps(zoomdb, opts, (
        find_deployments,
        update_proxy_configuration,
        ))
