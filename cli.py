#!/usr/bin/python3
import lib
import ast
import re
import time
import argparse



pattern = re.compile("^\s*([\w.]+)\s*\((.*)\)\s*$")


parser = argparse.ArgumentParser(description = "json-rpc cli client", epilog = "by Daniel Haba")

parser.add_argument("host", help = "Server host", type = str)
parser.add_argument("port", help = "Server port", type = int, default = lib.DEFAULT_PORT, nargs = "?")
parser.add_argument("-l", "--log-level", help = "Log level", type = str,
                    choices=["assert", "error", "warning", "message", "debug"], default = "message")

args = parser.parse_args()


lib.set_log_level({
    "assert": lib.LOG_ASSERT,
    "error": lib.LOG_ERROR,
    "warning": lib.LOG_WARNING,
    "message": lib.LOG_MESSAGE,
    "debug": lib.LOG_DEBUG
}[args.log_level])






client = lib.Client(args.host, args.port)

while not client.connect():
    time.sleep(5)


while True:
    command = input(">")

    if command == "exit":
        break

    matches = re.match(pattern, command)

    if matches is None:
        lib.log_e("Invalid syntax")

    else:
        method = matches.group(1)
        params = ast.literal_eval("[%s]" % matches.group(2))

        lib.log_d("Calling %s(%s)" % (method,params))
        client.call(method, params)




client.disconnect()
