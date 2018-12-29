import sys
sys.setrecursionlimit(100000)

import os

from rq import Worker, Queue, Connection
from cache import instance

listen = ['high', 'default', 'low']

if __name__ == '__main__':
    with Connection(instance()):
        worker = Worker(map(Queue, listen))
        worker.work()
