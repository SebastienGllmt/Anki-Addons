"""
Simulates a stopwatch

Copyright: Sebastien Guillemot 2017 <https://github.com/SebastienGllmt>

License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
"""

import time

class Stopwatch:

    def __init__(self):
        self.counter = [0,0]

    def get_time(self):
        if self.is_running():
            now = time.time()
            return self.counter[0] + (now - self.counter[1])
        else:
            return self.counter[0]

    def start(self):
        if self.counter[1] == 0:
            self.counter[1] = time.time()

    def stop(self):
        if self.counter[1] == 0:
            return
        now = time.time()
        self.counter[0] += (now - self.counter[1])
        self.counter[1] = 0

    def reset(self):
        self.counter = [0,0]

    def is_running(self):
        return self.counter[1] > 0