#!/usr/bin/python3
import lib
import commands
import signal
import argparse


def on_interrupt(signum, frame):
    lib.log_a("Interrupted")
    server.stop()
    server.join()

signal.signal(signal.SIGINT, on_interrupt)


parser = argparse.ArgumentParser(description = "json-rpc server", epilog = "by Daniel Haba")


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





server = lib.Server(args.port)
server.commands.load(commands)




server.start()
server.join()
