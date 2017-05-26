"""
Runs a set of clients given a version and a environment.
Splits the symbols into a number of processes (retrieved from
Versions/[version]/[index|environment].py ), with settings in
[environment].py overriding any conflicting settings in index.py


Copyright (c) Cambridge Quantum Computing ltd. All rights reserved.  
Licensed under the Attribution-ShareAlike 4.0 International. See LICENSE file
in the project root for full license information.  

"""
import os
import sys
import importlib
from multiprocessing import Process
from random import randint
from copy import deepcopy
import time
import sys

from Core.controller import Controller


""" Create a client from a set of symbols, a version and an environment.
    The client will write to it's own log file, not to the main process' stdout.
"""
def spawnClient(version, environment, global_settings, client_id, symbols):
    outname = "Logs/Client-{:s}-{:s}-{:d}.out".format(version, environment, client_id)
    errname = "Logs/Client-{:s}-{:s}-{:d}.error".format(version, environment, client_id)
    if os.path.exists(outname) or os.path.exists(errname):
        tmpoutname = outname + ".{:d}"
        tmperrname = errname + ".{:d}"
        i = 1
        while os.path.exists(tmpoutname.format(i)) or os.path.exists(tmperrname.format(i)):
            i += 1
        try:
            os.rename(outname, tmpoutname.format(i))
            os.rename(errname, tmperrname.format(i))
        except:
            pass
    sys.stdout = open(outname, 'w')
    sys.stderr = open(errname, "w")
    interface = Controller(version, environment, global_settings, client_id, symbols)
    interface.goLive()

""" Create an arrow server dedicated to backtesting. """
def spawnBacktestServer(number_of_processes, backtest_date):
    sys.stdout = open("Logs/Server-Backtest.out", 'w')
    sys.stderr = open("Logs/Server-Backtest.error", "w")
    # Load the backtest module
    sys.path.insert(0, '..')
    from Servers.backtest import BacktestServer
    # run the backtesting server
    server = BacktestServer(number_of_processes, backtest_date)
    server.listenForConnectionRequests()
    server.start()

if __name__ == "__main__":
    # collect available versions, environments, and symbols, from the Versions directory
    versions = {}
    dirs = [x for x in os.walk("Versions")][0][1]
    for version in dirs:
        files = [x for x in os.walk("Versions/{:s}".format(version))][0][2]
        environments = []
        for file in files:
            if file[-3:] == ".py" and file not in ["index.py", "__init__.py"]:
                environments.append(file.replace(".py", ""))
        symbols = [x for x in os.walk("Versions/{:s}/Stocks".format(version))]
        if len(symbols) == 0:
            symbols = []
        else:
            symbols = symbols[0][1]
        versions[version] = {
            "environments" : environments,
            "symbols" : symbols
        }
    # Validate user input, making sure the version and environment is present and accounted for
    problem = False
    input_version = None
    input_environment = None
    backtest_date = None
    processes = []
    if len(sys.argv) < 3:
        print("Input must be in the form of run.py [version] [environment]")
        problem = True
    else:
        input_version = sys.argv[1]
        input_environment = sys.argv[2]
        if input_version not in versions:
            print("Version '{:s}' does not exist".format(input_version))
            problem = True
        elif input_environment not in versions[input_version]["environments"]:
            print("Version '{:s}' has no environment {:s}".format(input_version, input_environment))
            problem = True
        if input_environment == "Backtest":
            if len(sys.argv) < 4:
                print("If [version] is \"Backtest\", then a third parameter")
                print("needs to be given for the date. An optional fourth")
                print("parameter can be used for an end date for multiple")
                print("day simulations.")
                problem = True
            else:
                backtest_date = sys.argv[3:]
    if problem is True:
        print("\nAvailable versions:")
        for version in versions:
            if len(versions[version]["environments"]) == 0:
                print("  {:18s}   No environments defined".format(version))
            else:
                print(
                    "  {:18s}   environments: {:s}".format(
                        version,
                        ", ".join(list(versions[version]['environments']))
                    )
                )
        quit()
    symbols = sorted(versions[input_version]["symbols"])
    # import the version file and the environment file, overriding
    # settings from the former with settings in the latter in the
    # case of a clash.
    global_settings = {}

    version_file = importlib.import_module(
        "Versions.{:s}.index".format(
            input_version,
            input_environment
        )
    )
    global_settings.update(version_file.settings)

    environment_file = importlib.import_module(
        "Versions.{:s}.{:s}".format(
            input_version,
            input_environment
        )
    )
    global_settings.update(environment_file.settings)
    # check if there is an include_symbols property. if so, we only use those symbols
    if 'include_symbols' in global_settings:
        print("Symbols before whitelist:", len(symbols))
        to_remove = []
        to_include = global_settings['include_symbols']
        for i in range(len(symbols)):
            if symbols[i] not in to_include:
                to_remove.append(i)
        for i in reversed(to_remove):
            del symbols[i]
        print("symbols after whitelist:", len(symbols))
    # otherwise, if there is an exclude_symbols property, exclude those symbols.
    # (inclusion is a whitelist, and takes priority over the blacklisting exclusion)
    elif 'exclude_symbols' in global_settings:
        print("symbols before blacklist:", len(symbols))
        to_remove = []
        to_exclude = global_settings['exclude_symbols']
        for i in range(len(symbols)):
            if symbols[i] in to_exclude:
                to_remove.append(i)
        for i in reversed(to_remove):
            del symbols[i]
        print("symbols after blacklist:", len(symbols))
    if len(symbols) == 0:
        print("No symbols are set to load, quitting.")
        quit()
    if backtest_date is not None:
        global_settings['backtest_date'] = backtest_date
    # if global_settings provides a number of processes, use that.
    # otherwise use one child process for all symbols.
    number_of_processes = global_settings["processes"] if "processes" in global_settings else 1
    number_of_processes = min(number_of_processes, len(symbols))
    # split symbols into lists of symbols
    process_symbols = [symbols[n::number_of_processes] for n in range(number_of_processes)]
    # for each child process, launch it and add it to the stored list of processes
    for i in range(len(process_symbols)):
        stock_set = process_symbols[i]
        p = Process(
            target=spawnClient,
            args=[
                input_version,
                input_environment,
                deepcopy(global_settings),
                i+1,
                stock_set
            ]
        )
        p.start()
        processes.append(p)
    if backtest_date is not None:
        p = Process(
            target=spawnBacktestServer,
            args=[
                number_of_processes,
                backtest_date
            ]
        )
        p.start()
        processes.append(p)
        time.sleep(0.1)
