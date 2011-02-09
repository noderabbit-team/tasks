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
This job ....
