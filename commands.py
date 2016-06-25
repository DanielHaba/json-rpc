import subprocess
import urllib.request


def echo(message):
    return message

#Very unsafe
def shell(command):
    return str(subprocess.check_output(command, shell = True), "UTF-8")

def terminal(directory = ""):
    return subprocess.call("gnome-terminal %s" % directory)

def download(url, to):
    urllib.request.urlretrieve(url, to)
