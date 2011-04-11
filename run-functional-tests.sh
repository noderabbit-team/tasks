#!/bin/sh
if (pgrep celery > /dev/null); then
    echo It appears a celery process is running. You should kill it before attempting to run the functional tests.
    exit 1
fi

cd dz/tasklib/tests
export CELERY_CONFIG_MODULE=celeryconfig_testing 
exec nosetests -vv funtests
