"""Independent Linux launcher: FIFO input and file output survive API reloads."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading


def main():
    fifo = sys.argv[1]
    descriptor = os.open(fifo, os.O_RDWR)
    process = subprocess.Popen(["/bin/sh", "./run.sh"], stdin=descriptor,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace", bufsize=1)
    os.close(descriptor)
    def collect():
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            if "Done (" in line:
                Path(".server-ready").write_text(str(process.pid), encoding="ascii")
    output = threading.Thread(target=collect, daemon=True)
    output.start()
    def forward(signum, _frame):
        if process.poll() is None:
            process.send_signal(signum)
    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)
    result = process.wait()
    output.join(timeout=2)
    sys.exit(result)


if __name__ == "__main__":
    main()
