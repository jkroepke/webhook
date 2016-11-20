#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#  webhook.py <bind ip> <bind port>
#
#   Jan-Otto Kröpke, Apache 2.0 Licence
#
# When triggered via a HTTP request, execute a command.
#
# HTTP GET and POST requests are supported. If you need more verbs or need
# to disable one of the two, edit the script. The request should have a
# "key" argument (via query string if GET, or body (urlencoded form) if POST),
# and the trigger is only activated if the key matches what's given on the
# command line.
#
# The command given on the commandline is executed (along with any arguments
# if given). If the command exits successfully (exit status 0), HTTP response
# code 200 is returned to the user, otherwise 500 is returned.
#
# Host is usually 0.0.0.0 (unless you want to listen only on a specific
# address/interface), port is the TCP port to listen on, key is the key
# that the client will have to supply to authorize the trigger, and the
# command is what should be executed.


import struct, fcntl, os, sys, json
import BaseHTTPServer
import urlparse
import subprocess
import logging
import yaml

try:  # py3
    from shlex import quote
except ImportError:  # py2
    from pipes import quote

class WebServer(BaseHTTPServer.HTTPServer):
    def __init__(self, *args, **kwargs):
        BaseHTTPServer.HTTPServer.__init__(self, *args, **kwargs)
        # Set FD_CLOEXEC flag
        flags = fcntl.fcntl(self.socket.fileno(), fcntl.F_GETFD)
        flags |= fcntl.FD_CLOEXEC
        fcntl.fcntl(self.socket.fileno(), fcntl.F_SETFD, flags)

class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    def do_POST(self):
        parsed_path = urlparse.urlparse(self.path)
        parsed_qs   = urlparse.parse_qs(parsed_path.query)

        logging.debug('Called URL: %s' % parsed_path.path)
        logging.debug('Parsed QS: %s' % parsed_qs)

        if not parsed_path.path in config:
            self.send_error(404, 'Not found')
            return

        if not 'command' in config[parsed_path.path]:
            self.send_error(503)
            return

        try:
            if 'workdir' in config[parsed_path.path]:
                workdir = config[parsed_path.path]['workdir']
            else:
                workdir = '/tmp'

            command = [config[parsed_path.path]['command']]

            if 'arguments' in config[parsed_path.path]:
                for arg, default in config[parsed_path.path]['arguments'].items():
                    if arg in parsed_qs:
                        command.append(quote(parsed_qs[arg][0]))
                    else:
                        command.append(default)

            logging.debug('Use work: %s' % workdir)
            logging.debug('Use command: %s' % ' '.join(command))

            retval = subprocess.call(' '.join(command), cwd=workdir, shell=True)

        except subprocess.CalledProcessError, e:
            logging.error('Error on CMD: %s' % e.output)
            retval = e.returncode

        if retval == 0:
            self.send_response(200)
        else:
            self.send_error(500)

        self.wfile.close()
        return

    def do_GET(self):
        self.send_error(400, 'Bad Request')
        return

if __name__ == '__main__':
    config_file = '/etc/webhook/config.yaml'
    log_file    = '/var/log/webhook.log'


    if len(sys.argv) < 3:
        sys.stderr.write('Usage: %s <host> <port> ...\n' % sys.argv[0])
        sys.exit(-1)

    if not os.path.exists(config_file):
        sys.stderr.write('%s does not exits ...\n' % config_file)
        logging.critical('%s does not exits ...\n' % config_file)
        sys.exit(-1)

    if not os.access(config_file, os.R_OK):
        sys.stderr.write('Can not read %s ...\n' % config_file)
        logging.critical('Can not read %s ...\n' % config_file)
        sys.exit(-1)

    config = yaml.load(open(config_file).read())

    server = WebServer((sys.argv[1], int(sys.argv[2])), RequestHandler)
    logging.basicConfig(filename=log_file,level=logging.DEBUG)

    try:
        server.serve_forever()
    except:
        server.socket.close()

    sys.exit(0)