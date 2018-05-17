import time
import os

def watch_directory(broker, path, args):
    """Wait 60 seconds, then recurse through path and
    publish to the filesystem.directory topic for every
    directory and to the filesystem.file topic for every
    file.
    """
    while True:
        for root, dirs, filenames in os.walk(path):
            broker.pub("filesystem.directory", root)
            for filename in filenames:
                _filename = os.path.join(root, filename)
                broker.pub("filesystem.file", _filename)
        time.sleep(60)
