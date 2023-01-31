import os
import sys
from .strace import STrace, STraceRecord
from .strace import parse_record


SHOW_COLLECTION = 1 << 1
SHOW_AVERAGE = 2 << 1
SHOW_TOTAL = 3 << 1
SHOW_ALL = SHOW_COLLECTION | SHOW_AVERAGE | SHOW_TOTAL


class Benchmark:
    # Input file data begins after
    MAX_HEADER_LINES = 3

    def __init__(self, command="", passes=2, setup="", teardown=""):
        """
        A benchmark record
        :param command: to execute
        :param passes: times to execute command
        :param setup: to execute before command
        :param teardown: to execute after command
        """
        self.result = []
        self.command = command
        self.passes = passes
        self.count = 0

        if self.passes < 1:
            self.passes = 1

        if self.command:
            for i in range(self.passes):
                if self.passes > 1:
                    print(f"Pass [{i+1}/{passes}]: ", end="")
                print(f"Running `{self.command}`")
                data = STrace(command, setup=setup, teardown=teardown).records
                self.count += len(data)
                self.result.append(data)

    def save(self, filename, clobber=False):
        """
        Write benchmark data to a file
        :param filename: output file path
        :param clobber: toggle overwriting the output file
        """
        if clobber and os.path.exists(filename):
            raise FileExistsError(filename)

        filename = os.path.abspath(filename)
        print(f"Writing {filename}")
        with open(filename, "w+") as fp:
            print(f"# {len(self.result)}", file=fp)
            print(f"# {self.command}", file=fp)
            print("", file=fp)
            for t, data in enumerate(self.result):
                print(f"# {t}", file=fp)
                for rec in data:
                    rec_fmt = f"{rec.name} {rec.calls} {rec.seconds:.6f} {rec.min:.6f} {rec.max:.6f} {rec.usecs_call}"
                    print(rec_fmt, file=fp)

    def load(self, filename):
        """
        Read benchmark data from a file
        :param filename: input file path
        """
        result = []
        filename_s = os.path.basename(filename)

        with open(filename, "r") as fp:
            collection_max = int(fp.readline().split("#")[1]) or 0
            command = fp.readline().split("#")[1] or "UNKNOWN"

        if not collection_max:
            raise ValueError(f"{filename_s} has no collections!")

        if command == "UNKNOWN":
            print(f"{filename_s}: no command stored", file=sys.stderr)

        print(f"{filename_s}: {collection_max} collection(s)")
        print(f"{filename_s}: command: {command}")
        data_count = 0
        start_collection = 0
        data = []

        fp = open(filename, "r")
        for i, line in enumerate(fp.readlines()):
            # Skip header information
            if i < self.MAX_HEADER_LINES:
                continue

            # Begin collecting records
            if not start_collection and line.startswith("#") and i == self.MAX_HEADER_LINES:
                start_collection = 1
                continue

            # Append collected records to result list
            if line.startswith("#") and start_collection:
                result.append(data)
                data = []
                continue

            # Store record
            rec = parse_record(line)
            data.append(rec)
            data_count += 1

        result.append(data)
        fp.close()
        self.count = data_count
        print(f"{filename}: {data_count} records")
        self.result = result

    def diff_record(self, a, b):
        """
        Calculate the difference between records a and b
        :param a: baseline StraceRecord
        :param b: comparison StraceRecord
        :return: StraceRecord containing the difference between a and b
        """
        r_calls = b.calls - a.calls
        r_seconds = b.seconds - a.seconds
        r_min = b.min - a.min
        r_max = b.max - a.max
        r_usecs_call = b.usecs_call - a.usecs_call

        return STraceRecord(a.name, r_calls, r_seconds, r_min, r_max, r_usecs_call)

    @property
    def total(self):
        """Sum of all records"""
        result = dict(name="Total", calls=0, usecs_call=0, min=0, max=0, seconds=0)
        for trace in self.result:
            for rec in trace:
                result["calls"] += rec.calls
                result["usecs_call"] += rec.usecs_call
                result["max"] += rec.max
                result["min"] += rec.min
                result["seconds"] += rec.seconds

        return STraceRecord(**result)

    @property
    def average(self):
        """Average of all records"""
        result = dict(name="Average", calls=0, usecs_call=0, min=0, max=0, seconds=0)
        total = self.total
        result["calls"] = total.calls
        result["usecs_call"] = int(total.usecs_call / self.count)
        result["max"] = int(total.max / self.count)
        result["min"] = int(total.min / self.count)
        result["seconds"] = int(total.seconds / self.count)

        return STraceRecord(**result)

    @staticmethod
    def get_winner(data):
        result = ""
        if data.usecs_call == 0:
            result = "same"
        elif data.usecs_call < 0:
            result = "faster"
        else:
            result = "slower"
        return result

    @staticmethod
    def get_percent(a, b):
        if (b.usecs_call - a.usecs_call) < 0:
            percent = (a.usecs_call - b.usecs_call) / a.usecs_call * 100
        else:
            percent = (b.usecs_call - a.usecs_call) / b.usecs_call * 100

        return percent

    def diff_show_record(self, title, a, b):
        abdiff = self.diff_record(a, b)
        fastest = self.get_winner(abdiff)
        percent = self.get_percent(a, b)
        if not a.calls or not b.calls:
            percent = 0
            fastest = ""

        print(f"{title}:")
        print(f"\tcalls: {a.calls:10d} {b.calls:10d} {abdiff.calls:+10d}")
        print(f"\t\u00B5s/call: {a.usecs_call:8d} {b.usecs_call:10d} {abdiff.usecs_call:+10d} {percent:10.2f}% {fastest}")

    def diff_total(self, b):
        """
        Display the total difference between total and b.total
        :param b:
        """
        total_a = self.total
        total_b = b.total
        self.diff_show_record("Total", total_a, total_b)

    def diff_average(self, b):
        """
        Display the average difference between result and b.average
        :param b:
        """
        average_a = self.average
        average_b = b.average
        self.diff_show_record("Average", average_a, average_b)

    @staticmethod
    def normalize_results(a, b):
        def extract(objs, name):
            for x in objs:
                if x.name == name:
                    return x

        x1_result = []
        x2_result = []
        nop = dict(name="", calls=0, usecs_call=0, min=0, max=0, seconds=0)

        for left, right in zip(a.result, b.result):
            empty = nop.copy()
            keys_a = set(x.name for x in left)
            keys_b = set(x.name for x in right)
            keys_missing = keys_b ^ keys_a
            x1_missing = []
            x2_missing = []
            x1_data = []
            x2_data = []

            for x in sorted(keys_a):
                if x in keys_missing:
                    x2_missing.append(x)
                value = extract(a.result[0], x)
                if not value:
                    continue
                x1_data.append(value)

            for x in sorted(keys_b):
                if x in keys_missing:
                    x1_missing.append(x)
                value = extract(b.result[0], x)
                x2_data.append(value)

            for x in sorted(x1_missing):
                empty["name"] = x
                x1_data.append(STraceRecord(**empty))

            for x in sorted(x2_missing):
                empty["name"] = x
                x2_data.append(STraceRecord(**empty))

            x1_result.append(sorted(x1_data))
            x2_result.append(sorted(x2_data))
        return zip(x1_result, x2_result)

    def diff(self, b, mode=SHOW_ALL):
        """
        Display the difference between stored result and b
        :param b: list of StraceRecords
        :param mode: flag to handle various output modes (not implemented)
        """
        a = self
        for i, (left, right) in enumerate(self.normalize_results(a, b)):
            print(f"\nCOLLECTION {i+1}\n")
            for x1, x2 in zip(left, right):
                self.diff_show_record(x1.name, x1, x2)