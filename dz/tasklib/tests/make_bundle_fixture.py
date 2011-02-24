#!/usr/bin/env python
import os
import shutil

from dz.tasklib import (bundle,
                        bundle_storage_local,
                        taskconfig)

BUNDLE_NAME = "bundle_app_2011-fixture"

if __name__ == "__main__":
    print "Making a bundle fixture for testing."

    here = os.path.abspath(os.path.split(__file__)[0])
    fixture_dir = os.path.join(here, 'fixtures')
    app_name = "app"

    # force rename the bundle
    app_dir = os.path.join(taskconfig.NR_CUSTOMER_DIR, app_name)

    if os.path.isdir(app_dir):
        shutil.rmtree(app_dir)

    shutil.copytree(os.path.join(fixture_dir, app_name),
                    app_dir)
    bundle_name = bundle.bundle_app(app_name,
                                    force_bundle_name=BUNDLE_NAME)

    bundle_dir = os.path.join(taskconfig.NR_CUSTOMER_DIR,
                              app_name,
                              bundle_name)

    tarball_name = bundle.zip_and_upload_bundle(app_name,
                                                BUNDLE_NAME,
                                                bundle_storage_local)

    # after upload, delete the dir where bundle was created
    shutil.rmtree(bundle_dir)

    print "Bundle %s now in local storage." % tarball_name
