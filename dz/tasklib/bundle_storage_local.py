"""
Bundle storage using local files. This is very simple and intended only
for development/testing, not production deployment.
"""

import os
import shutil
import tempfile
from dz.tasklib import taskconfig

BUNDLE_STORAGE_DIR = os.path.join(taskconfig.NR_CUSTOMER_DIR,
                                  "bundle_storage_local")

if not os.path.isdir(BUNDLE_STORAGE_DIR):
    os.makedirs(BUNDLE_STORAGE_DIR)


def _get_bundle_file(bundle_name):
    return os.path.join(BUNDLE_STORAGE_DIR,
                        bundle_name)


def put(bundle_name, filename):
    shutil.copy(filename, _get_bundle_file(bundle_name))


def get(bundle_name):
    bf = _get_bundle_file(bundle_name)
    if not os.path.isfile(bf):
        raise KeyError("Bundle not found: %s" % bundle_name)
    tmpfilename = tempfile.mktemp(prefix="tmpbundle")
    os.link(bf, tmpfilename)
    return tmpfilename


def delete(bundle_name):
    bf = _get_bundle_file(bundle_name)
    os.remove(bf)
