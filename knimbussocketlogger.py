#
#    Copyright (c) 2017 Kevin Kearney <kevkearney@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision: .2 $
#    $Author: kevkearney $
#    $Date: 2017-06-04 12:34:00 -0500 $
#
""" This driver connects to a socket.io (typically on localhost) and waits 
    for packet data. Once a new line comes into the socket, this will process
    the data and submit the packet back to weewx. 
    
    Based on SocketLogger, which is based on the hackulink driver, which was based on the weewx wmr100 driver

    Special thanks to Chris Newham for the socket thread idea
"""

import syslog
import threading
import time
from socketIO_client import SocketIO, LoggingNamespace

import weedb
import weewx.drivers
import weeutil.weeutil
import weewx.wxformulas

def logmsg(dst, msg):
    syslog.syslog(dst, 'KnimbusSocket: %s' % msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)
    
def logerror(msg):
    logmsg(syslog.LOG_ERROR, msg)
    
def logdebug(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loader(config_dict, engine):
    station = KnimbusSocketLogger(**config_dict['KnimbusSocketLogger'])
    return station
        
class WxSocket(threading.Thread):
    def __init__(self, callbacks, host, port):
        super(WxSocket, self).__init__()
        self.callbacks = callbacks
        self.host = host
        self.port = port
        self.daemon = True #this will kill the thread when the main thread exits
        self.start()

    #this is the worker function that will be held in the other thread
    def run(self):
        self.io = SocketIO(self.host, self.port, LoggingNamespace)               

        for event, callback in self.callbacks.iteritems():
            self.io.on(event, callback)

        self.io.wait()

    def connect(self):
        self.io.connect()

    def disconnect(self):
        self.io.disconnect()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.disconnect()

class KnimbusSocketLogger(weewx.drivers.AbstractDevice):
    """ Driver for the SocketLogger station. """
       
    def __init__(self, **stn_dict) :
        """ Initialize an object of type SocketLogger. """
        
        self.host_ip          = stn_dict.get('host_ip')
        self.host_port        = int(stn_dict.get('host_port'))    
              
        self.station_hardware = stn_dict.get('hardware')       
       
        self.packet = None

        self.socket = None
        self.openPort()

    def hardware_name(self):
        return self.station_hardware 
        
    def openPort(self):
        loginf("Connecting to socket on %s port %s" % (self.host_ip, self.host_port) )
        self.socket = WxSocket({'weather message': self.genPacket}, self.host_ip, self.host_port)   
        loginf("Connected to host %s on port %d" % (self.host_ip, self.host_port)) 

    def closePort(self):
        self.socket.disconnect()        
    
        
    #===============================================================================
    #                         LOOP record decoding functions
    #===============================================================================

    def genLoopPackets(self):
        """ Generator function that continuously returns loop packets """
        while True:
            time.sleep(5)
            if self.packet is not None:
                loginf('Retrieved packet')
                logdebug(self.packet)
                if self.packet["Humidity"] == 0 and self.packet["Temperature"] == 0
                    loginf('Bad Packet Data')
                else:
                    yield self.packet
                self.packet = None
                
    def genPacket(self, *args):
        #logdebug('weather message: %s' % (args)) 
        logdebug('genPacket fired')  
        self.packet = self._process_message(args[0])
               
    def _process_message(self, message):
        logdebug('weather message: %s' % (message))  
        _packet = {}
        # Separate line into a dict
        weatherData = dict(message)
              
        _packet['dateTime'] = int(time.time())
        _packet['usUnits'] = weewx.METRIC
        _packet['outTemp'] = float( weatherData["Temperature"]/100)
        _packet['outHumidity'] = float( weatherData["Humidity"] /100 )   
        _packet['inTemp'] = float( weatherData["BaroTemperature"] /100 )
        _packet['inHumidity'] = float( weatherData["BaroHumidity"] /100)
        _packet['pressure'] = float( weatherData["BaroPressure"]/10 )
        _packet['rain'] = (weatherData["RainClicks"]/100 )
        _packet['windDir'] = float( weatherData["WindDirection"] )
        _packet['windSpeed'] = float( (weatherData["WindSpeed"]/100) * 1.609344)
        #_packet['windGust'] = float( weatherData["windGust"] )
        #_packet['windGustDir'] = float( weatherData["windDir"] )
        #_packet['radiation'] = float( weatherData["radiation"] )
        #_packet['UV'] = float( weatherData["UV"] )
        #_packet['txBatteryStatus'] = float( weatherData["txBatteryStatus"] )   
        return _packet