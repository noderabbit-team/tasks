#!/bin/sh
export CELERY_CONFIG_MODULE=celeryconfig_debug
exec celeryctl $1 $2 $3 $4 $5 $6