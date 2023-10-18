import logging
import argparse
import rpyc
import rpyc.utils.server

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)  # read from env. var.

    parser = argparse.ArgumentParser(prog='Deregister')
    parser.add_argument('-n', '--name')
    args = parser.parse_args()

    try:
        conn = rpyc.connect('localhost', 1010, keepalive=True)
        conn.root.deregister_v1(args.name)
    finally:
        logging.info("deregistered")
