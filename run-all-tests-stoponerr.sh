#!/bin/sh
if (pgrep celery > /dev/null); then
    echo It appears a celery process is running. You should kill it before attempting to run the test suite.
    exit 1
fi

export CELERY_CONFIG_MODULE=celeryconfig_testing 
exec nosetests -vvx --pdb --pdb-failures
