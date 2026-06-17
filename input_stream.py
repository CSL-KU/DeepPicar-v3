#!/usr/bin/python3
import os
import time
import atexit
import termios, fcntl, sys, os
import select
import socket
import struct

import asyncio
import json

from datetime import datetime

from multiprocessing import Process, Lock, Array, Value



 
 
JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS   = 0x02
 
LISTEN_IP   = "0.0.0.0"
LISTEN_PORT = 5005


class input_stream:
    def __init__(self, speed=0.5):
        self.buffer = ' '
        self.direction = 0.
        self.speed = speed

    def read_inp():
        return self.buffer, self.direction

    def stop(self):
        return

    def __del__(self):
        self.stop()


class input_kbd(input_stream):
    def __init__(self, speed=50):
        super().__init__(speed)

    def init(self):
        fd = sys.stdin.fileno()
        # save old state
        flags_save = fcntl.fcntl(fd, fcntl.F_GETFL)
        attrs_save = termios.tcgetattr(fd)
        # make raw - the way to do this comes from the termios(3) man page.
        attrs = list(attrs_save) # copy the stored version to update
        # iflag
        attrs[0] &= ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK 
                      | termios.ISTRIP | termios.INLCR | termios. IGNCR 
                      | termios.ICRNL | termios.IXON )
        # oflag
        attrs[1] &= ~termios.OPOST
        # cflag
        attrs[2] &= ~(termios.CSIZE | termios. PARENB)
        attrs[2] |= termios.CS8
        # lflag
        attrs[3] &= ~(termios.ECHONL | termios.ECHO | termios.ICANON
                      | termios.ISIG | termios.IEXTEN)
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        # turn off non-blocking
        fcntl.fcntl(fd, fcntl.F_SETFL, flags_save & ~os.O_NONBLOCK)
        # read a single keystroke
        return (flags_save, attrs_save)
    
    def deinit(self,state):
        fd = sys.stdin.fileno()
        # restore old state
        termios.tcsetattr(fd, termios.TCSAFLUSH, state[1])
        fcntl.fcntl(fd, fcntl.F_SETFL, state[0])
     
    def read_inp(self):
        state = self.init()    
        r, w, e = select.select([sys.stdin], [], [], 0.000)
        self.buffer = ' '
        for s in r:
            if s == sys.stdin:
                self.buffer = sys.stdin.read(1)
                break
        self.deinit(state)
        return self.buffer, self.direction, self.speed

class input_gamepad(input_stream):
    def __init__(self, speed=0.5):
        self.CALIBRATION_FILE = 'calibration.txt'
        self.shared_arr = Array('d', [0.]*9) # joystick pos and other buttons and finish state
        #self.finish = Value('i', 1)
        self.lock=Lock()
        self.gamepad_process = Process(target=self.inputs_process, \
                args=(), daemon=True )#args=(self.shared_arr, self.finish, lock,))
        self.gamepad_process.start()
        super().__init__(speed)

    
    def load_calibration(self):
        try:
            with open(self.CALIBRATION_FILE, 'r') as f:
                data = f.read().strip().split(',')

                steering_offset = float(data[0])

                if len(data) > 1:
                    throttle_offset = float(data[1])
                else:
                    throttle_offset = 0

                return steering_offset, throttle_offset

        except (FileNotFoundError, ValueError):
            return 0, 0

    def save_calibration(self, steering_offset, throttle_offset):
        with open(self.CALIBRATION_FILE, 'w') as f:
            f.write(f"{steering_offset:.4f},{throttle_offset:.4f}")



    def inputs_process(self): #shr_gamepad_state, finish, lock):
        import inputs
        pads = inputs.devices.gamepads
        if len(pads) == 0:
            raise Exception("Couldn't find any Gamepads!")

        #shr_gamepad_state, finish, lock = self.shared_arr, self.finish, self.lock
        shr_gamepad_state, lock = self.shared_arr, self.lock
        # Empty buffer
        gamepad_events = inputs.get_gamepad()
        print('Joystick is ready')

        disable_joystick=False
        offset, throttle_offset = self.load_calibration()
        while True: #finish.value != 0:
            gamepad_events = inputs.get_gamepad()
            if disable_joystick and time.time() - gamepad_disable_time > 0.3: # 300 ms
                disable_joystick = False
            lock.acquire()
            for event in gamepad_events:
                if event.ev_type == 'Absolute' and event.code == 'ABS_Z':
                    val = int(event.state)
                   
                    center = 127.5
                    if True: # calib, dead area
                        if abs(val-center) < 5:
                            normalized = 0 
                        else:
                            normalized = max(-1.0, min(1.0, (val - center) / 127.5))
                        angle = round(normalized *30)
                        shr_gamepad_state[0] = angle
                if event.ev_type == 'Absolute' and event.code == 'ABS_Y':
                    val = int(event.state)

                    center = 128
                    deadzone = 5

                    if abs(val - center) < deadzone:
                        shr_gamepad_state[8] = 0
                    else:
                        shr_gamepad_state[8] = max(-1.0, min(1.0, -(val - center) / 128))
    
                elif event.ev_type == 'Absolute' and event.code == 'ABS_HAT0Y':
                    print(throttle_offset)
                    if int(event.state) == -1:
                        if throttle_offset < .5:
                            throttle_offset = round(throttle_offset + 0.1, 1)
                            self.save_calibration(offset, throttle_offset)
                    elif int(event.state) == 1:
                        if throttle_offset > 0:
                            throttle_offset = round(throttle_offset - 0.1, 1)
                            self.save_calibration(offset, throttle_offset)
                elif event.ev_type == 'Absolute' and event.code == 'ABS_HAT0X':
                    if int(event.state) == -1:
                        shr_gamepad_state[0]= -1.
                    elif int(event.state) == 1:
                        shr_gamepad_state[0]= 1.
                    elif int(event.state) == 0:
                        shr_gamepad_state[0]= 0.
                elif event.ev_type == 'Key' and event.code == 'BTN_NORTH' and int(event.state) == 1:
                    shr_gamepad_state[3]=1. # stop
                elif event.ev_type == 'Key' and event.code == 'BTN_EAST' and int(event.state) == 1:
                    shr_gamepad_state[4]=1. # record
                elif event.ev_type == 'Key' and event.code == 'BTN_START' and int(event.state) == 1:
                    shr_gamepad_state[5]=1.
                elif event.ev_type == 'Key' and event.code == 'BTN_SELECT':
                    shr_gamepad_state[6]=1.
                    #finish.value=1
                elif event.ev_type == 'Key' and event.code == 'BTN_WEST' and int(event.state) == 1:
                    shr_gamepad_state[7]=1.
                elif event.ev_type == 'Key' and event.code == 'BTN_SOUTH' and int(event.state) == 1:
                    shr_gamepad_state[0]=0.
                    disable_joystick=True
                    gamepad_disable_time = time.time()
                elif event.ev_type == 'Key' and event.code == 'BTN_TR':  # Right trigger button
                    if offset > -10:
                        offset -= 1
                        self.save_calibration(offset, throttle_offset)
                elif event.ev_type == 'Key' and event.code == 'BTN_TL':  # Left trigger button
                    if offset < 10:
                        offset += 1
                        self.save_calibration(offset, throttle_offset)
        
            lock.release()

    def read_inp(self):
        self.buffer = ' '
        self.lock.acquire()
        if self.shared_arr[1] == 1.:
            self.shared_arr[1] = 0.
            self.buffer='a'
            #print ("accel")
        elif self.shared_arr[2] == 1.:
            self.shared_arr[2] = 0.
            self.buffer='z'
            #print ("reverse")
        elif self.shared_arr[3] == 1.:
            self.shared_arr[3] = 0.
            self.buffer='s'
            #print ("stop")
        elif self.shared_arr[4] == 1.:
            self.shared_arr[4] = 0.
            self.buffer='r'
            #print ("toggle record mode")
        elif self.shared_arr[5] == 1.:
            self.shared_arr[5] = 0.
            self.buffer='d'
            #print ("toggle DNN mode")
        elif self.shared_arr[6] == 1.:
            self.shared_arr[6] = 0.
            self.buffer='q'
            #self.finish.value = 0
        elif self.shared_arr[7] == 1.:
            self.shared_arr[7] = 0.
            self.buffer='t'
            #print ("toggle video mode")

        self.direction = self.shared_arr[0]
        self.speed = self.shared_arr[8]
        self.lock.release()

        return self.buffer, self.direction, self.speed

    def stop(self):
        #self.finish.value = 0
        self.gamepad_process.terminate()


# class input_udp_gamepad(input_stream):
#     def __init__(self, speed=0.5):
#         self.shared_arr = Array('d', [0.] * 9)
#         self.lock = Lock()
#         self.gamepad_process = Process(
#             target=self.inputs_process, args=(), daemon=True
#         )
#         self.gamepad_process.start()
#         super().__init__(speed)

#     CALIBRATION_FILE = 'calibration.txt'
#     def load_calibration(self):
#         try:
#             with open(self.CALIBRATION_FILE, 'r') as f:
#                 return float(f.read().strip())
#         except (FileNotFoundError, ValueError):
#             return 0

#     def save_calibration(self, center):
#         with open(self.CALIBRATION_FILE, 'w') as f:
#             f.write(str(center))
 
#     def inputs_process(self):
#         sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         sock.bind((LISTEN_IP, LISTEN_PORT))
#         print('Joystick is ready')
 
#         shr_gamepad_state, lock = self.shared_arr, self.lock
 
#         disable_joystick = False
#         gamepad_disable_time = 0.0
#         offset = self.load_calibration()
#         while True:
            
#             data, _ = sock.recvfrom(8)
#             if len(data) != 8:
#                 continue
 
#             _, value, event_type, number = struct.unpack("<IhBB", data)

#             if disable_joystick and time.time() - gamepad_disable_time > 0.3:
#                 disable_joystick = False
 
#             lock.acquire()
 
#             if event_type == JS_EVENT_AXIS:
#                 center = 32667/2
#                 if event_type == JS_EVENT_AXIS:
#                     if number == 0:  # steering: -32767 to 32767
#                         val = value
#                         normalized = val / 32767.0
#                         if abs(normalized) < 0.05:
#                             normalized = 0.0
#                         else:
#                             normalized = max(-1.0, min(1.0, normalized))
#                         angle = round(normalized * 30, 1)
#                         shr_gamepad_state[0] = angle

#                     elif number == 2:  # throttle: 0 to 32767
#                         val = value / 32767.0
#                         if val < 0.05:
#                             shr_gamepad_state[8] = 0.0
#                         else:
#                             shr_gamepad_state[8] = val
 
 
#             elif event_type == JS_EVENT_BUTTON and value == 1:
#                 if number == 34:  #record
#                     shr_gamepad_state[4] = 1.
#                 elif number == 35:  #dnn
#                     shr_gamepad_state[5] = 1.
#                 elif number == 24:  #quit
#                     shr_gamepad_state[6] = 1.
#                 elif number == 13:  # Right trigger button
#                     if offset > -10:
#                         offset -= 1
#                         self.save_calibration(offset)
#                 elif number == 12:  # Left trigger button
#                     if offset < 10:
#                         offset += 1
#                         self.save_calibration(offset)
#             lock.release()
 
#     def read_inp(self):
#         self.buffer = ' '
#         self.lock.acquire()
#         if self.shared_arr[1] == 1.:
#             self.shared_arr[1] = 0.
#             self.buffer = 'a'
#         elif self.shared_arr[2] == 1.:
#             self.shared_arr[2] = 0.
#             self.buffer = 'z'
#         elif self.shared_arr[3] == 1.:
#             self.shared_arr[3] = 0.
#             self.buffer = 's'
#         elif self.shared_arr[4] == 1.:
#             self.shared_arr[4] = 0.
#             self.buffer = 'r'
#         elif self.shared_arr[5] == 1.:
#             self.shared_arr[5] = 0.
#             self.buffer = 'd'
#         elif self.shared_arr[6] == 1.:
#             self.shared_arr[6] = 0.
#             self.buffer = 'q'
#         elif self.shared_arr[7] == 1.:
#             self.shared_arr[7] = 0.
#             self.buffer = 't'
 
#         self.direction = self.shared_arr[0]
#         self.speed     = self.shared_arr[8]
#         self.lock.release()
 
#         return self.buffer, self.direction, self.speed
 
#     def stop(self):
#         self.gamepad_process.terminate()
 

class input_type:
    KEYBOARD=0
    GAMEPAD=1
    WEB=2

def instantiate_inp_stream(inp_type, def_throttle):
    inp_stream = None
    if inp_type == input_type.KEYBOARD:
        inp_stream= input_kbd(def_throttle)
    elif inp_type == input_type.GAMEPAD:
        inp_stream= input_gamepad(def_throttle)
    elif inp_type == input_type.WEB:
        inp_stream= input_udp_gamepad(def_throttle)

    return inp_stream
