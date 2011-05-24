"""

Needs to know.
 - vhost name of the project
 - project app server locations
 - static media locations (aka site media)

"""
from dz.tasks.decorators import task_inject_zoomdb
from dz.tasklib import nginx


@task_inject_zoomdb(name="update_proxy_conf", queue="frontend_proxy")
def update_proxy_conf(job_id, zoomdb, app_id, bundle_name,
                      appservers, virtual_hostnames, site_media_map):
    nginx.update_local_proxy_config(
        app_id, bundle_name,
        appservers, virtual_hostnames, site_media_map)


@task_inject_zoomdb(name="remove_proxy_conf", queue="frontend_proxy")
def remove_proxy_conf(job_id, zoomdb, app_id):
    nginx.remove_local_proxy_config(app_id)


@task_inject_zoomdb(name="update_hostnames", queue="frontend_proxy")
def update_hostnames(job_id, zoomdb, job_params):
    nginx.update_hostnames(zoomdb, job_params["app_id"],
                           job_params["zoombuild_cfg_content"])
