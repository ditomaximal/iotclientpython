# -*- coding: utf-8 -*-
'''
device driver base class for GREX iotserver

'''

import json
from time import time
from datetime import datetime
import logging

__version__ = '0.0.6'
__author__  = "Dietmar Millinger"



class Driver(object):
    '''
    classdocs
    '''

    def __init__(self, parameters, logger):
        '''
        Constructor
        '''
        
        self.debug_mode= False
        self.parameters= parameters
        
        
        if not logger:
            self.logger = logging.getLogger('iotclient')
            self.logger.handlers= []
            hdlr = logging.FileHandler('/var/log/iotclient.log')
            formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
            hdlr.setFormatter(formatter)
            self.logger.addHandler(hdlr) 
            self.logger.setLevel(logging.INFO)    
        else:
            self.logger= logger

        self.exception_counter= 0
        self.health= 0
        self.critical_hardware_error= 0
        
        try:
            if isinstance(parameters,dict):
                self.config= parameters
            else:
                self.config= json.loads(parameters)
                
            self.name= self.config.get('name','')
        except Exception as e:
            self.exception_counter+= 1
            self.handle_exception( e, 'driver.__init__')        

        if not hasattr(self, 'name') or not self.name:
            #module= self.__module__
            module= self.__class__.__name__.lower()
            self.name= module
        
        self.shall_run= True
        pass
    
    def __str__(self): 
        return self.name
    def __eq__(self, other):
        return object.__eq__(self.name, other.name)
    def __hash__(self):
        return hash(self.name)
    
    
    def initialize(self):
        self.period= 0;
        pass

    def start(self):
        pass
    
    def stop(self):
        pass
    
    def shutdown(self):
        self.shall_run= False

    def get_hardware_error_count(self):
        return self.critical_hardware_error

    def increment_hardware_error_count(self):
        self.critical_hardware_error= self.critical_hardware_error+ 1

    def clear_hardware_error_count(self):
        self.critical_hardware_error= 0




    def set_period(self,period):
        self.period= period;

    def observation(self, key, observation_time, value, unit ):
        observation= {}
        observation['key']= self.name + '.' + key
        observation['observation_time']= observation_time   # UTC in format '%Y-%m-%d %H:%M:%S'
        observation['value']= value
        observation['unit']= unit
        return observation
        
    def get_observation_time(self):
        ts = int(round(time() * 1000)) 
        return '%d' % (ts)
        
    def get_observation_time_millis(self):
        ts = int(round(time() * 1000)) 
        return ts
        
    def handle_debug(self,message):
        if self.debug_mode:
            self.logger.debug(message)
            
            
    def handle_exception(self,e,message):
        self.exception_count+= 1
        #print( "%s EXCEPTION: %s. %s" % ( datetime.now().strftime('%Y-%m-%d %H:%M:%S' + ' CET'), e, message ))    
        self.logger.error("EXCEPTION: %s. %s" % ( e, message ))
    
    def handle_info(self,message):
        #print( "%s INFO: %s" % ( datetime.now().strftime('%Y-%m-%d %H:%M:%S' + ' CET'), message ))    
        self.logger.info(message)
        
    def command(self,parameters):
        pass    
        
    def get_observations(self,container):
        pass
    
    def output_data (self, value):
        pass

    def get_name(self):
        return self.name







        