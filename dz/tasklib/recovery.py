import os


def restore_worker(zoomdb, w):
    from dz.tasklib import build_and_deploy as bd

    from dz.tasklib import (taskconfig,
                            utils)
    from dz.tasklib.database import DatabaseInfo
    from dz.tasks import nginx

    print "restoring: %s" % w

    soup = zoomdb._soup

    project = soup.dz2_project.filter(
        soup.dz2_project.id == w.project_id).one()

    bundle = soup.dz2_appbundle.filter(
        soup.dz2_appbundle.id == w.bundle_id).one()

    print w, project, bundle

    # force zoomdb to have the right project id - HIDEOUS HACK
    zoomdb.get_project_id = lambda: project.id
    zoomdb._project = project

    def fake_log(msg):
        print "ZOOMDB:", msg
    zoomdb.log = fake_log

    app_id = taskconfig.PROJECT_SYSID_FORMAT % project.id
    app_dir = os.path.join(taskconfig.NR_CUSTOMER_DIR, app_id)
    opts = {
        "BUNDLE_INFO": bundle,
        "APP_ID": app_id,
        "APP_DIR": app_dir,
        "BUNDLE_NAME": bundle.bundle_name,
        "DB": DatabaseInfo(project.db_host,
                           project.db_name,
                           project.db_username,
                           project.db_password),
        "NUM_WORKERS": project.num_workers,
        "USE_SUBTASKS": True,

        # Fake ZOOMBUILD_CFG_CONTENT. bd.remove_previous_versions
        # needs it in some cases, but doesn't actually use the value here.
        "ZOOMBUILD_CFG_CONTENT": None,
        }

    bd.select_app_server_for_deployment(zoomdb, opts)

    # undeploy all existing versions
    opts["DEPLOYED_WORKERS"] = []  # trick the following into removing all
    bd.remove_previous_versions(zoomdb, opts)

    bd.deploy_project_to_appserver(zoomdb, opts)
    # sets opts["DEPLOYED_ADDRESSES"] with
    # (instance_id, node_name, host_ip, host_port)
    # and opts["DEPLOYED_WORKERS"] with worker objects.
    new_w = opts["DEPLOYED_WORKERS"][0]

    #from celery.contrib import rdb; rdb.set_trace()

    # # don't run_post_deploy_hooks

    # replace bd.update_front_end_proxy
    fake_job_id = 1676  # TODO: fixme. Must have jobid in both local db and remote db.
    appservers = opts["DEPLOYED_ADDRESSES"]
    virtual_hostnames = zoomdb.get_project_virtual_hosts()
    site_media_map = utils.parse_site_media_map(project.site_media)

    args = [fake_job_id, opts["APP_ID"], opts["BUNDLE_NAME"],
            appservers, virtual_hostnames, site_media_map]
    res = nginx.update_proxy_conf.apply_async(
        args=args,
        kwargs={"remove_other_bundles": True})
    res.wait()

    return new_w


def recover_appserver(zoomdb, appserver_ip, project_id=None):
    dead_workers = zoomdb.search_allproject_workers(active=True,
                                                    ip_address=appserver_ip)
    updated = []
    for w in dead_workers:
        if not(project_id) or w.project_id == project_id:
            updated.append(restore_worker(zoomdb, w))

    return [asd.id for asd in updated]
