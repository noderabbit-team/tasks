from dz.tasklib import taskconfig
import os

from dz.tasklib import (utils,
                        common_steps,
                        bundle,
                        bundle_storage,
                        bundle_storage_local,
                        placement)
from dz.tasks import database, deploy, nginx


def write_build_configuration(zoomdb, opts):
    zcfg = file(os.path.join(opts["APP_DIR"], "zoombuild.cfg"), "w")
    zcfg.write(opts["ZOOMBUILD_CFG_CONTENT"])
    zcfg.close()


def build_project_bundle(zoomdb, opts):
    zoomdb.log("We're getting your project's dependencies and packaging "
               "everything up. This might take a couple of minutes.")
    bundle_name, code_revision, ue = bundle.bundle_app(opts["APP_ID"],
                                                       return_ue=True)
    zoomdb.log("Built project into bundle: %s" % bundle_name)
    opts["BUNDLE_NAME"] = bundle_name
    # and log this bundle into zoomdb
    opts["BUNDLE_INFO"] = zoomdb.add_bundle(bundle_name, code_revision)

    post_build_hooks = opts["POST_BUILD_HOOKS"]

    bundle_runner = os.path.join(opts["APP_DIR"],
                                 bundle_name,
                                 "thisbundle_build.py")
    # write out a temporary build-time bundle runner
    utils.render_tpl_to_file('deploy/thisbundle.py.tmpl',
                             bundle_runner,
                             dbinfo=None,  # no database access yet
                             num_workers=0,
                             env=ue)
    ue.call(["chmod", "700", bundle_runner])

    def run_buildtime_managepy_cmd(cmdlist, nonzero_exit_ok=False):
        stdout, stderr, p = ue.subproc([bundle_runner] + cmdlist,
                                       nonzero_exit_ok=nonzero_exit_ok)
        return stdout, stderr, p

    if post_build_hooks is None:
        post_build_hooks = []

        _stdout, managepy_help, _p = run_buildtime_managepy_cmd(
            ["help"], nonzero_exit_ok=True)
        try:
            available_commands = [x.strip() for x in
                                  managepy_help.rsplit(
                                      "Available subcommands:",
                                      1)[1].splitlines()]

            if "collectstatic" in available_commands:
                zoomdb.log("Found that your project offers a 'collectstatic' "
                           "management command; adding that to post-build "
                           "hooks.")
                post_build_hooks.append(["collectstatic",
                                         "--link",
                                         "--noinput"])

        except IndexError:
            zoomdb.log(("Warning: Couldn't determine whether you have a "
                     "'collectstatic' command because 'manage.py help' didn't "
                     "provide a list of available subcommands as expected. "
                     "Full manage.py help output was:\n%s") % managepy_help)

    if not post_build_hooks:
        zoomdb.log("No post-build hooks found.")
    else:
        try:
            for cmdlist in post_build_hooks:
                cmdtext = " ".join(cmdlist)
                zoomdb.log("Running post-build 'manage.py %s': " % cmdtext)
                cmd_output, cmd_err, cmd_p = run_buildtime_managepy_cmd(
                    cmdlist)
                zoomdb.log("Executed: " + cmd_output + cmd_err)
        except RuntimeError, e:
            zoomdb.log("Warning: there was an error running a post-build "
                       "command. Detail:\n" + e.message,
                       zoomdb.LOG_WARN)

    ue.call(["rm", bundle_runner])


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
        bundle_storage_engine=opts["BUNDLE_STORAGE"],
        delete_after_upload=True)
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
                    "The database for your project, %s, " % dbinfo.db_name +
                    "was previously created but access information has been "
                    "lost; please contact support for assistance.")
            else:
                dbinfo[dbiattr] = val

    # DON'T SHOW THIS TO END USERS - it includes the DB password!
    #zoomdb.log(str(dbinfo))
    opts["DB"] = dbinfo


def select_app_server_for_deployment(zoomdb, opts):
    opts["PLACEMENT"] = placement.placement(opts["APP_ID"])
    if not len(opts["PLACEMENT"]):
        raise utils.InfrastructureException(
            "Could not find any available appservers for hosting " +
            "your project.")


def deploy_project_to_appserver(zoomdb, opts):
    deployed_addresses = []  # in (hostname,port) format

    appserver_placeholder = object()

    dep_args = [opts["APP_ID"],
                opts["BUNDLE_NAME"],
                appserver_placeholder,
                opts["DB"],
                opts["NUM_WORKERS"]]

    if opts["USE_SUBTASKS"]:
        # send concurrent deploy commands to all placed servers.
        deployment_tasks = []

        for appserver in opts["PLACEMENT"]:
            zoomdb.log("Deploying to %s..." % appserver)

            my_args = list(dep_args)
            my_args[my_args.index(appserver_placeholder)] = appserver

            async_result = deploy.deploy_to_appserver.apply_async(
                args=my_args,
                queue="appserver:" + appserver)
            deployment_tasks.append(async_result)

        for (appserver, dt) in zip(opts["PLACEMENT"], deployment_tasks):
            (instance_id, node_name, host_ip, host_port) = dt.wait()
            zoomdb.log("Serving on %s:%d" % (instance_id, host_port))
            deployed_addresses.append((instance_id, node_name,
                                       host_ip, host_port))

    else:
        for appserver in opts["PLACEMENT"]:
            zoomdb.log("Deploying to %s..." % appserver)

            my_args = list(dep_args)
            my_args[my_args.index(appserver_placeholder)] = appserver

            (instance_id, node_name, host_ip, host_port) = \
                deploy.deploy_to_appserver(*my_args)
            zoomdb.log("Serving on %s:%d" % (host_ip, host_port))
            deployed_addresses.append((instance_id, node_name,
                                       host_ip, host_port))

    opts["DEPLOYED_ADDRESSES"] = deployed_addresses

    bundle_id = opts["BUNDLE_INFO"].id
    for (instance_id, node_name, host_ip, host_port) in deployed_addresses:
        #instance_id = hostname  # TODO: this is a hack :(

        # this won't work on ec2, we'll need to have deploy_to_appserver
        # return the appserver's internal IP address (or public int/ext
        # hostname)
        #host_ip = socket.gethostbyname(hostname)

        zoomdb.add_worker(bundle_id,
                          instance_id,
                          host_ip,
                          host_port)


def run_post_deploy_hooks(zoomdb, opts):
    """
    Intended for post deploy application initialization/update commands.
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

    post_deploy_hooks = opts["POST_DEPLOY_HOOKS"]

    if post_deploy_hooks is None:
        post_deploy_hooks = [["syncdb", "--noinput"]]
        managepy_help = run_managepy_cmd("help", nonzero_exit_ok=True)

        try:
            available_commands = [x.strip() for x in
                                  managepy_help.rsplit(
                                      "Available subcommands:",
                                      1)[1].splitlines()]
            if "migrate" in available_commands:
                post_deploy_hooks.append("migrate")

        except IndexError:
            zoomdb.log(("Warning: Couldn't determine whether you have a "
                        "'migrate' command because 'manage.py help' didn't "
                        "provide a list of available subcommands as expected. "
                        "Full manage.py help output was:\n%s") % managepy_help)

    try:
        for cmd in post_deploy_hooks:
            cmdtext = " ".join(cmd) if isinstance(cmd, list) else cmd
            zoomdb.log("Running 'manage.py %s': " % cmdtext)
            cmd_output = run_managepy_cmd(cmd)
            zoomdb.log("Executed: " + cmd_output)
    except RuntimeError, e:
        zoomdb.log("Warning: there was an error running a post-deploy "
                   "command. Detail:\n" + e.message,
                   zoomdb.LOG_WARN)


def update_front_end_proxy(zoomdb, opts):
    """
    Generate config template for site, note location of app servers as proxy
    backend.  Reload nginx.

    Nginx examples for this are in the chef nginx recipe.

    When running locally in dev, you must make sure whatever user runs celeryd
    has write permission to /etc/nginx/sites-enabled
    $ sudo chgrp nateaune /etc/nginx/sites-enabled/
    $ sudo chmod g+w /etc/nginx/sites-enabled/
    """
    # (instance_id, node_name, host_ip, host_port) format
    appservers = opts["DEPLOYED_ADDRESSES"]

    virtual_hostnames = zoomdb.get_project_virtual_hosts()

    zcfg = utils.parse_zoombuild(os.path.join(opts["APP_DIR"],
                                              "zoombuild.cfg"))
    site_media_map = utils.parse_site_media_map(zcfg.get("site_media_map", ""))

    args = [zoomdb._job_id, opts["APP_ID"], opts["BUNDLE_NAME"],
            appservers, virtual_hostnames, site_media_map]

    if opts["USE_SUBTASKS"]:
        res = nginx.update_proxy_conf.apply_async(args=args)
        res.wait()
    else:
        nginx.update_proxy_conf(*args)

    zoomdb.log("Updated proxy server configuration. Your project is now "
               "available from the following URLs: " +
               ", ".join(virtual_hostnames))


def build_and_deploy(zoomdb, app_id, src_url, zoombuild_cfg_content,
                     use_subtasks=True,
                     bundle_storage_engine=None,
                     post_build_hooks=None,
                     post_deploy_hooks=None,
                     num_workers=1,
                     ):
    app_dir = os.path.join(taskconfig.NR_CUSTOMER_DIR, app_id)

    if bundle_storage_engine is None:
        if taskconfig.DEFAULT_BUNDLE_STORAGE_ENGINE == "bundle_storage_local":
            bundle_storage_engine = bundle_storage_local
        else:
            bundle_storage_engine = bundle_storage

    opts = {
        "APP_ID": app_id,
        "APP_DIR": app_dir,
        "CO_DIR": os.path.join(app_dir, "src"),
        "SRC_URL": src_url,
        "ZOOMBUILD_CFG_CONTENT": zoombuild_cfg_content,
        "USE_SUBTASKS": use_subtasks,
        "BUNDLE_STORAGE": bundle_storage_engine,
        "POST_BUILD_HOOKS": post_build_hooks,
        "POST_DEPLOY_HOOKS": post_deploy_hooks,
        "NUM_WORKERS": num_workers,
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
            run_post_deploy_hooks,
            update_front_end_proxy,
            ))

    return opts["DEPLOYED_ADDRESSES"]
