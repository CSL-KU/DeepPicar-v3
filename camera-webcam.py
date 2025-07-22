import cv2
from threading import Thread,Lock
import time

use_thread = False
need_flip = False
cap = None
frame = None
lock=Lock()

# public API
# init(), read_frame(), stop()

def init(res=(320, 240), fps=30, threading=True):
    print ("Initilize camera.")
    global cap, use_thread, frame, cam_thr

    cap = cv2.VideoCapture(0)

    cap.set(3, res[0]) # width
    cap.set(4, res[1]) # height
    cap.set(5, fps)

    # start the camera thread
    if threading:
        use_thread = True
        cam_thr = Thread(target=__update, args=())
        cam_thr.start()
        print ("start camera thread")
        time.sleep(1.0)
    else:
        print ("No camera threading.")

    print ("camera init completed.")

def __update():
    global frame
    global lock
    while use_thread:
        ret, tmp_frame = cap.read() # blocking read
        if need_flip == True:
            frame_ = cv2.flip(tmp_frame, -1)
        else:
            frame_ = tmp_frame
        lock.acquire()
        frame=frame_
        lock.release()
    print ("Camera thread finished...")
    cap.release()        

def read_frame():
    global frame
    global lock
    if not use_thread:
       ret, frame = cap.read() # blocking read
       return frame
    else:
        lock.acquire()
        frame_=frame
        lock.release()
        return frame_

def stop():
    global use_thread
    print ("Close the camera.")
    use_thread = False

if __name__ == "__main__":
    init()
    while True:
        frame = read_frame()
        cv2.imshow('frame', frame)
        ch = cv2.waitKey(1) & 0xFF
        if ch == ord('q'):
            stop()
            break
    
