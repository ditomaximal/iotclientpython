# -*- coding: utf-8 -*-
'''
Created on 24. Sep. 2015
'''

__version__ = '0.0.4'
__author__  = "Dietmar Millinger"




import sys
sys.path.insert(1, '../')

import os
from drivers.driver import *
import time
from datetime import datetime
import threading
from PIL import Image, ImageChops
import math
import numpy as np
from io import BytesIO



stillFolderRoot= '/media/usb'
stillFolder= stillFolderRoot + '/images'
stillImagePeriodMillis = (60*60*1000)
initialStillImagePeriodMillis = (30*1000)



tempStillImageFile= '/tmp/still.jpg'
tempEntropyImageFile= '/tmp/entropy.jpg'


# os.system('fswebcam -r 320x240 -S 3 --jpeg 50 --save /home/pi/to_transmit/%H%M%S.jpg')



class UsbCameraDriver(Driver):
    '''
    driver for still images via pi internal camera
    '''

    def __init__(self, parameters, logger ):
        '''
        Constructor
        '''
        Driver.__init__(self, parameters, logger )

        self.max_entropy= 0
        self.debug_mode= False

        # SETUP folder for still images
        self.ensureStillFolder()
        
        self.sensor_worker= threading.Thread(target=self.run_sensor_worker)
        self.sensor_worker.setDaemon(True)
        self.sensor_worker.start()



        

    def get_observations(self,container):

        entropy= self.max_entropy
        self.max_entropy= 0
                
        change_observation= self.observation( 'camera_entropy', self.get_observation_time(), str("{:.1f}".format( entropy )), 'e' );
        container.append(change_observation)
        
        self.handle_debug ('driver ' + self.name + ' delivers ' + str(change_observation ) )



    def image_entropy(self,img):
        w,h = img.size
        a = np.array(img.convert('RGB')).reshape((w*h,3))
        h,e = np.histogramdd(a, bins=(16,)*3, range=((0,256),)*3)
        prob = h/np.sum(h) # normalize
        prob = prob[prob>0] # remove zeros
        return -np.sum(prob*np.log2(prob))



    def ensureStillFolder(self):
        try:
            os.makedirs(stillFolder, exist_ok=True)
        except Exception as e:
            pass
    
    def isStillFolderAvailable(self):
        try:
            if not os.path.isdir(stillFolderRoot):
                return False
            if not os.path.isdir(stillFolder):
                return False
            return True
        except Exception as e:
            pass
        return False

    
    def makeStillFileName(self):
        timestamp= self.get_observation_time_millis()
        return "%s/%d_img.jpg" % (stillFolder,timestamp) 
        

    def run_sensor_worker (self):
        
        self.nextStillImageMillis= self.get_observation_time_millis() + initialStillImagePeriodMillis
        time.sleep( 5 )
        
        self.last_image = None
        self.still_image = None
        
        self.handle_info ('starting camera thread')
        
        while self.shall_run:
            try:
                
                #
                # ENTROPY PART
                #
  
                # make entropy image              
                os.system('fswebcam -q -r 640x480 -S 3 --jpeg 90 --no-banner --save ' + tempEntropyImageFile + ' >/dev/null 2>&1' )

                self.new_image = Image.open(tempEntropyImageFile)
                

                if self.new_image and self.last_image:
                    
                    diff_image = ImageChops.difference(self.new_image,self.last_image)
                
                    entropy= self.image_entropy(diff_image)

                    if entropy > self.max_entropy:
                        self.max_entropy= entropy
                    
                    self.handle_debug ('found entropy {:.1f}'.format(entropy) )
                    
                
                self.last_image= self.new_image
                
                
                #
                # STILL IMAGE PART
                #

                hour= datetime.now().hour                
                if self.get_observation_time_millis() > self.nextStillImageMillis and hour > 5 and hour < 20:

                    self.handle_info ('starting still image at hour ' + str(hour) )
                    
                    if self.isStillFolderAvailable():                    

                        filename= self.makeStillFileName()
                        result= os.system('fswebcam -q -r 1640x922 -S 3 --jpeg 90 --no-banner --save ' + filename + ' >/dev/null 2>&1' )
                        
                        try:
                            value = int(result)
                        except ValueError:
                            value = 0
                        
                        if value:
                            self.increment_hardware_error_count()
                            self.handle_info ('fswebcam error ' + str(result) )
                        else:
                            self.clear_hardware_error_count()
                            
                            
                        self.nextStillImageMillis= self.get_observation_time_millis() + stillImagePeriodMillis

                    else:
                        self.handle_debug ('did not find still image folder' )
                

            except Exception as e:
                time.sleep( 10 )
                self.handle_debug ('exception ' + str(e) )
                pass
                        
                        
                        
            time.sleep( 20 )




if __name__ == '__main__':
    sensor= UsbCameraDriver( """{"width":1640,"height":"922"}""" )
    for count in range(0,1000):
        container= []
        sensor.get_observations(container)
        print ( container )
        time.sleep(10)

        
        
        
        
