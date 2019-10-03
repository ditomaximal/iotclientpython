# -*- coding: utf-8 -*-
'''
API handling for GREX iotserver

Module Handler
https://drive.google.com/open?id=0B71l1gP_zRPUZFZCcjNIN2RrSHM




'''

__version__ = '0.0.30'
__author__  = "Dietmar Millinger, GREX IT Services"


import os
import sys
import requests
import json
import threading
import re
import importlib
#from datetime import datetime
import inspect
import pickle
import glob
import subprocess
import signal
from queue import Queue
import logging
import time


sys.path.append('..')

api_path= 'https://iotserver.likelynx.com/api1'




iotclientInit= 0
iotclientRunning= 1
iotclientStopped= 2
iotclientRestarting= 3

initSleepPeriodS= (5*60)

filePath=os.path.dirname(os.path.abspath(__file__))
cacheFilePath= filePath + '/../cache'
cacheFileName= cacheFilePath + '/cf'
tmpFileName= cacheFilePath + '/tmpfile'

driverFilePath= filePath + '/../'
configurationFile= filePath + '/configuration'
identityFile= filePath + '/../identity.json'

loggingLevel= logging.INFO
#loggingLevel= logging.DEBUG




class IOThandler():
    '''
    classdocs
    '''
    def __init__(self):
        '''
        Constructor
        '''
        self.exception_count= 0
        self.updatePeriodS= initSleepPeriodS
        self.sleepPeriodS= initSleepPeriodS
        
        self.setup_logger()
        
        self.ssh_tunnel_close= False
        self.ssh_tunnel_start= False
        self.ssh_tunnel= 0
        self.ssh_last_command= 0

        #self.handle_info("file path " + filePath )
        #self.handle_info("configuration file " + configurationFile )
        #self.handle_info("identity file " + identityFile )


        # reads the following values from a json file         
        self.read_identity()
        self.read_configuration()

        if ( not 'name' in self.identity ) or not self.identity['name']:
            self.handle_error("found no valid identity configuration. " + identityFile + " is missing." )
            sys.exit(-1)
        
        
        self.api_error_count= 0
        self.api_error_description= ''
        self.api_status= 0
        self.api_mute= 0
        
        
        if 'api_token' in self.identity:
            self.configuration['api_token']= self.identity['api_token']
        
        if 'sleep_period_s' in self.identity:
            self.sleepPeriodS= int(self.identity['sleep_period_s']) 
        
        
        self.state= iotclientInit;

        self.handle_info("starting node " + self.identity['name'] + " with period " + str(self.sleepPeriodS) + "s" )

        self.sensor_worker= threading.Thread(target=self.run_sensor_worker)
        self.sensor_worker.setDaemon(True)

        self.setup_tunnel()
        self.tunnel_worker= threading.Thread(target=self.run_tunnel_worker)
        self.tunnel_worker.setDaemon(True)

        self.command_queue = Queue()
        self.command_worker= threading.Thread(target=self.run_command_worker)
        self.command_worker.setDaemon(True)
        
        
        self.health_worker= threading.Thread(target=self.run_health_worker)
        self.health_worker.setDaemon(True)
        
        
        
        # setup cache
        self.cacheFilePrefix= cacheFileName + "g"
        self.handle_info("initialized file cache at path prefix %s" % (self.cacheFilePrefix))
        self.cache_worker= threading.Thread(target=self.run_cache_worker)
        self.cache_worker.setDaemon(True)
        
        
        
        
        
        self.drivers= []
        self.driver_instances= []        
        
        #if self.identity['system'] == 'osx':
        #    self.load_plugin(self.drivers,'drivers.osxdriver')
            
        #if self.identity['system'] == 'raspberrypi':
        #    self.load_plugin(self.drivers,'drivers.raspberrypidriver')
        #    self.load_plugin(self.drivers,'drivers.rpdht22ada')
        #    #self.load_plugin(self.drivers,'drivers.usbhidds18b20')
        #    #self.load_plugin(self.drivers,'drivers.cameradriver')
        #    #self.load_plugin(self.drivers,'drivers.usbcameradriver')
        
        if ( not 'plugins' in self.identity ):
            self.handle_info("found no valid identity configuration. plugins are missing." )
            sys.exit(-1)
        if ( not 'parameters' in self.identity ):
            self.handle_info("found no valid identity configuration. parameters are missing." )
            sys.exit(-1)

        self.load_plugins()
        self.init_plugins()


        self.state= iotclientRunning;
        self.sensor_worker.start()
        self.tunnel_worker.start()
        self.health_worker.start()
        self.cache_worker.start()






    def stop(self):

        self.handle_info("stopping node " + self.identity['name'] )
        self.state= iotclientRestarting


    def load_plugin(self,name):
        self.drivers.append(importlib.import_module(name))


    def load_plugins(self):
        
        pysearchre = re.compile('.py$', re.IGNORECASE)
        subfolder = 'drivers'
        pluginfiles = filter(pysearchre.search, os.listdir(os.path.join(driverFilePath, subfolder )))
        form_module = lambda fp: '.' + os.path.splitext(fp)[0]
        plugins = map(form_module, pluginfiles)
        # import parent module / namespace
        importlib.import_module(subfolder)
        for plugin in plugins:
            module = subfolder + plugin
            if ( not plugin.startswith('__') ) and module in self.identity['plugins']:
                self.drivers.append(importlib.import_module(plugin,subfolder))
    
        return



    def init_plugins(self):

        for driver in self.drivers:
            
            is_class_member = lambda member: inspect.isclass(member) and member.__module__ == driver.__name__
            clsmembers = inspect.getmembers(driver, is_class_member)
            if not clsmembers or clsmembers[0][0] == 'Driver':
                continue

            try:
                
                name= clsmembers[0][0] 
                clazz= clsmembers[0][1]            
                if name in self.identity['parameters']:
                    
                    driver_instance= clazz( self.identity['parameters'][name], self.logger)
                    self.driver_instances.append(driver_instance)
                
                else:
                    self.handle_warn('failed to init driver. parameters for ' + name + '  missing in identity.json')        
                    
                
            except Exception as e:
                self.handle_exception( e, 'init_plugins')        

        
    def get_plugin_instance(self,name):
        
        for instance in self.driver_instances:
            if instance.__name__ == name:
                return instance
            if instance.__class__.__name__ == name:
                return instance

        return None
        
        

    def write_pickle(self,data,file_name):
        try:
            f = open(tmpFileName, 'wb')
            pickle.dump(data, f, pickle.DEFAULT_PROTOCOL )
            f.flush()
            os.fsync(f.fileno()) 
            f.close()
            os.rename(tmpFileName, file_name )
        except Exception as e:
            self.handle_exception(e, 'write_pickle')

    def read_pickle(self,file_name):
        data= {}
        try:
            if os.path.isfile(file_name):
                f = open(file_name, 'rb')
                data= pickle.load(f)
        except Exception as e:
            self.handle_exception(e, 'write_atomic')
        return data





    def write_json(self,data,file_name):
        try:
            with open(file_name, 'w') as fp:
                json.dump(data, fp)
        except Exception as e:
            self.handle_exception(e, 'write_json')

    def read_json(self,file_name):
        data= {}
        try:
            with open(file_name, 'r') as fp:
                data = json.load(fp)
        except Exception as e:
            self.handle_exception(e, 'read_json')
        return data




    def store_configuration ( self ):
        self.write_pickle(self.configuration,configurationFile)

    def read_configuration (self):
        self.configuration= self.read_pickle(configurationFile)

    def read_identity (self):
        self.identity= self.read_json(identityFile)
        #self.handle_info("found identity " + str(self.identity) )



    #
    # CACHE
    #
    #

    def write_atomic(self,data,cacheFile):
        try:
            f = open(tmpFileName, 'wb')
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL )
            f.flush()
            os.fsync(f.fileno()) 
            f.close()
            os.rename(tmpFileName, cacheFile )
        except Exception as e:
            self.handle_exception(e, 'write atomic exception' )

        
    def cache_put_data ( self, data ):
        timestamp_string= "%d" % ( int(round(time.time() * 1000)) )
        fileName=self.cacheFilePrefix + '-' + timestamp_string
        self.handle_debug( 'create cache file %s with data'% (fileName) )
        self.write_atomic(data,fileName)


    def cache_get(self):
        # returns a (filename,data) tuple. use this after transmission to call cache_clean
        # TODO: look for version that handles large amounts of files
        # https://stackoverflow.com/questions/20252669/get-files-from-directory-argument-sorting-by-size
        
        name_list= glob.glob( self.cacheFilePrefix + '*' )
        self.backlog= len(name_list)
        for name in name_list:
            try:
                if os.path.isfile(name):
                    f = open(name, 'rb')
                    data= pickle.load(f)
                    return ( name, data )
                    
            except Exception as e:
                self.handle_exception(e, 'work_cache')
        return (None,None)


    def cache_clean(self,file_data_tuple):
        name= file_data_tuple[0]
        if name:
            os.remove(name, dir_fd=None)
            self.handle_debug( 'remove cache file %s after transmission'% (name) )














    def handle_exception(self,e,message):
        self.exception_count+= 1
        self.logger.error("EXCEPTION: %s. %s" % ( e, message ))
        #print( "%s EXCEPTION: %s. %s" % ( datetime.now().strftime('%Y-%m-%d %H:%M:%S' + ' CET'), e, message ))    
    
    def handle_info(self,message):
        #print( "%s INFO: %s" % ( datetime.now().strftime('%Y-%m-%d %H:%M:%S' + ' CET'), message ))    
        self.logger.info(message)

    def handle_warn(self,message):
        #print( "%s INFO: %s" % ( datetime.now().strftime('%Y-%m-%d %H:%M:%S' + ' CET'), message ))    
        self.logger.warn(message)

    def handle_error(self,message):
        #print( "%s INFO: %s" % ( datetime.now().strftime('%Y-%m-%d %H:%M:%S' + ' CET'), message ))    
        self.logger.error(message)

    def handle_debug(self,message):
        #print( "%s INFO: %s" % ( datetime.now().strftime('%Y-%m-%d %H:%M:%S' + ' CET'), message ))    
        self.logger.debug(message)


    def setup_logger(self):
        self.logger = logging.getLogger('iotclient')
        self.logger.handlers= []
        hdlr = logging.FileHandler('/var/log/iotclient.log')
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        hdlr.setFormatter(formatter)
        self.logger.addHandler(hdlr) 
        self.logger.setLevel(loggingLevel)    
    
    
    
    
    
    
        
    def api_ok(self):
        self.api_status= 1
    
    def api_error(self):
        self.configuration['api_token']= ''
        self.api_status= 0
        self.api_error_count= self.api_error_count + 1


    def login(self):

        try:
            #headers = {'content-type': 'application/json'}
            url= api_path + '/login'
            
            headers = {'content-type': 'application/json' }
            params = { 'user_salt': self.identity['user_salt'], 'password': self.identity['password'], 'se_node_id': self.identity['node_id'] }
            # remove credentials from url
            response= requests.post(url, params=params, headers=headers, data=json.dumps(params), verify=False )
            
            #print response.status_code
            self.handle_info ( 'login response %s' % response.text )
            
            response_object= json.loads(response.text)
            if 'api_token' in response_object:
                self.configuration['api_token']= response_object['api_token']
                self.handle_info ('found token: %s' % self.configuration['api_token'] )
                self.api_ok()
                self.store_configuration()
            else:
                self.handle_info ('found problem: %s' % str(response_object) )
                self.api_error()
                
        except Exception as e:
            self.handle_info ('api login exception: %s' % e )
            self.api_error()
            
            
        return

    def is_valid_login(self ):
        if 'api_token' in self.configuration:
            return len(self.configuration['api_token']) > 0
        
        return False


    def clear_login(self):
        
        self.configuration['api_token']= ''


    def handle_login(self):
        if not self.is_valid_login():
            
            if 'api_token' in self.identity:
                self.configuration['api_token']= self.identity['api_token']
            else:
                self.login()
                
            if not self.is_valid_login():
                self.api_error()
                return False
        return True








    def send_status(self):
        
        if self.handle_login() == False:
            # pass here
            pass

        status = {}
        
        status['api_error_count']= self.api_error_count
        status['name']= self.identity['name']
        status['no_call_home']= self.ssh_tunnel
        status['version']= __version__

        no_status= 1
        if self.api_error_count:
            no_status= 2
        if self.ssh_tunnel:
            no_status= 4

        container = {}
        container['no_status']= no_status
        container['no_status_json']= status

        headers = {'content-type': 'application/json','x-access-token':self.configuration['api_token'] }
        
        url= api_path + '/node/status'
        
        params = {'se_api_token': self.configuration['api_token'], 'se_node_id': self.identity['node_id'] }

        try:
            response= requests.post (url, params=params,  headers=headers, data=json.dumps(container), verify=True )
            self.handle_server_response( response.text )
            self.api_ok()
            self.handle_info ( 'sent status to server' )

        except Exception as e:
            self.handle_exception(e, "send_status")
            self.api_error()






    def send_observations(self, observations ):

        if self.handle_login() == False:
            return -4
        
        headers = {'content-type': 'application/json','x-access-token':self.configuration['api_token'] }
        url= api_path + '/observation'
        params = {'se_api_token': self.configuration['api_token'], 'se_node_id': self.identity['node_id'] }
        
        try:
            
            if not self.api_mute:
                
                response= requests.post(url, params=params,  headers=headers, data=json.dumps(observations), verify=True )
                self.handle_server_response( response.text )
                
                if response.status_code >= 300:
                    self.handle_debug("send_observation error code %d" % (response.status_code) )
                    self.api_error()
                    self.cache_put_data(observations)
                    return -2
                else:
                    self.api_ok()
                    return 0
                    
            else:
                self.cache_put_data(observations)
                return -3
                
        except Exception as e:
            self.handle_exception(e, "send_observation")
            self.api_error()
            self.cache_put_data(observations)
            
        return -1









    def send_image(self, filename ):

        if self.handle_login() == False:
            pass
        
        headers = {'x-access-token':self.configuration['api_token'] }
        
        files = {'media': open(filename, 'rb') }
        url= api_path + '/observation'
        
        params = {'se_api_token': self.configuration['api_token'], 'se_node_id': self.identity['node_id'] }

        try:
            response= requests.post(url, params=params,  headers=headers, files=files, verify=True )
            self.handle_server_response( response.text )
            self.api_ok()
        except Exception as e:
            self.handle_exception(e, "send_image" )
            self.api_error()


    def handle_command(self,command):
        
        if not command:
            return

        self.command_queue.put(command)
        
        pass








    def handle_server_response(self, response ):
        try:
            response_object= json.loads(response)
            if response_object['status'] != 'ok':
                self.handle_error ( 'api server response: %s' % response )
                self.api_error()
            else:
                #print ( 'DEBUG response %s' % (response) )
                
                if response_object['no_call_home'] == 1 and self.ssh_tunnel != 2:    
                    self.ssh_tunnel_start= True
                    self.handle_info('found tunnel open request')

                elif response_object['no_call_home'] == 3:
                    self.ssh_tunnel_close= True
                    self.handle_info('found tunnel close request')
                    
                if response_object['no_update_period_s'] != self.updatePeriodS:
                    self.updatePeriodS= response_object['no_update_period_s']

                    self.handle_info('found new update period ' + str (response_object['no_update_period_s']) )

                    periodS= self.sleepPeriodS                    
                    try:
                        periodS= self.updatePeriodS
                    except ValueError:
                        pass
                    
                    if periodS > 0.5 and periodS <= 300.0:
                        self.sleepPeriodS= periodS
                
                self.handle_command(response_object['no_command'])


                
        except Exception as e:
            self.handle_exception(e, "handle_server_response")
            self.api_error()




        

    def build_observation_container(self):
        data= []
        return data
        
    def add(self, container, key, observation_time, value, unit ):
        observation= {}
        observation['key']= key
        observation['observation_time']= observation_time
        observation['value']= value
        observation['unit']= unit
        container.append(observation)




        


    def kill_tunnel(self):
        try:
            line = subprocess.check_output(['pgrep', '-f', 'ssh.*:localhost:'])
            pid = int(line.split(None, 1)[0])
            os.kill(pid, signal.SIGKILL)
            self.ssh_tunnel= 0
        except subprocess.CalledProcessError as e:
            self.handle_exception(e, "kill_tunnel")
            self.ssh_tunnel= 0


    def check_tunnel(self):
        try:    
            out = subprocess.check_output("pgrep -x ssh", shell=True)
            self.handle_info('checking tunnel ' + str ( out ) )
            self.ssh_tunnel= 2
        except subprocess.CalledProcessError as e:
            self.ssh_tunnel= 0
            pass


    def ensure_tunnel(self):
        try:    
            out = subprocess.check_output("pgrep -x ssh", shell=True)
            self.handle_info('checking tunnel ' + str ( out ) )
            self.ssh_tunnel= 2
            
        except subprocess.CalledProcessError as e:
            
            try:    
                self.handle_info('attempt to open tunnel')

                full_ssh_command= "ssh -p %s -i %s -fN -R %s:localhost:22 %s" % (self.ssh_port, self.key_file, self.port, self.username_ipaddress)
                ssh_output = subprocess.check_output(full_ssh_command, shell=True)
                if not ssh_output:
                    self.ssh_tunnel= 2
                    self.handle_info('tunnel open')
            
            except Exception as e:
                self.ssh_tunnel= 0
                self.ssh_tunnel_start= False
                self.handle_info('tunnel open failed ' + str (e) )


    def setup_tunnel(self):
        self.key_file = "/home/pi/.ssh/id_rsa_tunnel"
        self.port = "62224"
        self.username_ipaddress = "tunnel-user@195.201.32.107"
        self.ssh_port= "26126"



    def run_tunnel_worker (self):
        
        self.handle_info('starting tunnel worker')
        time.sleep( 10 )

        while self.state == iotclientRunning:

            if self.ssh_tunnel_start and self.ssh_last_command == 0:
                self.handle_info('starting tunnel')
                self.ensure_tunnel()
                self.send_status()
                self.ssh_tunnel_start= False
                self.ssh_last_command = 1


            if self.ssh_tunnel_close:
                self.kill_tunnel()
                self.send_status()
                self.ssh_tunnel_close= False
                self.ssh_last_command = 0
        
        
            time.sleep( 1 )






    def run_health_worker (self):
        
        self.handle_info('starting health worker')
        time.sleep( 10 )
        
        apiDownCounter= 0
        loggedApiErrorCount= 0

        while self.state == iotclientRunning:

            hardware_error_count= 0
            for driver_instance in self.driver_instances:
                hardware_error_count= hardware_error_count + driver_instance.get_hardware_error_count()

            if self.api_error_count > 0 and loggedApiErrorCount != self.api_error_count:
                self.handle_info('found api error count ' + str(self.api_error_count) )
                loggedApiErrorCount= self.api_error_count

            if hardware_error_count > 0:
                self.handle_info('found hardware error count ' + str(hardware_error_count) )

            if self.api_status == 0:
                apiDownCounter= apiDownCounter+ 1
            else:
                apiDownCounter= 0


            if hardware_error_count > 4 or self.api_error_count > 50 or apiDownCounter > 1200:
                
                self.handle_info('sync and shutdown')
                
                os.system('sudo sync')
                os.system('sudo shutdown -r now')

                self.handle_info('triggering restart of node')
                
                self.stop()


            time.sleep( 15 )


    def run_cache_worker (self):
        
        self.handle_info('starting cache worker')
        
        time.sleep( 10 )
        
        while True:
        
            try:
                if self.api_status == 1 and not self.api_mute:
                    
                    file_data_tuple= self.cache_get()
                    if file_data_tuple[0] != None and file_data_tuple[1] != None:
                        # attempt to transmit
                        if self.send_observations(file_data_tuple[1]) == 0:
                            # clean cache file: return value of 0 indicated successfull transmission
                            self.cache_clean( file_data_tuple )

    
                time.sleep( 1 )

            except Exception as e:
                
                self.handle_exception(e,"run_cache_worker")
                time.sleep( 10 )




    def run_command_worker (self):
        
        self.handle_info('starting command worker')

        time.sleep( 4 )
        
        while self.state == iotclientRunning:

            command= self.command_queue.get(True)
            self.handle_info('found command' + str(command) )
            
            # TODO: risky, since other commands may contain this string also        
            if 'cameraimage' in command:
                
                cameraplugin= self.get_plugin_instance('UsbCameraDriver')
                if cameraplugin:
                    cameraplugin.command(command)
                        
            time.sleep( 10 )


        # tear down





    def run_sensor_worker (self):
        
        self.handle_info('starting sensor worker')

        time.sleep( 5 )
        
        self.check_tunnel()
        self.send_status()
        
        statusCounter= 0
        while self.state == iotclientRunning:

            observations= self.build_observation_container()

            for driver_instance in self.driver_instances:
            
                try:
                    driver_instance.get_observations(observations)
                except Exception as e:
                    self.handle_debug(str(e))
                    pass    
                
            
            
            try:
                self.send_observations(observations)
            except:
                pass    
            
            if statusCounter > 10:
                self.send_status()
                statusCounter= 0
            else:
                statusCounter= statusCounter + 1

                        
            time.sleep( self.sleepPeriodS )


        # tear down






if __name__ == '__main__':
    
    handler= IOThandler()

    while handler.state == iotclientRunning:
        time.sleep( 5 )
        

    sys.exit(0)
