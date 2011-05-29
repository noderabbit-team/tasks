from dz.tasklib import (taskconfig,
                        utils)
import os
import psi
import psi.process
import pwd
import re


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
                               bundle_name=bundledir,
                               bundle_path=fullbundledir))
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


def get_uptime():
    return psi.uptime().timestamp()


def get_loadavg():
    return psi.loadavg()

# gunicorn: master ['bundle_p00000002_2011-05-11-02.50.14 on :10004']
# gunicorn: master ['bundle_p00000002_2011-04-08-16.40.42 on :10001']
GUNICORN_CMD_RE = re.compile(
    r"^gunicorn: (master|worker) \['(\S+) on :(\d+)'\]\s*$")


def get_unicorns():

    unicorns_by_bundle = {}

    for pid, proc in psi.process.ProcessTable().items():
        m = GUNICORN_CMD_RE.match(proc.command)
        if not m:
            continue

        proc_type = m.group(1)
        bundle_name = m.group(2)
        port = int(m.group(3))

        d = unicorns_by_bundle.setdefault(
            bundle_name,
            dict(bundle_name=bundle_name,
                 port=port,
                 user=pwd.getpwuid(proc.euid).pw_name))
        if proc_type == "master":
            d["master_pid"] = pid
        else:
            d.setdefault("worker_pids", []).append(pid)

    return sorted(unicorns_by_bundle.values(), key=lambda x: x["bundle_name"])


def gunicorn_signal(gunicorn_master_pid, signal_name, appserver_name):
    my_hostname = utils.node_meta("name")

    if appserver_name not in (my_hostname, "localhost"):
        raise utils.InfrastructureException(
            "Incorrect appserver received gunicorn_signal task; " +
            "I am %s but the task is requesting %s." % (my_hostname,
                                                        appserver_name))

    if signal_name not in ("TTIN", "TTOU"):
        raise utils.InfrastructureException(
            "Unexpected gunicorn_signal %s: only TTIN & TTOU allowed."
            % signal_name)

    utils.local_privileged(["gunicorn_signal",
                            signal_name,
                            gunicorn_master_pid])


def server_health():
    """
    Get a bunch of stats pertaining to current server health.
    """
    def _maxdisk():
        maxdisk = dict(pct=0)

        # parse df output to find max disk use indicator
        header_line = ""
        for cmd, usetype in (("df -h", "space"),
                             ("df -i", "inode")):
            output = utils.local(cmd)
            for i, line in enumerate(output.splitlines()):
                if i == 0:
                    header_line = line
                if line.startswith("/dev"):
                    pct_use = line.split()[-2]
                    if pct_use.endswith("%"):
                        pct = int(pct_use[:-1])
                        if pct > maxdisk["pct"]:
                            maxdisk = dict(pct=pct,
                                           type=usetype,
                                           detail="\n".join((header_line,
                                                             line)))
        return maxdisk

    # get num active tasks
    from celery.worker.control.builtins import dump_active
    num_active_tasks = len(dump_active(None)) # no panel needed

    return dict(maxdisk=_maxdisk(),
                uptime=get_uptime(),
                loadavg_curr=psi.loadavg()[0],
                num_active_tasks=num_active_tasks)
