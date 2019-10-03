# -*- coding: utf-8 -*-
'''
Created on 24. Sep. 2015

@author: dietmar
'''


import sys
sys.path.insert(1, '../')

from drivers.driver import *
import time
import Adafruit_DHT
from datetime import datetime


class RPDHT22ADA(Driver):
    '''
    DHT22 driver via raspberry pi pin 
    '''


    def __init__(self, parameters,logger ):
        '''
        Constructor
        '''
        Driver.__init__(self, parameters,logger )

        self.sensor= Adafruit_DHT.DHT22
        self.pin= "4"

        

    def get_observations(self,container):
        
        humidity, temperature = Adafruit_DHT.read_retry(self.sensor, self.pin)
        
        humidity_observation= {}
        if humidity:
            humidity_observation= self.observation('humidity', self.get_observation_time(), str("{:.1f}".format( humidity )), '%' )
            container.append(humidity_observation)
        
        temperature_observation= {}
        if temperature:
            temperature_observation= self.observation( 'temperature', self.get_observation_time(), str("{:.1f}".format( temperature )), u"°C" );
            container.append(temperature_observation)
        
        self.handle_debug(self.name + ' delivers ' + ascii(humidity_observation) + ", " + ascii(temperature_observation) )



if __name__ == '__main__':
    sensor= RPDHT22ADA( """{"pin":2,"sensor":"22"}""", None )
    for count in range(0,100):
        container= []
        sensor.get_observations(container)
        print ( ascii(container) )
        time.sleep(5)

        
        
        
        
