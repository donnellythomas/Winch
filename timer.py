from time import time


class Timer:
    def __init__(self):
        self._start_time = None
        
    def start(self): # Can only be started once until stopped
        if self._start_time is None:
            self._start_time = time()
        
    def stop(self):
        if self._start_time is None:
            return 0
        elapsed_time = time()-self._start_time
        self._start_time = None
        return elapsed_time
    
    def reset(self):
        elapsed_time = self.check_time()
        self._start_time = time()
        return elapsed_time
        
    
    def check_time(self):
        if self._start_time is None:
            return 0
        elapsed_time = time()-self._start_time
        return elapsed_time