"""
Bundle storage using S3.
"""

import tempfile

from dz.tasklib import taskconfig
from boto.s3.connection import S3Connection


def _get_bucket():
    connection = S3Connection()
    bucket = connection.get_bucket(taskconfig.NR_BUNDLE_BUCKET)
    return bucket


def put(bundle_name, filename):
    """
    Upload the given bundle to our bucket on S3.

    :returns: None
    """
    key = _get_bucket().new_key(bundle_name)
    key.set_contents_from_file(open(filename), policy="private")


def get(bundle_name):
    """Get a bundle by name from our bucket on S3.

    :returns: Path to a temporary file containing the bundle.
    """
    key = _get_bucket().get_key(bundle_name)

    if key is None:
        raise KeyError("No such bundle: %s" % bundle_name)

    (fd, tmpfilename) = tempfile.mkstemp(prefix="tmpbundle")
    key.get_contents_to_filename(tmpfilename)
    return tmpfilename


def delete(bundle_name):
    """
    Delete a bundle by name from S3.

    :returns: None
    """
    key = _get_bucket().get_key(bundle_name)
    key.delete()
