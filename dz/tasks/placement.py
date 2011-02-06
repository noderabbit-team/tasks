"""

Intermediary Task, which will consider placement of an appserver process
on multiple appserver machines. Things to consider

  - which machines currently have the app deployed, ideally we should
    spread machines and not colocate all the appservers processes
    on the same machine.

  - what's the load of the machine, we'll need some monitoring agent
    tracking memory/cpu usage on the machines, and ideally try to
    allocate on the least used.

Should enrich/inject the machine id into the deploy message as a routing key.

"""
