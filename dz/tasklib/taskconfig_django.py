import subprocess

DJANGO_VERSIONS = {
    "1.2": dict(caption="Django-1.2 latest (currently 1.2.7)",
                pip_line="Django==1.2.7",
                tarball="Django-1.2.7.tar.gz"),
    "1.3": dict(caption="Django-1.3.1 latest (currently 1.3.1)",
                pip_line="Django==1.3.1",
                tarball="Django-1.3.1.tar.gz"),
}
DJANGO_VERSION_DEFAULT = "1.3.1"

DJANGO_VERSIONS_CHOICES = [(k, v["caption"]) for (k, v) in
                           DJANGO_VERSIONS.items()]
# sort with latest version first
DJANGO_VERSIONS_CHOICES.sort(key=lambda (k, v): k, reverse=True)

DJANGO_TARBALLS_DIR = "/cust/django"

# Get your tarballs!
# wget http://www.djangoproject.com/download/1.3/tarball/
# Tarballs corresponding to DJANGO_VERSION above will be automatically
# downloaded during a quick_deploy if you answer yes to the question about
# checking for new Django versions.

# PYTHON_VERSIONS = {}

# for pyver in ("2.7", "2.6", "2.5"):
#     try:
#         exe = "/usr/bin/python%s" % pyver
#         caption = subprocess.check_output([exe, "--version"],
#                                           stderr=subprocess.STDOUT).strip()
#         PYTHON_VERSIONS[pyver] = dict(caption=caption,
#                                       exe=exe)
#     except OSError:
#         pass

# PYTHON_VERSION_DEFAULT = "2.7"
