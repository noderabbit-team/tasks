#!/bin/sh
export CELERY_CONFIG_MODULE=celeryconfig_debug
celeryctl inspect enable_events
exec celeryev $1 $2 $3 $4 $5 $6