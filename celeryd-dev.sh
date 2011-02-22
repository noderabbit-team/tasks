#!/bin/sh
export CELERY_CONFIG_MODULE=celeryconfig_debug
exec celeryd --concurrency=2 -Q build,appserver,database,celery,appserver:localhost -l debug
