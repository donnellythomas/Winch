from time import time

class TimerError(Exception):
    """Custom exception used to report errors in use of Timer class"""
class Timer:
    def __init__(self):
        self._start_time = None
        
    def start(self):
        if self._start_time is not None:
            raise TimerError("Timer is running. Use .stop() to stop it")
        self._start_time = time()
        
    def stop(self):
        if self._start_time is None:
            raise TimerError("Timer is not running. Use .start() to start it")
        elapsed_time = time()-self._start_time
        self._start_time = None
        return elapsed_time
    
    def reset(self):
        self._start_time = time()
    
    def check_time(self):
        if self._start_time is None:
            return 0
        elapsed_time = time()-self._start_time
        return elapsed_time