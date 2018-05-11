"""A collection of useful utility functions to use with
slitherd.automon.

pidperf: Get performance information about the specified pid
run: Run a command in a shell with control over stdin, stdout
and stderr.
run_and_monitor: Run a command in a shell with control over stdin, stdout
and stderr and monitor the thread or process.
"""
import time
import os
import logging
import psutil
from collections import namedtuple
from DataPower import DataPower

__all__ = [
    "pidperf"
]


READINGS = [
    "name",
    "cpu_times",
    "cpu_percent",
    "create_time",
    "ppid",
    "status",
    "memory_info",
    "num_threads",
    "num_handles",
    "num_ctx_switches"
]

perf_reading = namedtuple(
    "perf_reading",
    READINGS,
)
def pidperf(pid: int=os.getpid()):
    proc = psutil.Process(pid)
    reading = proc.as_dict(
        attrs=READINGS,
        ad_value=None,
    )
    print(reading)
    return reading

def hello():
    print("hello, world @ {}!".format(time.time()))

def follow(filename, delay: float=0.1):
    with open(filename, "r") as fp:
        while True:
            line = fp.readline()
            if not line:
                time.sleep(0.1)
                continue
            yield line

def get_status(sleep_delay=10):
    while True:
        try:
            dp = DataPower(
                hostname="127.0.0.1",
                username="admin",
                password="admin",
                xml_mgmt_port=15550,
                verify=False,
            )
            print(
                dp.soma.get_status(
                    "CPUUsage"
                ).text
            )
        except:
            logging.getLogger("slither.exception").exception("An unhandled exception occurred")
            raise
        time.sleep(sleep_delay)
