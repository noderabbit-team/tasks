from dz.tasklib import (taskconfig,
                        utils)
import os


def get_installed_bundles():
    if not os.path.isdir(taskconfig.NR_CUSTOMER_DIR):
        return []

    result = []
    for custdir in os.listdir(taskconfig.NR_CUSTOMER_DIR):
        if custdir.startswith(".") or custdir == "django":
            continue
        fullcustdir = os.path.join(taskconfig.NR_CUSTOMER_DIR, custdir)
        if not os.path.isdir(fullcustdir):
            continue

        for bundledir in os.listdir(fullcustdir):
            if bundledir.startswith(".") or bundledir == "src":
                continue
            fullbundledir = os.path.join(fullcustdir, bundledir)
            if not os.path.isdir(fullbundledir):
                continue

            result.append(dict(app_id=custdir,
                               bundle_name=bundledir))
    return result


def get_df():
    result = []

    for cmd in ("df -h", "df -i"):
        output = utils.local(cmd)
        for i, line in enumerate(output.splitlines()):
            if i == 0 or line.startswith("/dev"):
                result.append(line)
        result.append("")

    return "\n".join(result)


def get_nginx_sites_enabled():
    if not os.path.isdir(taskconfig.NGINX_SITES_ENABLED_DIR):
        return []

    result = []
    for site in os.listdir(taskconfig.NGINX_SITES_ENABLED_DIR):
        if site.startswith("."):
            continue

        sitefile = os.path.join(taskconfig.NGINX_SITES_ENABLED_DIR, site)

        siteinfo = dict(site=site)

        for line in open(sitefile).readlines():
            parts = line.strip().rstrip(";").split()
            if len(parts) < 2:
                continue

            if parts[0] == "server" and parts[1] != "{":
                siteinfo["server"] = parts[1]
            elif parts[0] == "server_name":
                siteinfo["server_name"] = parts[1:]
            elif parts[0] == "alias":
                siteinfo["bundle_name"] = parts[1].split("/")[3]

        result.append(siteinfo)

    return result
