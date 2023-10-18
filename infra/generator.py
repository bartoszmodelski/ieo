import time
import datetime
import threading
import argparse
import logging
import sys

import numpy as np
import schedule
import rpyc
import rpyc.utils.server

from const import *
if test_mode:
    sched = schedule.every(15).seconds
else:
    sched = schedule.every().minutes.at(":00")


class Signal:
    def __init__(self):
        self.signal = (None, None)
        self.mutex = threading.Lock()

    def generate(self):
        self.mutex.acquire()
        self.signal = np.random.uniform(), time.time()
        self.mutex.release()

        time_str = str(datetime.datetime.fromtimestamp(self.signal[1]))
        signal_str = str(self.signal[0])
        logging.info("generated signal: " + signal_str + ", ts: " + time_str)

    def get(self):
        self.mutex.acquire()
        value = self.signal
        self.mutex.release()
        return value

    def run(self):
        logging.info("starting T2")
        sched.do(self.generate)
        while True:
            schedule.run_pending()
            time.sleep(1)


@rpyc.service
class GeneratorService(rpyc.Service):
    def __init__(self, signal):
        self.signal = signal

    @rpyc.exposed
    def get_signal_v1(self):
        return self.signal.get()


def main(port):
    logging.basicConfig(level=logging.INFO)  # read from env. var.
    logging.info("starting signal generator")

    signal = Signal()
    threading.Thread(target=signal.run, daemon=True).start()

    logging.info("listening to RPCs")
    server = rpyc.utils.server.ThreadedServer(
        GeneratorService(signal), port=port)
    server.start()
    logging.info("shutting down")
    sys.exit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='Generator')
    parser.add_argument('-p', '--port')
    args = parser.parse_args()
    main(args.port)
