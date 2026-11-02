"""Best-effort process-local noise counts, never an audit/history substitute."""
from array import array
from datetime import datetime, timezone
import math
import os
from threading import Lock
import time
from uuid import uuid4

from .paths import SIGNATURES

WINDOW_SECONDS = 60
MAX_COUNT = (1 << 63) - 1
_INDEX = {key: index for index, key in enumerate(SIGNATURES)}


class NoiseCounters:
    __slots__ = ('_clock', '_pid', '_token', '_started', '_window', '_total',
                 '_current', '_previous', '_lost', '_lock')

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._pid = os.getpid()
        self._token = str(uuid4())
        self._started = datetime.now(timezone.utc).isoformat()
        self._window = self._window_now()
        self._total = array('Q', [0] * len(SIGNATURES))
        self._current = array('Q', [0] * len(SIGNATURES))
        self._previous = array('Q', [0] * len(SIGNATURES))
        self._lost = False
        self._lock = Lock()

    def _window_now(self):
        now = self._clock()
        if not math.isfinite(now) or now < 0:
            raise ValueError('SCAN_COUNTER_CLOCK')
        return int(now // WINDOW_SECONDS)

    def after_fork(self):
        # Called in the single-threaded child before worker threads can start.
        self.__init__(clock=self._clock)

    def _roll(self):
        window = self._window_now()
        if window < self._window:
            raise ValueError('SCAN_COUNTER_CLOCK')
        if window != self._window:
            self._previous = self._current if window == self._window + 1 else array('Q', [0] * len(SIGNATURES))
            self._current = array('Q', [0] * len(SIGNATURES))
            self._window = window

    def note(self, signature):
        if type(signature) is not str or signature not in _INDEX:
            return False
        if os.getpid() != self._pid:
            return False
        if not self._lock.acquire(blocking=False):
            self._lost = True
            return False
        try:
            self._roll()
            index = _INDEX[signature]
            for counts in (self._total, self._current):
                if counts[index] == MAX_COUNT:
                    self._lost = True
                else:
                    counts[index] += 1
            return True
        except Exception:
            self._lost = True
            return False
        finally:
            self._lock.release()

    def mark_incomplete(self):
        self._lost = True

    def snapshot(self):
        common = {'scope': 'process', 'processId': self._pid, 'processToken': self._token,
                  'sinceUtc': self._started, 'historyIncomplete': True,
                  'windowSeconds': WINDOW_SECONDS, 'configuredKeyLimit': len(SIGNATURES)}
        if os.getpid() != self._pid:
            return {**common, 'processId': os.getpid(), 'available': False,
                    'countIsLowerBound': True}
        if not self._lock.acquire(blocking=False):
            return {**common, 'available': False, 'countIsLowerBound': True}
        try:
            self._roll()
            return {**common, 'available': True, 'countIsLowerBound': self._lost,
                    'counts': {key: {'total': self._total[index], 'current': self._current[index],
                                     'previous': self._previous[index]}
                               for index, key in enumerate(SIGNATURES)}}
        except Exception:
            self._lost = True
            return {**common, 'available': False, 'countIsLowerBound': True}
        finally:
            self._lock.release()


COUNTERS = NoiseCounters()
if hasattr(os, 'register_at_fork'):
    os.register_at_fork(after_in_child=COUNTERS.after_fork)
