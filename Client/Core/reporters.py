"""
Send a report of all trades for this client application.


Copyright (c) Cambridge Quantum Computing ltd. All rights reserved.  
Licensed under the MIT License. See LICENSE file
in the project root for full license information.  

"""
from abc import ABCMeta, abstractmethod

class Reporter:
    """ Generic reporter class, used to report progress for the current clients' trades. """
    @abstractmethod
    def initiate(self, version, environment, client_id):
        """ When a client controller is initiated, it calls this method to implant the
        version name, environment name, and client_id, which is useful for distinguishing
        between different processes. If there are any connections to be made, they are done so here."""
        pass
    @abstractmethod
    def newBars(self, controller, time):
        """ After each minutes' bars have been processed, this method is called. It should determine
        whether it is the right time to make a report (e.g. for an email every 10 minutes), and action
        it accordingly """
        pass
    @abstractmethod
    def endOfDay(self, controller):
        """ This is called at the end of the trading day, to generate a final report """
        pass

class NullReporter:
    """ A reporter that simply does nothing - it is a fill-in for when a reporter isn't required """
    def initiate(self, version, environment, client_id):
        pass
    def newBars(self, controller, time):
        pass
    def endOfDay(self, controller):
        pass

class MultiReporter:
    """ If multiple reporters are needed, this class encapsulates the behaviour of each individual
    reporter, using the methods of a single reporter. """
    def __init__(self, child_reporters):
        self.child_reporters = child_reporters
    def initiate(self, version, environment, client_id):
        for reporter in self.child_reporters:
            reporter.initiate(version, environment, client_id)
    def newBars(self, controller, time):
        for reporter in self.child_reporters:
            reporter.newBars(controller, time)
    def endOfDay(self, controller):
        for reporter in self.child_reporters:
            reporter.endOfDay(controller)