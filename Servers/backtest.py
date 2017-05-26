"""
Run a backtesting server, using historical data as "live" data.

Copyright (c) Cambridge Quantum Computing ltd. All rights reserved.  
Licensed under the Attribution-ShareAlike 4.0 International. See LICENSE file
in the project root for full license information.  

"""
import time
import datetime
import sys
import zmq
import ujson

class BacktestServer:
    def __init__(self, num_clients, dates):
        self.num_clients = num_clients
        dates = [datetime.datetime.strptime(date, "%Y-%m-%d") for date in dates]
        if len(dates) == 1:
            self.dates = dates
        else:
            self.dates = [
                dates[0] + datetime.timedelta(days=j)
                for j in range((dates[-1] - dates[0]).days + 1)
            ]
        print("Dates:", [str(d) for d in self.dates])
        self.timeout = 50
        self.context = zmq.Context()
        self.sockets_in = {}
        self.sockets_out = {}
        self.pollers_in = {}
        self.pollers_out = {}
        self.ready = {}
        self.bars = {}
        self.symbols_to_requests = {}
        self.do_listen = True

    """
    Send a JSON message to a given connection ID.
    The connection is first grabbed from sockets_out, polled,
    then the message is sent in string format.
    \param connectionID the integer ID of the connection to send the message to
    \param message a dictionary to be converted to JSON, stringified, and sent.
    """
    def send(self, connectionID, message):
        if connectionID not in self.sockets_out:
            raise Exception("Socket " + str(connectionID) + " requested, but it doesn't exist!")
        elif connectionID not in self.pollers_out:
            raise Exception("Poller " + str(connectionID) + " requested, but it doesn't exist!")
        if self.pollers_out[connectionID].poll(50):
            self.report("Sending: ", connectionID, message)
            self.sockets_out[connectionID].send_string(ujson.dumps(message))
            self.report("Sent")
        else:
            self.report("Polling connection ", connectionID, " failed.")

    """
    Receive a JSON message from a given connection ID.
    The connection is first grabbed from sockets_in, polled,
    then the message is received in stringified JSON format
    and converted into a dictionary.
    \param connectionID the integer ID of the connection to receive a message from
    \return A dictionary converted from the received message's JSON string, or None
            in the case of no message.
    """
    def receive(self, connectionID):
        if connectionID not in self.sockets_in:
            raise Exception("Socket " + str(connectionID) + " requested, but it doesn't exist!")
        elif connectionID not in self.pollers_in:
            raise Exception("Poller " + str(connectionID) + " requested, but it doesn't exist!")
        if self.pollers_in[connectionID].poll(200):
            message = ujson.loads(self.sockets_in[connectionID].recv().decode('ascii'))
            self.report("Received: ", connectionID, message)
            return message
        return None

    """
    Require a parameter from an input dictionary. Automatically throws an exception
    if the parameter does not exist in the input.
    \param input The dictionary given by input
    \param param The name of the key in the dictionary
    \return The value of the input's value at the key provided
    """
    @staticmethod
    def requireParam(input, param):
        if param not in input:
            raise RuntimeError("Invalid JSON input: must have field '" + param + "'")
        return input[param]
    
    """
    When input arrives, we want to see what it wants to do and go to the relevant method.
    This method is called by listen() until a Finalise signal is received for each client,
    allowing us to ignore input and only really focus on output. This is because we have
    no real thread handling in python, so we split tasks in a linear fashion.
    \param connectionID The ID of the connection that a request was sent from
    \param input The dict generated from the connection's message.
    """
    def parseInput(self, connectionID, input):
        requestType = self.requireParam(input, "Type")
        if requestType == "IsReady":
            self.parseIsReady(connectionID, input)
        elif requestType == "Request Accounts":
            self.requestAccounts(connectionID, input)
        elif requestType == "Request Stock":
            self.requestStock(connectionID, input)
        elif requestType == "Request Live Data":
            self.requestLiveData(connectionID, input)
        elif requestType == "Finalise":
            self.connectionFinalised(connectionID, input)
        else:
            self.send(
                connectionID,
                {
                    "Type" : "Fatal Error",
                    "RequestID" : self.requireParam(input, "RequestID"),
                    "Message" : "Unknown request '" + requestType + "'"
                }
            )
    
    """
    The Clients will send an "Is Ready" request to make sure the
    server is capable of handling incoming requests. As this is a
    backtester, there are no APIs to connect with, so we can accept input
    right away.
    \param connectionID The ID of the connection that a request was sent from
    \param input The dict generated from the connection's message.
    """
    def parseIsReady(self, connectionID, input):
        RequestID = self.requireParam(input, "RequestID")
        What = self.requireParam(input, "What")
        self.send(connectionID,
            {
                "Type": "IsReady",
                "Ready" : True,
                "RequestID" : RequestID
            }
        )

    """
    For some APIs, we need to send an account along with the requests.
    This is here to grab the relevant account ID. Of course, in the backtester
    we require no such functionality, so an ID of 'N/A' is sent instead.
    \param connectionID The ID of the connection that a request was sent from
    \param input The dict generated from the connection's message.
    """
    def requestAccounts(self, connectionID, input):
        RequestID = self.requireParam(input, "RequestID")
        self.send(connectionID,
            {
                "Type" : "Accounts",
                "Accounts" : [{"ID":  "N/A"}],
                "RequestID" : RequestID
            }
        )
    
    """
    We want to make sure that there is no problem grabbing a stock. In a live
    scenario, we could check that the stock is available from the exchange. In
    a backtesting scenario, we want to make sure that the stock can be loaded.
    \param connectionID The ID of the connection that a request was sent from
    \param input The dict generated from the connection's message.
    """
    def requestStock(self, connectionID, input):
        self.send(
            connectionID,
            {
                "RequestID" : self.requireParam(input, "RequestID"),
                "Type": "Stock Response",
                "Stock" : {
                    "Symbol" : self.requireParam(input, "Symbol"),
                    "Exchange" : self.requireParam(input, "Exchange"),
                    "Currency" : self.requireParam(input, "Currency"),
                }
            }
        )
    
    """
    When a client requests live data for a stock, we want to be able
    to return that data to that client. There is no point loading different
    stocks for different clients, so we link symbols to requests to
    efficiently send the data in.
    \param connectionID The ID of the connection that a request was sent from
    \param input The dict generated from the connection's message.
    """
    def requestLiveData(self, connectionID, input):
        symbol = self.requireParam(input, 'Symbol')
        connection_path = (connectionID, self.requireParam(input, 'RequestID'))
        if symbol not in self.symbols_to_requests:
            self.symbols_to_requests[symbol] = [connection_path]
        else:
            self.symbols_to_requests[symbol].append(connection_path)
        self.report("added {:s} to {:s}".format(symbol, str(connection_path)))

    """
    Send a set of live bars to a given connection.
    \param connectionID The ID of the connection to send the bars to
    \param package A list of pricebars to send in (requestID, symbol, bar) format.
    """
    def sendLiveBars(self, connectionID, package):
        requestID = self.ready[connectionID]
        self.send(
            connectionID,
            {
                "RequestID" : self.ready[connectionID],
                "Type": "Prepare for Live Bars"
            }
        )
        for (requestID, symbol, bar) in package:
            del bar['UnconvertedTime']
            self.send(
                connectionID,
                {
                    "RequestID" : requestID,
                    "Type"      : "Live Bar",
                    "Exchange"  : "N/A",
                    "Symbol"    : symbol,
                    "Bar"       : bar
                }
            )
        
        self.send(
            connectionID,
            {
                "RequestID" : self.ready[connectionID],
                "Type": "End of Live Bars"
            }
        )
    """
    A client can request historical data from a stock.
    In the backtester, there is no benefit in this, so we just send empty bars.
    \param connectionID The ID of the connection that a request was sent from
    \param input The dict generated from the connection's message.
    """
    def requestHistoricalData(self, connectionID, input):
        self.report("Trying to send to connection ", connectionID, " some historical data for ", self.requireParam(input, "Symbol"))
        self.send(
            connectionID,
            {
                "RequestID" : self.requireParam(input, "RequestID"),
                "Type" : "HistoricalBars",
                "Exchange" : self.requireParam(input, "Exchange"),
                "Symbol" : self.requireParam(input, "Symbol"),
                "Bars" : []
            }
        )
    """
    When a client is ready to start receiving data, we note it and keep the request ID
    for later use. If all clients are ready, we can begin sending data.
    \param connectionID The ID of the connection that a request was sent from
    \param input The dict generated from the connection's message.
    """
    def connectionFinalised(self, connectionID, input):
        self.ready[connectionID] = int(self.requireParam(input, 'RequestID'))
        if len(self.ready) == len(self.sockets_in):
            self.stopListening()

    """
    When we are going into 'send bars' mode, we don't want to keep listening for input,
    because we don't have threading capabilities. Insteda, we just stop listening
    by setting the do_listen flag to False (which terminates the loop in listen())
    """
    def stopListening(self):
        self.do_listen = False
    
    """
    In the start up process of a Client, a lot of requests are sent to this
    server application. This method polls a specific connection for input, so that
    it can respond appropriately.
    \param connectionID The ID of the connection that a request may have been sent from
    """
    def listen(self, connectionID):
        if connectionID not in self.sockets_in:
            raise RuntimeError("Socket " + str(connectionID) + " requested, but it doesn't exist!")
        try:
            message = self.receive(connectionID)
            if message != None:
                self.parseInput(connectionID, message)
        except RuntimeError as e:
            self.report("Gateway Error: ", e)

    """
    Connections are formed initially when a connection request is received through a fixed
    listening port (:92482 was picked at random).

    When a message is received on this channel, we respond to it with a JSON message,
    providing it with a port to send messages to and a port to receive messages from. This
    method first looks for available ports, sets up connections, bindings, and pollers,
    then responds to the client with the information that it needs to get started.

    In a normal situation, this runs on its own thread to allow new connections
    at any time. However, we do not have the luxury of threading in Python, so
    instead we only run it until self.num_clients clients have connected, then
    move on with the rest of the processing.
    """     
    def listenForConnectionRequests(self):
        initial_connection_socket = self.context.socket(zmq.REP)
        initial_connection_socket.bind("tcp://127.0.0.1:92482")
        connection_poller = zmq.Poller()
        connection_poller.register(initial_connection_socket, zmq.POLLIN)
        for _ in range(self.num_clients):
            self.report("Listening")
            if connection_poller.poll(100000): #... in seconds. We are willing to wait a while here.
                message = initial_connection_socket.recv().decode("ASCII")
                self.report("Connection request received")
                key = 0
                for socket_id in self.sockets_in:
                    key = max(key, socket_id)
                for socket_id in self.sockets_out:
                    key = max(key, socket_id)
                key += 1

                socketIn = self.context.socket(zmq.PULL)
                socketOut = self.context.socket(zmq.PUSH)
                
                try:
                    success = False
                    lastError = ""
                    for i in range(500):
                        try:
                            inSocket = 103141 + i
                            socketIn.bind("tcp://127.0.0.1:" + str(inSocket))
                            success = True
                            break
                        except Exception as e:
                            lastError = str(e)
                    if not success:
                        raise RuntimeError("SocketIn connection failure: " + lastError)
                    success = False
                    for i in range(500):
                        try:
                            outSocket = 104141 + i
                            socketOut.bind("tcp://127.0.0.1:" + str(outSocket))
                            success = True
                            break
                        except Exception as e:
                            lastError = str(e)
                    if not success:
                        raise RuntimeError("SocketOut connection failure: " + lastError)
                except RuntimeError as e:
                    self.report("ERROR: ", str(e))
                    initial_connection_socket.send(
                        ujson.dumps({
                            "Error": str(e)
                        })
                    )
                    return
                pollerIn = zmq.Poller()
                pollerIn.register(socketIn, zmq.POLLIN)
                pollerOut = zmq.Poller()
                pollerOut.register(socketOut, zmq.POLLOUT)

                self.sockets_in[key] = socketIn
                self.sockets_out[key] = socketOut
                self.pollers_in[key] = pollerIn
                self.pollers_out[key] = pollerOut
                self.report("Granted connection request. In socket: ", inSocket, ", Out socket: ", outSocket, ", Key: ", key)
                initial_connection_socket.send_string(
                    ujson.dumps({
                        "In": inSocket,
                        "Out": outSocket
                    })
                )
    """
    When we are ready to start sending our "Live" bars, we do so by
    packaging bars up for each connection (depending on the symbols
    it is registered to), then sending them all in one go to each
    connection.
    """
    def sendBars(self):
        do_continue = True
        while do_continue:
            connection_bars = {}
            earliest_time = min(
                [
                    self.bars[symbol][0]['UnconvertedTime']
                    for symbol in self.bars
                    if self.bars[symbol]
                ]
            )
            for symbol in self.symbols_to_requests:
                if (not self.bars[symbol]) or self.bars[symbol][0]['UnconvertedTime'] > earliest_time:
                    continue
                for (connectionID, requestID) in self.symbols_to_requests[symbol]:
                    package = (requestID, symbol, self.bars[symbol][0])
                    if connectionID not in connection_bars:
                        connection_bars[connectionID] = [package]
                    else:
                        connection_bars[connectionID].append(package)
            for connectionID in connection_bars:
                self.sendLiveBars(connectionID, connection_bars[connectionID])
            do_continue = False
            for symbol in self.bars:
                if self.bars[symbol] and len(self.bars[symbol]) > 1:
                    do_continue = True
                    self.bars[symbol] = self.bars[symbol][1:]
            self.ready = {}
            self.do_listen = True
            while self.do_listen:
                for i in self.sockets_in:
                    self.listen(i)
        self.finish()

    """
    Before we can send the data, we need to have some data to send!
    This is where you will need to load data for the day and store OHLCV bars
    in self.bars[symbol][]
    """
    def start(self):
        while self.do_listen:
            for i in self.sockets_in:
                self.listen(i)
        for symbol in self.symbols_to_requests:
            day_bars = []
            self.report("Loading data for {:s}".format(symbol))
            #
            #    day_bars.append({
            #        'Time'      : str(bar_index),
            #        'Open'      : bar['Open'],
            #        'Close'     : bar['Close'],
            #        'High'      : bar['High'],
            #        'Low'       : bar['Low'],
            #        'Volume'    : bar['Volume']
            #        'UnconvertedTime' : bar_index,
            #    })
            self.bars[symbol] = day_bars
            self.report("Loaded {:d} records for {:s}".format(len(day_bars), symbol))
        self.sendBars()
    """
    When all the data has been sent, we should inform the clients that we're shutting down,
    then close the communication lines etc.
    """
    def finish(self):
        for connectionID in self.sockets_out:
            self.send(
                connectionID,
                {
                    "Type": "Server Exit",
                    "RequestID" : self.ready[connectionID]
                }
            )
            self.pollers_out[connectionID].unregister(self.sockets_out[connectionID])
            self.sockets_out[connectionID].close()
            self.pollers_in[connectionID].unregister(self.sockets_in[connectionID])
            self.sockets_in[connectionID].close()
        sys.exit(0)


    """
    This is just a helper method to allow server output in a log-friendly manner.
    Accepts arbitrary arguments in the same manner as print.
    """
    @staticmethod
    def report(*arg):
        print(
            "{:s} ~ [Server] > ".format(
                str(datetime.datetime.now())[:24]
            ),
            *arg
        )
        sys.stdout.flush()