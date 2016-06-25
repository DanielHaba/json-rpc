import sys
import json
import select
import socket
import inspect
import threading
import traceback
import importlib




DEFAULT_BUFFER_SIZE = 4096
DEFAULT_PORT = 8338




LOG_ASSERT = 0
LOG_ERROR = 1
LOG_WARNING = 2
LOG_MESSAGE = 3
LOG_DEBUG = 4

__LOG_OUTPUT = {
    LOG_ASSERT: sys.stderr,
    LOG_ERROR: sys.stderr,
    LOG_WARNING: sys.stdout,
    LOG_MESSAGE: sys.stdout,
    LOG_DEBUG: sys.stdout,
}
__LOG_LEVEL = LOG_DEBUG
__LOG_LOCK = threading.Lock()



def log(level, message):
    if level <= __LOG_LEVEL:
        __LOG_LOCK.acquire()
        __LOG_OUTPUT[level].write("%s\n" %message)
        __LOG_LOCK.release()

def set_log_level(level):
    global __LOG_LEVEL
    __LOG_LEVEL = level

def get_log_level():
    return __LOG_LEVEL

def log_a(message):
    log(LOG_ASSERT, message)

def log_e(message):
    log(LOG_ERROR, message)

def log_w(message):
    log(LOG_WARNING, message)

def log_m(message):
    log(LOG_MESSAGE, message)

def log_d(message):
    log(LOG_DEBUG, message)







class Commands:
    def __init__(self):
        self.commands = {}
        self.lock = threading.Lock()

        self.register("help", lambda: self.help())
        self.register("import", lambda name: self.import_module(name))

    def register(self, name, handler):
        if self.exists(name):
            log_w("Overriding command %s" % name)
        else:
            log_d("Binding command %s" % name)

        self.lock.acquire()
        self.commands[name] = handler
        self.lock.release()

    def load(self, module):
        items = inspect.getmembers(module, inspect.isfunction)

        for item in items:
            self.register(item[0], item[1])


    def exists(self, name):
        self.lock.acquire()
        result = name in self.commands
        self.lock.release()
        return result

    def get(self, name):
        self.lock.acquire()
        result = self.commands[name]
        self.lock.release()
        return result

    def help(self):
        result = ""
        for name, func in self.commands.items():
            print("%s%s" % (name, func))
            result += "%s%s\n" % (name, inspect.signature(func))
        return result

    def import_module(self, name):
        importlib.import_module(name)
        self.load(sys.modules[name])
        return "Module %s loaded" % name

class Executor:
    def __init__(self, commands):
        self.commands = commands

    def call(self, name, arguments):
        if self.commands.exists(name):

            command = self.commands.get(name)
            log_d("Executing %s(%s)" % (name, arguments))

            return command(*arguments)

        else:
            raise RuntimeError("Command %s not found" % name)


class Server(threading.Thread):
    def __init__(self, port = DEFAULT_PORT):
        threading.Thread.__init__(self)
        self.socket = None
        self.port = port
        self.running = threading.Event()
        self.connections = []
        self.commands = Commands()
        self.commands.register("shutdown", lambda: self.stop())

    def run(self):
        try:
            address = (socket.gethostname(), self.port)
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind(address)
            self.socket.listen(5)
            self.running.set()

            log_m("Server startup %s:%u" % address)

        except socket.error as error:

            if self.socket:
                self.socket.close()
            self.socket = None

            log_e("Server startup failed (%s)" % error)
            return


        listen = [self.socket]
        while self.running.is_set():

            read, write, error = select.select(listen, [], [], 1.0)

            if not read and not write and not error:
                continue

            for sock in read:
                (client, address) = sock.accept()

                connection = Connection(self, client, address)
                connection.start()
                self.connections.append(connection)

        log_m("Closing connections...")
        for connection in self.connections:
            connection.join()

        log_m("Connections closed")
        self.connections.clear()
        self.socket.close()
        self.socket = None

        log_m("Server shutdown")

    def stop(self):
        log_m("Stopping server")
        self.running.clear()

class Connection(threading.Thread):
    def __init__(self, server, socket, address):
        threading.Thread.__init__(self)
        self.server = server
        self.socket = socket
        self.address = address
        self.executor = Executor(server.commands)

    def run(self):
        log_m("Connected to %s:%u" % self.address)

        while True:
            data = self.socket.recv(DEFAULT_BUFFER_SIZE)
            size = len(data)

            if not data:
                break

            log_m("Received %ubytes from %s:%u" % (size, self.address[0], self.address[1]))
            log_d(data)

            id = None
            result = None
            error = None

            try:
                request = json.loads(str(data, "UTF-8"))

                if not "id" in request:
                    raise ValueError("'id' is required")

                if not "method" in request:
                    raise ValueError("'method' is required")

                # throws error when params are empty
                # if not "params" in request:
                #     raise ValueError("'params' are required")

                if not isinstance(request["method"], str):
                    raise TypeError("'method must be a string'")

                if not isinstance(request["params"], list):
                    raise TypeError("'params' must be a array")

                id = request["id"]
                result = self.executor.call(request["method"], request["params"])



            except BaseException as e:
                log_e(traceback.format_exc())
                error = str(e)


            data = bytes(json.dumps({
                "id": id,
                "result": result,
                "error": error,
            }), "UTF-8")

            size = self.socket.send(data)
            log_m("Sent %ubytes to %s:%u" %(size, self.address[0], self.address[1]))
            log_d(data)

        log_m("Disconnected from %s:%u" % self.address)

class Client:
    def __init__(self, host, port = DEFAULT_PORT):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = port
        self.connected = threading.Event()
        self.last_id = None

    def connect(self):

        if self.connected.is_set():
            log_w("Already connected to %s:%u" % (self.host, self.port))
            return True

        try:
            log_m("Connecting to %s:%u..." % (self.host, self.port))
            self.socket.connect((self.host, self.port))
            self.connected.set()
            self.last_id = 0
            log_m("Connected")
            return True


        except socket.error:
            log_w("Cannot connect to %s:%u" % (self.host, self.port))
            return False

    def disconnect(self):
        if not self.connected.is_set():
            log_w("Not connected")
            return True

        else:
            self.socket.close()
            self.connected.clear()
            self.last_id = None
            log_m("Disconnected")
            return True

    def call(self, method, params):

        if not self.connected:
            raise RuntimeError("Not connected")

        if not method:
            raise ValueError("'method' is required")

        if not isinstance(method, str):
            raise TypeError("'method must be a string'")

        if not isinstance(params, list):
            raise TypeError("'params' must be a array")


        self.last_id += 1

        data = bytes(json.dumps({

            "id": self.last_id,
            "method": method,
            "params": params,

        }), "UTF-8")

        size = self.socket.send(data)
        log_d("Sent %ubytes to %s:%u" % (size, self.host, self.port))

        data = self.socket.recv(DEFAULT_BUFFER_SIZE)
        log_d("Received %ubytes from %s:%u" % (size, self.host, self.port))

        data = json.loads(str(data, "UTF-8"))

        if not data["id"] == self.last_id:
            log_e("Wrong response")
            return False

        if data["result"]:
            log_m(data["result"])

        elif data["error"]:
            log_e(data["error"])

        return True
