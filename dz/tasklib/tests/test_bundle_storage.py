from dz.tasklib import (taskconfig,
                        bundle_storage,
                        bundle_storage_local)
from dz.tasklib.tests.dztestcase import DZTestCase

import os
import tempfile
import random


class BundleStorageTestCase(DZTestCase):
    """Test bundle storage modules."""

    def _test_put_get_delete_bundle(self, storage_engine):
        """Put, get, and delete a new bundle."""

        FAKE_BUNDLE_CONTENT = "This is a fake bundle file.\n"

        (fd, filename) = tempfile.mkstemp()
        f = os.fdopen(fd, "w")
        f.write(FAKE_BUNDLE_CONTENT)
        f.close()

        bundlename = "bundle_" + str(random.randint(1000, 9999))

        storage_engine.put(bundlename, filename)

        downloaded_bundle_filename = storage_engine.get(bundlename)

        self.assertEqual(open(downloaded_bundle_filename).read(),
                         FAKE_BUNDLE_CONTENT)

        os.remove(filename)
        os.remove(downloaded_bundle_filename)

        storage_engine.delete(bundlename)

        with self.failUnlessRaises(KeyError):
            # Getting a deleted bundle should raise an exception.
            storage_engine.get(bundlename)

    def test_s3_storage_engine(self):
        """Test S3-based bundle storage."""
        return self._test_put_get_delete_bundle(bundle_storage)

    def test_local_storage_engine(self):
        """Test local bundle storage."""
        return self._test_put_get_delete_bundle(bundle_storage_local)
