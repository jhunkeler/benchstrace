import os
import re
import subprocess
import sys
import tempfile
from collections import namedtuple

KEYS = ["name", "calls", "seconds", "min", "max", "usecs_call"]
STraceRecord = namedtuple("STraceRecord", KEYS)


def find_program(name):
    syspath = os.environ.get("PATH", "")
    for x in syspath.split(":"):
        target = os.path.abspath(os.path.join(x, name))
        if os.path.exists(target):
            return target
    return ""


def parse_record(line):
    """
    Parse a single line from: strace -w -c
    :return: an StraceRecord
    """
    rec = line.split()
    data = dict(zip(*[KEYS, rec]))
    result = dict()
    for k, v in data.items():
        result[k] = v
        if k == "name":
            continue
        elif k == "calls" or k == "usecs_call":
            if "." in v:
                v = v[:v.find(".")]
            result[k] = int(v)
        else:
            result[k] = float(v)
    return STraceRecord(**result)


def parse_output(lines):
    """
    Parse all lines from: strace -w -c
    :return: a list of STraceRecords
    """
    result = []
    for i, line in enumerate(lines):
        if i < 2 or i > len(lines) - 3:
            continue
        result.append(parse_record(line))
    return result


class STrace:
    """Run strace command and parse statistical output
    """
    VERSION_RE = re.compile(r"strace.*version\s(?P<major>\d+)\.(?P<minor>\d+)\.?(?P<patch>\d+)?")
    NEED_VERSION = (6, 0, 0)

    def __init__(self, command="", setup="", teardown="", output_file=""):
        self.program = find_program("strace")
        self.command = command
        major, minor, _ = self.version
        if major < 6:
            raise RuntimeError(f"strace {major}.{minor} is too old. Install {self.NEED_VERSION}, or greater.")
        self.records = self.run(setup, teardown) or []

    def run(self, setup="", teardown=""):
        """
        Execute strace
        :param setup: command to execute before `self.command`
        :param teardown: command to execute after `self.command`
        :return: a list of STraceRecords
        """
        handle, tmpfile = tempfile.mkstemp()
        os.close(handle)
        command = ["strace", "-o", tmpfile, "-w", "-c", "-S", "name", "-U", "name,calls,time-total,time-min,time-max,time-avg"] + self.command.split(" ")

        if setup:
            proc_setup = subprocess.run(setup.split())
            if proc_setup.returncode:
                print(f"Warning: setup command failed ({proc_setup.returncode})", file=sys.stderr)

        proc = subprocess.run(command, stderr=open("/dev/null", "w"))
        if proc.returncode:
            print("Warning: non-zero exit ({proc.returncode})", file=sys.stderr)

        if teardown:
            proc_teardown = subprocess.run(teardown.split())
            if proc_teardown.returncode:
                print(f"Warning: teardown command failed ({proc_teardown.returncode})", file=sys.stderr)

        data = open(tmpfile, "r").read().splitlines()
        os.remove(tmpfile)
        return parse_output(data)

    @property
    def version(self):
        """Retrieve version number from strace
        :return: tuple containing major, minor, and patch version
        """
        command = ["strace", "--version"]
        proc = subprocess.run(command, capture_output=True)
        data = proc.stdout.decode().splitlines()
        match = re.match(self.VERSION_RE, data[0])
        if not match:
            return 0, 0, 0

        result = match.groupdict()
        if not result.get("patch"):
            result["patch"] = 0
        return int(result["major"]), int(result["minor"]), int(result["patch"])
