DJANGO_VERSIONS = {
    "1.2": dict(caption="Django-1.2 latest (currently 1.2.5)",
                pip_line="Django==1.2.5",
                tarball="Django-1.2.5.tar.gz"),
}
DJANGO_VERSION_DEFAULT = "1.2"

DJANGO_VERSIONS_CHOICES = [ (k, v["caption"]) for (k,v) in DJANGO_VERSIONS.items() ]

DJANGO_TARBALLS_DIR = "/cust/django"
