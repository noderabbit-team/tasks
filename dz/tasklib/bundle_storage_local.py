"""
Bundle storage using local files. This is very simple and intended only
for development/testing, not production deployment.
"""

import os
import shutil
import tempfile
from dz.tasklib import taskconfig


def _get_bundle_file(bundle_name):
    bundle_storage_dir = os.path.join(taskconfig.NR_CUSTOMER_DIR,
                                      "bundle_storage_local")

    if not os.path.isdir(bundle_storage_dir):
        os.makedirs(bundle_storage_dir)

    return os.path.join(bundle_storage_dir,
                        bundle_name)


def put(bundle_name, filename):
    shutil.copy(filename, _get_bundle_file(bundle_name))


def get(bundle_name):
    bf = _get_bundle_file(bundle_name)
    if not os.path.isfile(bf):
        raise KeyError("Bundle not found: %s (expected it in %s)" % (
                bundle_name,
                bf))
    tmpfilename = tempfile.mktemp(prefix="tmpbundle")
    shutil.copy(bf, tmpfilename)
    return tmpfilename


def delete(bundle_name):
    bf = _get_bundle_file(bundle_name)
    os.remove(bf)
