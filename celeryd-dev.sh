#!/bin/sh
export CELERY_CONFIG_MODULE=celeryconfig_debug
exec celeryd -Q build,appserver,database -l info
