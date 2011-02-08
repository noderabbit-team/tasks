#!/bin/sh
export CELERY_CONFIG_MODULE=celeryconfig_testing 
exec nosetests -vv
