""" Contains the gateway to the Server

Copyright (c) Cambridge Quantum Computing ltd. All rights reserved.  
Licensed under the MIT License. See LICENSE file
in the project root for full license information.  

"""

import time
import datetime
import sys
import zmq
import ujson

from .loggable import Loggable
from .pricebar import PriceBar
from .stock import Stock
class Gateway(Loggable):
    """ The gateway between the Controller and the Server

    Communication is done via TCP with the ZMQ library. First we send
    a message to a main connection initialization port, which then
    provides this object with an input port and an output port, so
    that requests can be sent and received.

    All requests are automatically linked with a unique Request ID,
    so that when a response is received we can determine what the
    request is in response of.
    """
    def __init__(self, server_ip="127.0.0.1", connection_port = 92482, timeout=25000):
        """ Create the Gateway object. """
        self.server_ip = server_ip
        self.connection_port = connection_port

        self.timeout = timeout
        self.zmq_context = zmq.Context()
        self.report("Connecting to the Gateway...")
        details = self.connect()
        # The server application returns a pair of communication ports
        # for communication with this specific client. Depending on the requests,
        # one or multiple responses can be received, so we use separate push and
        # pull sockets rather than a request/response socket.
        # NOTE: "In" for the server is "Out" for the client.
        out_port = details['In']
        in_port = details['Out']
        self.report("Using in  port ", in_port)
        self.report("Using out port ", out_port)
        # This is the socket we're using to send requests
        self.socket_out_poller = zmq.Poller()
        self.socket_out = self.zmq_context.socket(zmq.PUSH)
        self.socket_out.connect("tcp://" + serverIP + ":" + str(out_port))
        self.socket_out_poller.register(self.socket_out, zmq.POLLOUT)
        # This is the socket that we get responses from
        self.socket_in_poller = zmq.Poller()
        self.socket_in = self.zmq_context.socket(zmq.PULL)
        self.socket_in.connect("tcp://" + serverIP + ":" + str(in_port))
        self.socket_in_poller.register(self.socket_in, zmq.POLLIN)
        # An incrementing request ID so that responses can be
        # matched to requests
        self.request_id = 0
        # If a message arrives, but we're waiting for a message with a different
        # request_id, we cache the arrived message until it is ready to be processed.
        self.cached_results = {}
        # ID of a status input, which is first set when we tell the server that
        # we're ready to receive data, and is sent back when e.g. a set of data
        # is ready to come in.
        self.status_id = None
        self.account = None
        # When pricebars are returned, we want to make sure that
        # there is no request.
        self.request_to_stock = {}

    # Establish the initial connection. To do this, we communicate
    # with a static Request socket. The server application allocates a unique
    # input port and output port for dedicated communication between the server
    # application and this client, providing smooth communication between
    # the server and multiple clients.
    def connect(self):
        initial_connection_socket = self.zmq_context.socket(zmq.REQ)
        initial_connection_socket.connect("tcp://{:s}/{:d}".format(self.server_ip, self.connection_port))
        poller = zmq.Poller()
        poller.register(initial_connection_socket)
        connected = False
        attempts = 0
        # Attempt to connect up to 5 times.
        while not connected:
            attempts += 1
            poll_result = dict(poller.poll(self.timeout))
            # If we get a connection established, establish initial communication with the server
            if poll_result and poll_result.get(initial_connection_socket) == zmq.POLLOUT:
                initial_connection_socket.send_string('{"Type": "Connect"}')
                # Grab the response and convert it from a JSON string to a python dictionary
                result = ujson.loads(
                    initial_connection_socket.recv().decode('ascii')
                )
                # If there was an error returned by the server, output and retry.
                if "Error" in result:
                    self.report(
                        "Error on attempt", attempts,
                        ":", result["Error"]
                    )
                else:
                    # Close the initial connection socket and return the dictionary
                    initial_connection_socket.close()
                    return result
            if attempts > 5:
                self.report("=================================================")
                self.report("No connection response after 5 attempts.         ")
                self.report("This could mean that:                            ")
                self.report("\t- The server is too busy                       ")
                self.report("\t- The server application isn't running         ")
                self.report("\t- The server itself is off                     ")
                self.report("                                                 ")
                self.report("This client will give up trying to connect.      ")
                self.report("Please try and find the problem and restart me!  ")
                self.report("=================================================")
                quit()
            else:
                self.report("No connection response in {d} seconds.".format(int(self.timeout/1000)))
                self.report("trying again in 5 seconds")
                time.sleep(5)

    """ Poll the input thread, with an optional custom timeout """
    def pollInput(self, timeout=None):
        if timeout is None:
            timeout = self.timeout
        if self.socket_in_poller.poll(timeout):
            self.report("polling is okay")
            return True
        return False
    
    """ Poll the output thread, with an optional custom timeout """
    def pollOutput(self, timeout=None):
        if timeout is None:
            timeout = self.timeout
        if self.socket_out_poller.poll(timeout):
            return True
        return False

    def _send(self, to_send, attempts=1):
        """ Raw sending of dicts """
        for _ in range(attempts):
            if self.pollOutput():
                self.report("Sending: ", to_send)
                self.socket_out.send_string(ujson.dumps(to_send))
                return True
        return False

    def _receive(self, request_ids, ignore_timeout=False):
        """ Raw receiving """
        if not isinstance(request_ids, list):
            request_ids = [request_ids]

        # See if the result has been received previously
        for request_id in request_ids:
            if request_id in self.cached_results and len(self.cached_results[request_id]) > 0:
                return self.cached_results[request_id]

        # Otherwise, receive responses.
        while True:
            # Poll the input. If timeout occurs, raise an exception.
            if ignore_timeout or self.pollInput():
                # The message will be in JSON format once converted to ASCII
                # Receive the message and convert the JSON string into a dict.
                self.report("Trying to receive...")
                result = ujson.loads(self.socket_in.recv().decode('ascii'))
                self.report("Received: ", result)

                # Check that it's the corresponding request ID.
                # If not, cache it.
                if result['RequestID'] in request_ids:
                    return result
                else:
                    request = result['RequestID']
                    if request not in self.cached_results:
                        self.cached_results[request] = [result]
                    else:
                        self.cached_results[request].append(result)
            else:
                raise RuntimeError(
                    "Timeout of %f seconds has occurred" % (self.timeout/1000)
                )

    def send(self, to_send, attempts=1):
        """ Send a request, attaching and returning a unique request ID """
        request = self.request_id
        self.request_id += 1
        to_send["RequestID"] = request
        self._send(to_send, attempts)
        return request

    def request(self, message):
        """ Send a request and return the response, using request ID matching """
        try:
            requestID = self.send(message)
            result = self._receive(requestID)
        except RuntimeError as error:
            self.report(error)
            return False
        if result['Type'] == "Fatal Error":
            raise RuntimeError("Fatal Error: " + result['Message'])
        return result

    def finalise(self):
        self.status_id = self.send({
            "Type" : "Finalise"
        })
    def getAccounts(self):
        """ Load available accounts, if applicable, to which orders are placed """
        self.report("Waiting until account data has been loaded")
        self.waitUntilReady("Accounts")
        self.report("Accounts have been loaded")
        response = self.request({"Type": "Request Accounts"})
        self.account = response['Accounts'][0]['ID']
        return [a['ID'] for a in response['Accounts']]


    def getStock(self, account_id, symbol, exchange, currency):
        """ Get the stock, preparing the server in case it needs notice. """
        message = self.request({
            "Type": "Request Stock",
            "AccountID" : account_id,
            "Symbol" : symbol,
            "Exchange" : exchange,
            "Currency" : currency
        })
        return Stock(self, message['Stock'])
    
    def getHistory(self, stock, days_backwards = 1):
        message = self.request({
            "Type" : "Request Historical Data",
            "AccountID" : self.account,
            "Symbol" : stock.symbol,
            "Exchange" : stock.exchange,
            "Timespan" : days_backwards
        })
        price_bars = []
        for price_bar in message['Bars']:
            price_bars.append(PriceBar(price_bar))
        return price_bars

    def subscribeToMarketData(self, stock):
        request_id = self.send({
            "Type": "Request Live Data",
            "AccountID" : self.account,
            "Symbol" : stock.symbol,
            "Exchange" : stock.exchange
        })
        self.request_to_stock[request_id] = stock.symbol

    def makeOrder(self, stock, shares):
        return stock.addOrder(shares)

    def listen(self):
        """ Poll the server to receive order updates and pricebars """
        return self._receive(list(self.request_to_stock) + [self.status_id], ignore_timeout=True)

    def waitUntilReady(self, what):
        """ Query the Server, waiting until it is ready to start receiving commands """
        while True:
            result = self.request({
                "Type" : "IsReady",
                "What" : what
            })
            if result['Ready'] is True:
                return
            time.sleep(1)

    def getLogTag(self):
        return "Gateway"