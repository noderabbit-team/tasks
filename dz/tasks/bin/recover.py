#!/usr/bin/env python
import sys

from dz.tasks import recover_appserver

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "recover_appserver":
        print "Usage: recovery.py recover_appserver <dead_ip> [project_id]"
        sys.exit(1)

    dead_ip = sys.argv[2]
    args = [-1, dead_ip]
    if len(sys.argv) > 3:
        project_id = int(sys.argv[3])
        args.append(project_id)

    r = recover_appserver.apply_async(args=args)
    print "Completed: ", r.wait()
