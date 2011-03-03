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
        dbinfo = opts["database_setup_result"].wait()
        del opts["database_setup_result"]
    else:
        zoomdb.log("Warning: running database creation in synchronous mode.")
        dbinfo = database.setup_database_for_app(opts["APP_ID"])

    if dbinfo.just_created:
        zoomdb.log("Database %s was created. " % dbinfo.db_name +
                   "Congratulations on your first deployment of this project!")
        p = zoomdb.get_project()
        p.db_host = dbinfo.host
        p.db_name = dbinfo.db_name
        p.db_username = dbinfo.username
        p.db_password = dbinfo.password
        zoomdb.flush()

    else:
        zoomdb.log("Database %s was previously created. " % dbinfo.db_name +
                   "Congratulations on a new release!")
        p = zoomdb.get_project()
        for pattr, dbiattr in (
            ("db_host", "host"),
            ("db_name", "db_name"),
            ("db_username", "username"),
            ("db_password", "password"),
            ):

            val = getattr(p, pattr)

            if not val:
                raise utils.InfrastructureException(
                    "Couldn't find existing %s setting in project. " % pattr +
                    "The database for your project was previously created " +
                    "but access information has been lost; please contact " +
                    "support for assistance.")
            else:
                setattr(dbinfo, dbiattr, val)

    zoomdb.log(str(dbinfo))
    opts["DB"] = dbinfo


def select_app_server_for_deployment(zoomdb, opts):
    opts["PLACEMENT"] = placement.placement(opts["APP_ID"])
    if not len(opts["PLACEMENT"]):
        raise utils.InfrastructureException(
            "Could not find any available appservers for hosting " +
            "your project.")


def deploy_project_to_appserver(zoomdb, opts):
    deployed_addresses = []  # in hostname:port format

    if opts["USE_SUBTASKS"]:
        # send concurrent deploy commands to all placed servers.
        deployment_tasks = []

        for appserver in opts["PLACEMENT"]:
            zoomdb.log("Deploying to %s..." % appserver)

            async_result = deploy.deploy_to_appserver.apply_async(
                args=[opts["APP_ID"],
                      opts["BUNDLE_NAME"],
                      appserver,
                      opts["DB"]],
                queue="appserver:" + appserver)
            deployment_tasks.append(async_result)

        for (appserver, dt) in zip(opts["PLACEMENT"], deployment_tasks):
            port = dt.wait()
            zoomdb.log("Serving on %s:%d" % (appserver, port))
            deployed_addresses.append("%s:%d" % (appserver, port))

    else:
        for appserver in opts["PLACEMENT"]:
            zoomdb.log("Deploying to %s..." % appserver)
            port = deploy.deploy_to_appserver(
                opts["APP_ID"],
                opts["BUNDLE_NAME"],
                appserver,
                opts["DB"])
            zoomdb.log("Serving on %s:%d" % (appserver, port))
            deployed_addresses.append("%s:%d" % (appserver, port))

    opts["DEPLOYED_ADDRESSES"] = deployed_addresses


def run_post_build_hooks(zoomdb, opts):
    """
    Intended for post build application initialization/update commands.
    """
    appserver = opts["PLACEMENT"][0]

    def run_managepy_cmd(cmd, nonzero_exit_ok=False):
        """Wraps logic for invoking a manage.py command using either
        subtasks or direct function call."""
        cmd_args = [opts["APP_ID"],
                    opts["BUNDLE_NAME"],
                    cmd,
                    nonzero_exit_ok]
        if opts["USE_SUBTASKS"]:
            res = deploy.managepy_command.apply_async(
                args=cmd_args,
                queue="appserver:" + appserver)
            cmd_output = res.wait()
        else:
            cmd_output = deploy.managepy_command(*cmd_args)

        return cmd_output


    post_build_hooks = opts["POST_BUILD_HOOKS"]

    if post_build_hooks is None:
        post_build_hooks = [["syncdb", "--noinput"]]
        managepy_help = run_managepy_cmd("help", nonzero_exit_ok=True)
        available_commands = [x.strip() for x in 
                              managepy_help.rsplit("Available subcommands:",
                                                   1)[1].splitlines()]
        if "migrate" in available_commands:
            post_build_hooks.append("migrate")

    for cmd in post_build_hooks:
        zoomdb.log("Running 'manage.py %s' ..." % cmd)
        cmd_output = run_managepy_cmd(cmd)
        zoomdb.log(cmd_output)


def update_front_end_proxy(zoomdb, opts):
    """
    Effectively have
    Nginx config stored in /etc/nginx/sites-available

    Generate config template for site, note location of app servers as proxy
    backend.  Reload nginx.

    Nginx examples for this are in the chef nginx recipe.
    """
    pass


def build_and_deploy(zoomdb, app_id, src_url, zoombuild_cfg_content,
                     use_subtasks=True,
                     bundle_storage_engine=bundle_storage,
                     post_build_hooks=None,
                     ):
    app_dir = os.path.join(taskconfig.NR_CUSTOMER_DIR, app_id)

    opts = {
        "APP_ID": app_id,
        "APP_DIR": app_dir,
        "CO_DIR": os.path.join(app_dir, "src"),
        "SRC_URL": src_url,
        "ZOOMBUILD_CFG_CONTENT": zoombuild_cfg_content,
        "USE_SUBTASKS": use_subtasks,
        "BUNDLE_STORAGE": bundle_storage_engine,
        "POST_BUILD_HOOKS": post_build_hooks,
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

    return opts["DEPLOYED_ADDRESSES"]
