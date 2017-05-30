""" Contains the Loggable abstract class.

Copyright (c) Cambridge Quantum Computing ltd. All rights reserved.
Licensed under the MIT License. See LICENSE file
in the project root for full license information.

"""
import datetime
import sys
from abc import ABCMeta, abstractmethod
class Loggable(ABCMeta):
    """A class used to log state information.

    Each child class needs to implement a getLogTag(self) method.
    This method should return a unique string which is then inserted
    into the log, so that the origin of each logged statement can be
    easily identified. Alongside this tag, a millisecond-precision
    timestamp is provided.
    """
    @abstractmethod
    def getLogTag(self):
        """ Return a unique string identifying the origin of the log entry """
        pass
    def report(self, *arg):
        """ Log a message to stdout, with a timestamp and a unique tag from getLogTag """
        print(
            "{:s} ~ {:s} > ".format(
                str(datetime.datetime.now())[:23],
                self.getLogTag()
            ),
            *arg
        )
        # in cases that the output is piped to a file, flush it to the file
        sys.stdout.flush()
    def reportError(self, *arg):
        """ Log a message to stderr, with a timestamp and a unique tag from getLogTag """
        print(
            "{:s} ~ {:s} > ".format(
                str(datetime.datetime.now())[:23],
                self.getLogTag()
            ),
            *arg,
            file=sys.stderr
        )
        # in cases that the output is piped to a file, flush it to the file
        sys.stderr.flush()
