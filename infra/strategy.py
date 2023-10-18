import logging
import time
import datetime
import signal
import argparse

import schedule
import rpyc

from const import *
if test_mode:
    sched = schedule.every(15).seconds
else:
    sched = schedule.every().minutes.at(":00")


class Strategy:
    def __init__(self, trader_port, signals_port, name):
        self.name = name
        self.signals_port = signals_port
        self.signals_conn = []
        self.trader_port = trader_port
        self.trader_conn = None

    def collect_point(self, signal_index, timestamp):
        signal, signal_timestamp = None, None
        conn_error = False

        retries = 0
        while ((signal_timestamp == None or abs(timestamp - signal_timestamp) > TIME_TOLERANCE)
               and retries < RETRIES_LIMIT):

            if conn_error:
                try:
                    port = self.signals_port[signal_index]
                    self.signals_conn[signal_index] = rpyc.connect(
                        'localhost', port, keepalive=True)
                except ConnectionRefusedError:
                    logging.error("reconnecting: connection refused")
                else:
                    logging.info("reconnecting: reconnected successfully")
                    conn_error = False

            try:
                conn = self.signals_conn[signal_index]
                signal, signal_timestamp = conn.root.get_signal_v1()
            except EOFError:
                logging.error("lost connection to signal: reconnecting")
                conn_error = True

            retries += 1
            time.sleep(1)

        if retries >= RETRIES_LIMIT:
            return None

        return signal

    def submit_decision(self, decision, timestamp):
        retries = 0
        conn_error = False
        submitted = False
        while retries < RETRIES_LIMIT and not submitted:
            if conn_error:
                try:
                    logging.info("attempting reconnection to trader")
                    self.trader_conn = rpyc.connect(
                        'localhost', self.trader_port, keepalive=True)
                except ConnectionRefusedError:
                    logging.error("reconnecting: connection to trader refused")
                else:
                    logging.info(
                        "reconnecting: reconnected to trader successfully")
                    conn_error = False

            try:
                self.trader_conn.root.submit_decision_v1(
                    (decision, timestamp), self.name)
            except EOFError:
                logging.error("lost connection to trader")
                conn_error = True
            else:
                logging.info("decision submitted")
                submitted = True

            time.sleep(1)

    def process(self):
        timestamp = time.time()
        signals = []

        for signal_index, _ in enumerate(self.signals_conn):
            signal = self.collect_point(signal_index, timestamp)

            if signal == None:
                logging.error("failed to collect signal")
                return

            signals.append(signal)

        logging.info("collected signals: " + str(signals))

        decision = sum(signals)
        logging.info("decision: " + str(decision))

        self.submit_decision(decision, timestamp)

    def signal_handler(self, sig, frame):
        logging.info("received signal: shutting down")
        if self.trader_conn != None:
            self.trader_conn.root.deregister_v1(self.name)

        exit(0)

    def run(self):
        logging.basicConfig(level=logging.INFO)  # read from env. var.

        logging.info("connecting to signal(s)")

        for port in self.signals_port:
            logging.info("connecting to localhost:" + str(port))
            conn = rpyc.connect('localhost', port, keepalive=True)
            conn._config['sync_request_timeout'] = 10
            self.signals_conn.append(conn)

        logging.info("connecting to trader")
        self.trader_conn = rpyc.connect('localhost', 1010, keepalive=True)
        self.trader_conn._config['sync_request_timeout'] = 10

        registered = self.trader_conn.root.register_v1(self.name)
        if not registered:
            logging.fatal("registration rejected by trader")
            exit(1)

        signal.signal(signal.SIGINT, self.signal_handler)

        logging.info("starting strategy")
        sched.do(self.process)
        while True:
            schedule.run_pending()
            time.sleep(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='Strategy')
    parser.add_argument('-tp', '--trader-port')
    parser.add_argument('-sp', '--signal-ports')
    parser.add_argument('-n', '--name')
    args = parser.parse_args()

    signal_ports = map(int, args.signal_ports.split(','))
    strategy = Strategy(args.trader_port, signal_ports, args.name)
    strategy.run()
