# -*- coding: utf-8 -*-
'''
Created on 24. Sep. 2015

@author: dietmar
'''


import sys
sys.path.insert(1, '../')

from drivers.driver import *
import time
import threading


class USBHIDDS18B20(Driver):
    '''
    ds18b20 driver via USB HID
    '''


    def __init__(self, parameters,logger ):
        '''
        Constructor
        '''
        Driver.__init__(self, parameters,logger )

        self.path= '/dev/hidraw0'
        self.fp= None
        
        self.temperature1= 0
        self.temperature2= 0
        self.pwr= 0
        self.id= 0
        self.max= 0
        self.lastUpdate1= ''
        self.lastUpdate2= ''
        
        self.debug_mode= True

        self.sensor_worker= threading.Thread(target=self.run_sensor_worker)
        self.sensor_worker.setDaemon(True)
        self.sensor_worker.start()
        
        
    def open(self):
        try:
            self.fp = open( self.path, 'rb')    
        except Exception as e:
            self.fp= None
            pass


    def get_observations(self,container):

        if not self.fp:
            return
        
        temperature_observation= self.observation( 'temperature1', self.lastUpdate1, str("{:.1f}".format( self.temperature1 )), '°C' );
        container.append(temperature_observation)

        self.handle_debug(self.name + ' delivers ' +  str(temperature_observation) )

        temperature_observation= self.observation( 'temperature2', self.lastUpdate2, str("{:.1f}".format( self.temperature2 )), '°C' );
        container.append(temperature_observation)

        self.handle_debug(self.name + ' delivers ' +  str(temperature_observation) )


    def run_sensor_worker (self):
        
        self.handle_debug ('starting thread')
        while self.shall_run:
            try:
                
                if not self.fp:
                    self.open()
                
                buffer = self.fp.read(64)
                
                #print ('DEBUG: found data' + str(buffer) )

                self.pwr= buffer[2]
                self.id=buffer[1]
                self.max=buffer[0]
                
                bytebuffer = bytes([buffer[4], buffer[5]])
                temperatureTimes10= int.from_bytes(bytebuffer, byteorder='little', signed=True)
                temperature= temperatureTimes10 / 10.0

                if self.id == 1:
                    self.temperature1= temperature
                    self.lastUpdate1= self.get_observation_time()
                if self.id == 2:
                    self.temperature2= temperature
                    self.lastUpdate2= self.get_observation_time()

            except Exception as e:
                time.sleep( 15 )
                pass

                        
            time.sleep( 1 )
            #print ('DEBUG: looping thread')





if __name__ == '__main__':
    sensor= USBHIDDS18B20( """{"device":"/dev/hidraw0"}""" )
    for count in range(0,100):
        container= []
        sensor.get_observations(container)
        print ( container )
        time.sleep(5)

        
        
        
        
