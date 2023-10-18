import threading
import logging
import argparse
import time
import statistics

import schedule
import rpyc
import rpyc.utils.server


from const import *
if test_mode:
    sched = schedule.every(15).seconds
else:
    sched = schedule.every().minutes.at(":00")


class Trader:
    def __init__(self):
        self.mutex = threading.Lock()
        self.registered = {}

    def deregister(self, strategy):
        self.mutex.acquire()
        if strategy in self.registered:
            del self.registered[strategy]
        self.mutex.release()

    def register(self, strategy):
        self.mutex.acquire()
        if strategy in self.registered:
            logging.error("double registration: rejecting")
            self.mutex.release()
            return False

        self.registered[strategy] = None
        self.mutex.release()
        logging.info("registered " + str(strategy))
        return True

    def submit_decision(self, decision, strategy):
        self.mutex.acquire()
        if strategy not in self.registered:
            logging.info("implicit registration: " + str(strategy))

        logging.info(str(strategy) + " submitted " + str(decision[0]))
        self.registered[strategy] = decision
        self.mutex.release()

    def compute_median(self):
        if len(self.registered) == 0:
            logging.error("median: no strategies registered")
            return None

        # ensure we have recent data
        timestamp = time.time()

        decisions = []

        self.mutex.acquire()
        for strategy, value in self.registered.items():
            if value == None:
                logging.debug("median: cannot compute, no data submitted by " + str(strategy))
                self.mutex.release()
                return None

            (decision, decision_timestamp) = value
            if abs(timestamp - decision_timestamp) > TIME_TOLERANCE:
                logging.debug("median: cannot compute, stale data for " + str(strategy))
                self.mutex.release()
                return None

            decisions.append(decision)
        self.mutex.release()

        return statistics.median(decisions)


    def process_decisions(self):
        median = self.compute_median()
        retries = 0

        while median == None and retries < RETRIES_LIMIT:
            time.sleep(1)
            logging.info("median: retrying to compute")
            median = self.compute_median()
            retries += 1

        if median != None:
            logging.info("median: " + str(median))


    def run(self):
        logging.info("starting T2")
        sched.do(self.process_decisions)
        while True:
            schedule.run_pending()
            time.sleep(1)


@rpyc.service
class TraderService(rpyc.Service):
    def __init__(self, trader):
        self.trader = trader

    @rpyc.exposed
    def register_v1(self, strategy):
        return self.trader.register(strategy)

    @rpyc.exposed
    def submit_decision_v1(self, decision, strategy):
        self.trader.submit_decision(decision, strategy)

    @rpyc.exposed
    def deregister_v1(self, strategy):
        self.trader.deregister(strategy)


def main(port):
    logging.basicConfig(level=logging.INFO)  # read from env. var.
    logging.info("starting trader")

    trader = Trader()
    threading.Thread(target=trader.run, daemon=True).start()

    logging.info("listening to RPCs")
    server = rpyc.utils.server.ThreadedServer(TraderService(trader), port=port)
    server.start()
    logging.info("shutting down")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='Trader')
    parser.add_argument('-p', '--port')
    args = parser.parse_args()
    main(args.port)
