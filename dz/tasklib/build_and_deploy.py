from dz.tasklib import taskconfig
import os

from dz.tasklib import (utils,
                        common_steps,
                        bundle,
                        bundle_storage,
                        placement)
from dz.tasks import database, deploy


def write_build_configuration(zoomdb, opts):
    zcfg = file(os.path.join(opts["APP_DIR"], "zoombuild.cfg"), "w")
    zcfg.write(opts["ZOOMBUILD_CFG_CONTENT"])
    zcfg.close()


def build_project_bundle(zoomdb, opts):
    bundle_name = bundle.bundle_app(opts["APP_ID"])
    zoomdb.log("Built project into bundle: %s" % bundle_name)
    opts["BUNDLE_NAME"] = bundle_name


def request_database_setup(zoomdb, opts):
    if opts["USE_SUBTASKS"]:
        async_result = database.setup_database_for_app.delay(opts["APP_ID"])
        zoomdb.log("Requested database setup for app %s." % opts["APP_ID"])
        opts["database_setup_result"] = async_result
    # if not USE_SUBTASKS, this just gets run synchronously in
    # wait_for_database_setup_to_complete


def upload_project_bundle(zoomdb, opts):
    zoomdb.log("Uploading application bundle %s." % opts["BUNDLE_NAME"])
    bundle.zip_and_upload_bundle(
        opts["APP_ID"], opts["BUNDLE_NAME"],
        bundle_storage_engine=opts["BUNDLE_STORAGE"])
    zoomdb.log("Bundle %s uploaded OK." % opts["BUNDLE_NAME"])


def wait_for_database_setup_to_complete(zoomdb, opts):
    zoomdb.log("Checking to see if database setup is complete...")

    if opts["USE_SUBTASKS"]:
        res = opts["database_setup_result"].wait()
        del opts["database_setup_result"]
        (created, db_host, db_name, db_username, db_password) = res
    else:
        zoomdb.log("Warning: running database creation in synchronous mode.")
        (created, db_host, db_name, db_username, db_password) = \
            database.setup_database_for_app(opts["APP_ID"])


    if created:
        zoomdb.log("Database %s was created. Congratulations " % db_name +
                   "on your first deployment of this project!")
    else:
        zoomdb.log("Database %s was previously created. " % db_name +
                   "Congratulations on a new release!")

    zoomdb.log("Database info: user=%s password=%s dbname=%s host=%s" % (
            db_username, db_password, db_name, db_host))
    opts["DB"] = [db_username, db_password, db_name, db_host]


def select_app_server_for_deployment(zoomdb, opts):
    opts["PLACEMENT"] = placement.placement(opts["APP_ID"])
    if not len(opts["PLACEMENT"]):
        raise utils.InfrastructureException(
            "Could not find any available appservers for hosting " +
            "your project.")


def deploy_project_to_appserver(zoomdb, opts):
    if opts["USE_SUBTASKS"]:
        # send concurrent deploy commands to all placed servers.
        deployment_tasks = []

        for appserver in opts["PLACEMENT"]:
            zoomdb.log("Deploying to %s..." % appserver)

            async_result = deploy.deploy_to_appserver.apply_async(
                args=[opts["APP_ID"],
                      opts["BUNDLE_NAME"],
                      appserver,
                      ] + opts["DB"],
                queue="appserver:" + appserver)
            deployment_tasks.append(async_result)

        for dt in deployment_tasks:
            logmsg = dt.wait()
            zoomdb.log(logmsg)
    else:
        for appserver in opts["PLACEMENT"]:
            zoomdb.log("Deploying to %s..." % appserver)
            logmsg = deploy.deploy_to_appserver(
                opts["APP_ID"],
                opts["BUNDLE_NAME"],
                appserver,
                *opts["DB"])
            zoomdb.log(logmsg)


def run_post_build_hooks(zoomdb, opts):
    """
    Intended for post build application initialization/update commands.
    """


def update_front_end_proxy(zoomdb, opts):
    """
    Effectively have
    Nginx config stored in /etc/nginx/sites-available

    Generate config template for site, note location of app servers as proxy backend.
    Reload nginx.

    Nginx examples for this are in the chef nginx recipe.
    """
    pass


def build_and_deploy(zoomdb, app_id, src_url, zoombuild_cfg_content,
                     use_subtasks=True,
                     bundle_storage_engine=bundle_storage):
    app_dir = os.path.join(taskconfig.NR_CUSTOMER_DIR, app_id)

    opts = {
        "APP_ID": app_id,
        "APP_DIR": app_dir,
        "CO_DIR": os.path.join(app_dir, "src"),
        "SRC_URL": src_url,
        "ZOOMBUILD_CFG_CONTENT": zoombuild_cfg_content,
        "USE_SUBTASKS": use_subtasks,
        "BUNDLE_STORAGE": bundle_storage_engine,
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
