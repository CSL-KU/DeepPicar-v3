#!/usr/bin/env python
##########################################################
# camera module selection
#   "camera-webcam" "camera-null"
##########################################################
camera="camera-webcam"

##########################################################
# actuator selection
#   "actuator-drv8835", "actuator-adafruit_hat"
#   "actuator-null"
##########################################################
actuator="actuator-drv8835"

##########################################################
#Address to send video to
##########################################################
dest_ip = "" # place ip of device on same network like : "xxx.xxx.x.xx"
##########################################################
# input config 
##########################################################
img_width = 200
img_height = 66
img_channels = 3

##########################################################
# model selection
#   "model_large"   <-- nvidia dave-2 model
##########################################################
model_name = "model_large"
model_file = "./models/{}-{}x{}x{}".format(model_name[6:], img_width, img_height, img_channels)

##########################################################
# recording config 
##########################################################
data_dir = './data/'
rec_vid_file = data_dir + "out-video.avi"
rec_csv_file = data_dir + "out-key.csv"
