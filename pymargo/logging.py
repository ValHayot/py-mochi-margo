# (C) 2022 The University of Chicago
# See COPYRIGHT in top-level directory.

import _pymargo
from abc import ABC, abstractmethod


level = _pymargo.log_level


set_global_logger = _pymargo.set_global_logger
set_global_log_level = _pymargo.set_global_log_level

trace = _pymargo.trace
debug = _pymargo.debug
info = _pymargo.info
warning = _pymargo.warning
error = _pymargo.error
critical = _pymargo.critical


class Logger(ABC):

    @abstractmethod
    def trace(self, msg):
        pass

    @abstractmethod
    def debug(self, msg):
        pass

    @abstractmethod
    def info(self, msg):
        pass

    @abstractmethod
    def warning(self, msg):
        pass

    @abstractmethod
    def error(self, msg):
        pass

    @abstractmethod
    def critical(self, msg):
        pass
