# coding=utf-8
# -*- coding: utf-8 -*-
'''
Created on 24. Sep. 2015

@author: dietmar
'''


from drivers.driver import Driver
import time
import os
import psutil 


#print('DEBUG: loaded raspberrypidriver' )


class RaspberryPiDriver(Driver):
    '''
    classdocs
    '''

    def __init__(self, parameters,logger ):
        '''
        Constructor
        '''
        Driver.__init__(self, parameters,logger )

        self.last_write_count= 0
        self.last_bytes_used_eth0= 0
        self.last_bytes_used_wlan0= 0


    def get_observations(self,container):

        res = os.popen('vcgencmd measure_temp').readline()
        temp= res.replace("temp=","").replace("'C\n","")
        temp_observation= self.observation( 'cpu_temperature', self.get_observation_time(), temp, u"°C" );
        container.append(temp_observation)
        
        
        cpu_usage = "{:.1f}".format( psutil.cpu_percent() )
        load_observation= self.observation('cpu_load', self.get_observation_time(), cpu_usage, '%' )
        container.append(load_observation)
        
        disk = psutil.disk_usage('/')
        disk_percent_used = "{:.1f}".format (disk.percent)
        disk_observation= self.observation('disk_usage', self.get_observation_time(), disk_percent_used, '%' )
        container.append(disk_observation)

        self.logger.debug ( self.name + ' delivers ' + str(temp_observation) + ", " + str(load_observation) + ", " + str (disk_observation) )


        disk_counts = psutil.disk_io_counters()

        if self.last_write_count:
            write_count= "{}".format (disk_counts.write_count-self.last_write_count)
            disk_write_observation= self.observation('disk_write_count', self.get_observation_time(), write_count, '' )
            container.append(disk_write_observation)

        self.last_write_count= disk_counts.write_count


        net_io_counters= psutil.net_io_counters(pernic=True)
        if 'eth0' in net_io_counters:
            eth0 = net_io_counters['eth0']
            bytes_used= eth0.bytes_recv + eth0.bytes_sent - self.last_bytes_used_eth0
            
            if self.last_bytes_used_eth0:
                eth0_observation= self.observation('lan_traffic', self.get_observation_time(), bytes_used, 'b' )
                container.append(eth0_observation)
                self.logger.debug(self.name + ' delivers ' + str(eth0_observation) )
                
            self.last_bytes_used_eth0= eth0.bytes_recv + eth0.bytes_sent    
                
                
                  
        if 'ppp0' in net_io_counters:
            ppp0 = net_io_counters['ppp0']
            bytes_used= ppp0.bytes_recv + ppp0.bytes_sent
            ppp0_observation= self.observation('ppp_traffic', self.get_observation_time(), bytes_used, 'b' )
            container.append(ppp0_observation)
            self.logger.debug (self.name + ' delivers ' + str(ppp0_observation) )
            
            
        if 'wlan0' in net_io_counters:
        
            wlan0 = net_io_counters['wlan0']
            bytes_used= wlan0.bytes_recv + wlan0.bytes_sent - self.last_bytes_used_wlan0
            
            if self.last_bytes_used_wlan0:
            
                wlan0_observation= self.observation('wifi_traffic', self.get_observation_time(), bytes_used, 'b' )
                container.append(wlan0_observation)
                self.logger.debug(self.name + ' delivers ' + str(wlan0_observation) )
            
            self.last_bytes_used_wlan0= wlan0.bytes_recv + wlan0.bytes_sent
            
        
        pass

    

if __name__ == '__main__':
    sensor= RaspberryPiDriver( {'name':'raspberrypidriver'} )
    for count in range(0,100):
        observations= []
        sensor.get_observations(observations)
        print ( observations )
        time.sleep(1)

