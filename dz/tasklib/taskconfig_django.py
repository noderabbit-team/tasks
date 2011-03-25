DJANGO_VERSIONS = {
    "1.2": dict(caption="Django-1.2 latest (currently 1.2.5)",
                pip_line="Django==1.2.5",
                tarball="Django-1.2.5.tar.gz"),
    "1.3": dict(caption="Django-1.3 latest (currently 1.3)",
                pip_line="Django==1.3",
                tarball="Django-1.3.tar.gz"),
}
DJANGO_VERSION_DEFAULT = "1.3"

DJANGO_VERSIONS_CHOICES = [(k, v["caption"]) for (k, v) in
                           DJANGO_VERSIONS.items()]
# sort with latest version first
DJANGO_VERSIONS_CHOICES.sort(key=lambda (k, v): k, reverse=True)

DJANGO_TARBALLS_DIR = "/cust/django"

# Get your tarballs!
# wget http://www.djangoproject.com/download/1.3/tarball/
