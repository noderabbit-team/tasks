"""
This module contains management jobs available for invocation via Celery's
broadcast mechanism.
"""

from celery.worker.control import Panel
from celery.task import task
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


# @Panel.register
# def get_installed_bundles(panel):
#     panel.logger.info("Remote control get_installed_bundles request.")
#     return list(management.get_installed_bundles())


def make_mgmt_fun(mgmt_fun_name, wrapper=None):
    f = getattr(management, mgmt_fun_name)

    def mgmtf(panel):
        panel.logger.info("Remote control %s request." % mgmt_fun_name)
        if wrapper:
            return wrapper(f())
        else:
            return f()

    mgmtf.__name__ = mgmt_fun_name

    return mgmtf


for mgmt_fun in ("get_df", "get_nginx_sites_enabled",
                 "get_loadavg", "get_uptime", "get_unicorns",
                 "server_health"):
    Panel.register(make_mgmt_fun(mgmt_fun))

for mgmt_list_fun in ("get_installed_bundles",):
    Panel.register(make_mgmt_fun(mgmt_list_fun, list))


@task(name="gunicorn_signal",
      queue="__QUEUE_MUST_BE_SPECIFIED_DYNAMICALLY__")
def gunicorn_signal(gunicorn_master_pid, signal_name, appserver_name):
    return management.gunicorn_signal(gunicorn_master_pid,
                                      signal_name,
                                      appserver_name)
