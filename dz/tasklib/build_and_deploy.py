from dz.tasklib import taskconfig
import os

from dz.tasklib import utils, common_steps
from dz.tasklib.bundle import bundle_app


def write_build_configuration(zoomdb, opts):
    zcfg = file(os.path.join(opts["APP_DIR"], "zoombuild.cfg"), "w")
    zcfg.write(opts["ZOOMBUILD_CFG_CONTENT"])
    zcfg.close()


def build_project_bundle(zoomdb, opts):
    bundle_name = bundle_app(opts["APP_ID"])
    zoomdb.log("Bundle name: %s" % bundle_name)


def request_database_setup(zoomdb, opts):
    pass


def upload_project_bundle(zoomdb, opts):
    pass


def wait_for_database_setup_to_complete(zoomdb, opts):
    pass


def select_app_server_for_deployment(zoomdb, opts):
    pass


def deploy_project_to_appserver(zoomdb, opts):
    pass


def run_post_build_hooks(zoomdb, opts):
    pass


def update_front_end_proxy(zoomdb, opts):
    pass


def build_and_deploy(zoomdb, app_id, src_url, zoombuild_cfg_content):
    app_dir = os.path.join(taskconfig.NR_CUSTOMER_DIR, app_id)

    opts = {
        "APP_ID": app_id,
        "APP_DIR": app_dir,
        "CO_DIR": os.path.join(app_dir, "src"),
        "SRC_URL": src_url,
        "ZOOMBUILD_CFG_CONTENT": zoombuild_cfg_content,
        }

    utils.run_steps(zoomdb, opts, (
            common_steps.checkout_code,
            write_build_configuration,
            build_project_bundle,
            request_database_setup,
            upload_project_bundle,
            wait_for_database_setup_to_complete,
            select_app_server_for_deployment,
            deploy_project_to_appserver,
            run_post_build_hooks,
            update_front_end_proxy,
            ))
