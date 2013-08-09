#!/usr/bin/env python

import os
import sys
import supervisor.xmlrpc
import xmlrpclib

from cement.core import backend, foundation, controller, handler

OK, WARNING, CRITICAL, UNKNOWN = range(4)
SHUTDOWN, RESTARTING, RUNNING, FATAL = range(-1, 3)

# set the home environment variable for cement
os.environ['HOME'] = '/home'

class CheckSupervisorController(controller.CementBaseController):
    status_map = {'SHUTDOWN': SHUTDOWN, 'STOPPED': RESTARTING, 'RUNNING': RUNNING, 'FATAL': FATAL}

    class Meta:
        label = 'base'
        description = 'Checks the status of a local supervisor or supervisor process'

        config_defaults = dict(socket='unix:///tmp/supervisor.sock',
                               group='')

        arguments = [
            (['-s', '--socket'], dict(action='store', help='Path to the unix socket for supervisor communication.')),
            (['-g', '--group'], dict(action='store', help='Name of the group of supervisor processes to monitor.'))
        ]

    @controller.expose(hide=False, aliases=['monitor'])
    def default(self):
        # setup the proxy for talking to supervisor
        socketpath = self.config.get('controller.base', 'socket')

        try:
            proxy = xmlrpclib.ServerProxy('http://127.0.0.1', transport=supervisor.xmlrpc.SupervisorTransport(None, None, serverurl=socketpath))
            state_info = proxy.supervisor.getState()
        except:
            print('CRITICAL : Unable to connect to supervisor socket')
            sys.exit(CRITICAL)

        # check supervisor in general
        status_code = state_info['statecode']
        status_message = 'Supervisor'

        # if we got a process group name, check its status
        group_name = self.config.get('controller.base', 'group')

        if (group_name != ''):
            try:
                # pull all the processes
                all_process_info = proxy.supervisor.getAllProcessInfo()

                # filter by group
                group_process_statuses = [self.status_map[process['statename']] for process in all_process_info if process['group'] == group_name]

                # if none in group, group is not running
                if (len(group_process_statuses) == 0):
                    status_code = SHUTDOWN
                else:
                    # sort the status codes from worst to best
                    group_process_statuses.sort()

                    # pop the worst off and return it
                    status_code = group_process_statuses[0]

                status_message = 'Process Group %s' % group_name

            except:
                print('CRITICAL : Error getting status of processes in group %s' % group_name)
                sys.exit(CRITICAL)

        # exit with the right numeric status and a message
        if (status_code == RUNNING):
            print("OK : %s is running" % status_message)
            sys.exit(OK)

        if (status_code == FATAL or status_code == SHUTDOWN):
            print('CRITICAL : %s has a fatal error or has shutdown' % status_message)
            sys.exit(CRITICAL)

        if (status_code == RESTARTING):
            print('WARNING : %s is restarting or stopped' % status_message)
            sys.exit(WARNING)

        print('UNKNOWN : Cannot process supervisor status')
        sys.exit(UNKNOWN)

app = foundation.CementApp('check_supervisor', base_controller=CheckSupervisorController, arguments_override_config=True)

try:
    app.setup()
    app.run()
finally:
    app.close()
