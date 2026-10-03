"""Windowless logging, per-data-directory lock and temporary processing wake lock."""
import ctypes, logging, logging.handlers, os, threading
from pathlib import Path

class InstanceLock:
    def __init__(self,path):
        self.file=Path(path).open('a+b');self.file.seek(0);self.file.write(b'0');self.file.flush();self.file.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:self.file.close();raise RuntimeError('This Studio data directory is already open. No second dashboard started.')

class LogStream:
    def __init__(self,logger):self.logger=logger
    def write(self,text):
        if text.strip():self.logger.info(text.rstrip())
    def flush(self):pass

def logs(directory):
    Path(directory).mkdir(parents=True,exist_ok=True)
    logger=logging.getLogger('studio-background');logger.setLevel(logging.INFO)
    handler=logging.handlers.RotatingFileHandler(Path(directory)/'dashboard.log',maxBytes=4*1024*1024,backupCount=4,encoding='utf-8')
    logger.addHandler(handler);return LogStream(logger)

def prevent_sleep(engine):
    """One thread owns and clears ES_SYSTEM_REQUIRED. The display may sleep."""
    if os.name!='nt':return
    def monitor():
        enabled=False
        try:
            while not engine.stop.wait(3):
                with engine.store.lock:busy=any(j['status']=='running' for j in engine.store.db['jobs'].values())
                if busy!=enabled:
                    result=ctypes.windll.kernel32.SetThreadExecutionState(0x80000000|(1 if busy else 0))
                    if not result:logging.getLogger('studio-background').warning('Could not set temporary processing wake lock.')
                    enabled=busy
        finally:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
    threading.Thread(target=monitor,daemon=True,name='studio-wake-lock').start()
