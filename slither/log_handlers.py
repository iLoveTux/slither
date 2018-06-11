import os
import logging
from lxml import etree
import subprocess
from logging import (
    StreamHandler,
    Handler,
    getLevelName,
    LogRecord,
)


class OverwritingFileHandler(StreamHandler):
    """
    A handler class which writes formatted logging records to disk files.
    """
    def __init__(self, filename, mode='w', encoding=None, delay=True):
        """
        Open the specified file each time a record is logged.
        This Handler is meant to support writing out file contents
        with the latest information. By default this will overwrite
        the contents on each log event.
        """
        # Issue #27493: add support for Path objects to be passed in
        try:
            filename = os.fspath(filename)
        except AttributeError:
            # Python < 3.6
            pass
        #keep the absolute path, otherwise derived classes which use this
        #may come a cropper when the current directory changes
        self.baseFilename = os.path.abspath(filename)
        self.mode = mode
        self.encoding = encoding
        self.delay = delay
        #We don't open the stream, but we still need to call the
        #Handler constructor to set level, formatter, lock etc.
        Handler.__init__(self)
        self.stream = None

    def close(self):
        """
        Closes the stream.
        """
        self.acquire()
        try:
            try:
                if self.stream:
                    try:
                        self.flush()
                    finally:
                        stream = self.stream
                        self.stream = None
                        if hasattr(stream, "close"):
                            stream.close()
            finally:
                # Issue #19523: call unconditionally to
                # prevent a handler leak when delay is set
                StreamHandler.close(self)
        finally:
            self.release()

    def _open(self):
        """
        Open the current base file with the (original) mode and encoding.
        Return the resulting stream.
        """
        return open(self.baseFilename, self.mode, encoding=self.encoding)

    def emit(self, record):
        """
        Emit a record.
        If the stream was not opened because 'delay' was specified in the
        constructor, open it before calling the superclass's emit.
        """
        try:
            self.stream = self._open()
            StreamHandler.emit(self, record)
        finally:
            self.close()

    def __repr__(self):
        level = getLevelName(self.level)
        return '<%s %s (%s)>' % (self.__class__.__name__, self.baseFilename, level)


class XPathingOverwritingFileHandler(OverwritingFileHandler):
    def __init__(self, filename, xpath=None, **kwargs):
        super().__init__(filename, **kwargs)
        self.xpath = xpath

    def emit(self, record):
        """
        Emit a record.
        If the stream was not opened because 'delay' was specified in the
        constructor, open it before calling the superclass's emit.
        """
        try:
            self.stream = self._open()
            if self.xpath is not None:
                for _record in etree.fromstring(record.msg).xpath(self.xpath):
                    _log_record = LogRecord(record.name, record.levelno, record.pathname, record.lineno, etree.tostring(_record).decode(), record.args, record.exc_info, record.funcName, record.stack_info)
                    StreamHandler.emit(self, _log_record)
            else:
                StreamHandler.emit(self, _record)
        finally:
            self.close()

class SubprocessPipeHandler(Handler):
    def __init__(self, command, stdin=subprocess.PIPE, stdout=None, stderr=None, bufsize=1, universal_newlines=True, **kwargs):
        Handler.__init__(self)
        self.proc = subprocess.Popen(command, stdin=stdin, stdout=stdout, stderr=stderr, bufsize=bufsize, **kwargs)
        self.proc

    def emit(self, record):
        self.proc.stdin.write(record.msg.encode().strip() + os.linesep.encode())
