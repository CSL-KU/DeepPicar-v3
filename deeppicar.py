#!/usr/bin/python
import os
import time
import atexit
import cv2
import math
import numpy as np
import sys
import params
import argparse
import array
from multiprocessing import Process, Lock, Array
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer

from PIL import Image, ImageDraw
import input_stream
import json
import logging

import signal
import sys
import shutil



##########################################################
# import deeppicar's sensor/actuator modules
##########################################################
camera   = __import__(params.camera)
actuator = __import__(params.actuator)

##########################################################
# global variable initialization
##########################################################
use_dnn = False
use_thread = True
view_video = False
fpv_video = False
enable_record = False

counter = 0

cfg_cam_res = (320, 240)
cfg_cam_fps = 30
cfg_throttle = 0.5 # 50% power.

frame_id = 0
angle = 0.0
period = 0.05 # sec (=50ms)

interpreter = None
input_index = None
output_index = None
finish = False
last_angle = None
# Web stream and file handling

        
##########################################################
# local functions
##########################################################

def deg2rad(deg):
    return deg * math.pi / 180.0

def rad2deg(rad):
    return 180.0 * rad / math.pi

def g_tick():
    t = time.time()
    count = 0
    while True:
        count += 1
        yield max(t + count*period - time.time(),0)

def turn_off():
    print('Finishing...')
    actuator.stop()
    camera.stop()
    cur_inp_stream.stop()

def preprocess(img):
    img = img[img.shape[0]//2:]
    img = cv2.resize(img, (params.img_width, params.img_height))
    # Convert to grayscale and readd channel dimension
    if params.img_channels == 1:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img = np.reshape(img, (params.img_height, params.img_width, params.img_channels))
    img = img / 255.
    return img


def load_model():
    global interpreter
    global input_index
    global output_index
    ##########################################################
    # import deeppicar's DNN model
    ##########################################################
    print ("Loading model: " + params.model_file)
    try:
        # Import TFLite interpreter from tflite_runtime package if it's available.
        from tflite_runtime.interpreter import Interpreter
        interpreter = Interpreter(params.model_file+'.tflite', num_threads=args.ncpu)
    except ImportError:
        # If not, fallback to use the TFLite interpreter from the full TF package.
        import tensorflow as tf
        interpreter = tf.lite.Interpreter(model_path=params.model_file+'.tflite', num_threads=args.ncpu)

    interpreter.allocate_tensors()
    input_index = interpreter.get_input_details()[0]["index"]
    output_index = interpreter.get_output_details()[0]["index"]

def signal_handler(sig, frame):
    global finish
    finish = True

signal.signal(signal.SIGINT, signal_handler)


##########################################################
# program begins
##########################################################
if __name__ == '__main__':    

    parser = argparse.ArgumentParser(description='DeepPicar main')
    parser.add_argument("-d", "--dnn", help="Enable DNN", action="store_true")
    parser.add_argument("-t", "--throttle", help="throttle percent. [0-100]%", type=float)
    parser.add_argument("-n", "--ncpu", help="number of cores to use.", type=int, default=1)
    parser.add_argument("-f", "--hz", help="control frequnecy", type=int)
    parser.add_argument("-g", "--gamepad", help="Use gamepad", action="store_true")
    parser.add_argument("-u", "--udp", help="Use gamepad from udp", action="store_true")
    parser.add_argument("-w", "--web", help="Use webpage based input", action="store_true")
    parser.add_argument("--fpvvideo", help="Take FPV video of DNN driving", action="store_true")
    args = parser.parse_args()


    if args.dnn:
        print ("DNN is on")
        use_dnn = True
    if args.throttle:
        cfg_throttle = args.throttle
        print ("throttle = %d pct" % (args.throttle))
    if args.hz:
        period = 1.0/args.hz
        print("new period: ", period)
    if args.fpvvideo:
        fpv_video = True
        print("FPV video of DNN driving is on")

    load_model()
        
    if args.gamepad:
        cur_inp_type= input_stream.input_type.GAMEPAD
    elif args.udp:
        cur_inp_type= input_stream.input_type.WEB
    else:
        cur_inp_type= input_stream.input_type.KEYBOARD
    new_inp_type=cur_inp_type
    cur_inp_stream= input_stream.instantiate_inp_stream(cur_inp_type, cfg_throttle)


    # initlaize deeppicar modules
    actuator.init(cfg_throttle)
    camera.init(res=cfg_cam_res, fps=cfg_cam_fps)

    g = g_tick()
    start_ts = time.time()

    frame_arr = []
    angle_arr = []
    # enter main loop
    while not finish:
        if use_thread:
            time.sleep(next(g))
        frame = camera.read_frame()
        ts = time.time()

        if new_inp_type != cur_inp_type:
            del cur_inp_stream
            cur_inp_type= new_inp_type
            cur_inp_stream= input_stream.instantiate_inp_stream(cur_inp_type, speed)        
        command, direction, speed = cur_inp_stream.read_inp()
        if command == 'r':
            print ("toggle record mode")
            if enable_record:
                keyfile.close()
                vidfile.release()
                frame_id= 0
            enable_record = not enable_record
        elif command == 't':
            print ("toggle video mode")
            view_video = not view_video
        elif command == 'd':
            print ("toggle DNN mode")
            use_dnn = not use_dnn
        elif command == 'q':
            finish = True
            break

        if not use_dnn:
            if not args.gamepad and not args.udp:
                    if command == 'a':
                        actuator.set_speed(args.throttle/100)
                        print ("accel")
                    elif command == 's':
                        actuator.stop()
                        print ("stop")
                    elif command == 'z':
                        actuator.set_speed(-args.throttle/100)
                        print ("reverse")
                    elif command == "j":
                        actuator.steer(-30)
                    elif command == "k":
                        actuator.steer(0)
                    elif command == "l":
                        actuator.steer(30)

            else:
                angle = direction
                actuator.steer(direction)
                print (f"Angle: {direction}")
                throttle = speed * (cfg_throttle/100)
                actuator.set_speed(throttle)
                print("THROTTLE", throttle)

        else:
            # 1. machine input
            img = preprocess(frame)
            img = np.expand_dims(img, axis=0).astype(np.float32)
            interpreter.set_tensor(input_index, img)
            interpreter.invoke()
            result, speed = interpreter.get_tensor(output_index)[0]

            action_limit = 10
            angle = result * 30

            try:
                with open("calibration.txt", "r") as f:
                    parts = f.read().strip().split(",")
                    throttle_off = float(parts[1]) if len(parts) > 1 else 0
            except:
                throttle_off = 0

            throttle = speed * (cfg_throttle / 100)
            throttle = throttle + throttle_off
            throttle = max(-1, min(1, throttle))

            actuator.set_speed(throttle)
            print(f"Speed: {throttle} (CPU)")

            actuator.steer(angle)
            print(f"Steering: {angle} (CPU)")



        dur = time.time() - ts
        if dur > period:
            print("%.3f: took %d ms - deadline miss."
                % (ts - start_ts, int(dur * 1000)))
        else:
            print("%.3f: took %d ms" % (ts - start_ts, int(dur * 1000)))

        if enable_record == True and frame_id == 0:
            # ensure directory exists
            os.makedirs(params.data_dir, exist_ok=True)
            # create files for data recording
            keyfile = open(params.rec_csv_file, 'w+')
            keyfile.write("ts_micro,frame,wheel,throttle\n") #TESTING
            try:
                fourcc = cv2.cv.CV_FOURCC(*'XVID')
            except AttributeError as e:
                fourcc = cv2.VideoWriter_fourcc(*'XVID')
            vidfile = cv2.VideoWriter(params.rec_vid_file, fourcc,
                                    cfg_cam_fps, cfg_cam_res)
        if enable_record == True:
            # increase frame_id
            frame_id += 1

            # write input (angle)
            str = "{},{},{},{}\n".format(int(ts*1000), frame_id, angle, throttle) #TESTING
            keyfile.write(str)


            # write video stream
            vidfile.write(frame)
            img_name = "cal_images/opencv_frame_{}.png".format(frame_id)
            cv2.imwrite(img_name, frame)
            #if frame_id >= 1000:
            #    print ("recorded 1000 frames")
            #    break
            print ("%.3f %d %.3f %.3f %d(ms)" %
            (ts, frame_id, angle, throttle, int((time.time() - ts)*1000)))

    turn_off()
