"""
This module contains management jobs available for invocation via Celery's
broadcast mechanism.
"""

from celery.worker.control import Panel
from dz.tasklib import (utils,
                        deploy,
                        management)


@Panel.register
def server_profile(panel):
    panel.logger.info("Remote control server_profile request.")
    return {"name": utils.node_meta("name"),
            "role": utils.node_meta("role"),
            "instance_id": utils.node_meta("instance_id"),
            }


@Panel.register
def get_active_bundles(panel):
    panel.logger.info("Remote control get_active_bundles request.")
    return list(deploy.get_active_bundles())


@Panel.register
def get_installed_bundles(panel):
    panel.logger.info("Remote control get_installed_bundles request.")
    return list(management.get_installed_bundles())


@Panel.register
def get_df(panel):
    panel.logger.info("Remote control get_df request.")
    return management.get_df()


@Panel.register
def get_nginx_sites_enabled(panel):
    panel.logger.info("Remote control get_nginx_sites_enabled request.")
    return management.get_nginx_sites_enabled()
