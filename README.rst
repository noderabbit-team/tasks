Task management for DjangoZoom
==============================

This project contains two main packages:

 * dz.tasks, which provides callable celery tasks for various djangozoom
   functions

 * dz.tasklib, which contains the actual work logic for those tasks.

Tasks are managed using a network of celeryd workers, all speaking to a
central AMQP (rabbitmq) server. The server layout looks like this:

 * usercontrol: runs rabbitmq. No celeryd processes.
 * build: runs celeryd -Q build (i.e. only looks at the "build" queue)
 * appserver: runs celeryd -Q all_appservers,appserver_<my_instance_id>
 * proxy: runs celeryd -Q proxy
 * database: runs celeryd -Q database

Each user-visible job, represented by the Job model in dz2.models, may
reflect a set of other jobs executed across the above workers. The
distinction between a Job and a task is that a Job is a user-visible (and
usually, but not neccessarily, user-initiated) unit of work; a Job may
involve one or many celery tasks.

Job: check_repo
===============

This job is used during the setup of a brand new project. It checks out the
code, does some parsing and snooping around in it, and provides a set of
guesses about how the project should be configured in order to make the code
buildable and deployable.

Sequence:
 * [usercontrol] user provides source code URL
 * [usercontrol] check_repo task issued (in queue "build")
 * [build] check_repo task executed
    * check out code
    * inspect code
    * write ConfigGuesses to DB via zoomdb
 * [usercontrol] on task completion, forward user to verification form

Job: build_and_deploy
=====================

This job creates a bundle corresponding to a newly built version of the
project code and all known dependencies. The bundle is then uploaded to S3
and the database is updated with information about the new bundle. If
necessary, a database is created for the project. The bundle is then
deployed to an appserver, and post-build hooks (i.e. syncdb & migrate) are
run on the appserver.

Sequence:
 * [usercontrol] user requests new build
 * [usercontrol] build_and_deploy task issued (in queue "build")
    * zoombuild.cfg attached (as job_params)
 * [build] build_bundle task enqueued and executed (as subtask of 
   build_and_launch)
    * check out code
    * create virtualenv
    * install dependencies
    * verify can execute something simple, abort on importerror etc
    * archive bundle into tarball
    * enqueue create_database task (in parallel with bundle_upload below)
       * [db] create_database task executed (in parallel)
          * create database for app if needed
          * return db name, hostname, user (=sysid), password (random)
    * enqueue bundle_upload task (in parallel with create_database)
       * [build] upload bundle to S3
    * wait for create_database and bundle_upload to finish
    * enqueue and wait for placement task
       * [build] execute placement task
          * select appserver
             * initially choose from the list of length 1
             * later select based on continuously-updated load/health stats
          * return selected appserver ID
    * enqueue and wait for deploy task to selected appserver's queue
       * [appserver-<ID>] execute deploy task
          * download bundle from S3
          * create project user if needed
          * extract bundle
          * run bundle under cherrypy/gunicorn/whatevs
          * update DB with bundle deployment location
          * return hostname, port, and instance id where worker is running
    * process post-build hooks (maybe initially do this as part of deploy)
       * syncdb, migrate
    * enqueue proxy_update task to proxy queue
       * [proxy] execute proxy_update task
          * given app ID, virtual hostnames, appserver IP & port, 
            (re)create nginx config entry for app
    * (later) execute rollback (or at least vhost rename) of other (old)
      bundle versions 
    * w00t, report success & url to user!
