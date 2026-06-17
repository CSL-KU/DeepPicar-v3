from picamera2 import Picamera2
from threading import Thread, Lock
import cv2
import time

use_thread = False
need_flip = False
frame = None
lock = Lock()
cam_thr = None
picam2 = None

# public API
# init(), read_frame(), stop()

def init(res=(320, 240), fps=30, threading=True):
    global picam2, use_thread, frame, cam_thr

    print("Initializing Picamera2...")
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"size": res, "format": "RGB888"})
    picam2.configure(config)
    picam2.start()

    # Allow camera to warm up
    time.sleep(1.0)

    if threading:
        use_thread = True
        cam_thr = Thread(target=__update, daemon=True)
        cam_thr.start()
        print("Camera thread started.")
    else:
        print("No camera threading.")

    print("Camera init completed.")


def __update():
    global frame, lock, use_thread
    while use_thread:
        tmp_frame = picam2.capture_array()
        if need_flip:
            tmp_frame = cv2.flip(tmp_frame, -1)
        with lock:
            frame = tmp_frame
    print("Camera thread finished...")
    picam2.stop()


def read_frame():
    global frame, lock
    if not use_thread:
        frame = picam2.capture_array()
        return cv2.flip(frame, -1) if need_flip else frame
    else:
        with lock:
            return frame.copy() if frame is not None else None


def stop():
    global use_thread
    print("Stopping camera...")
    use_thread = False
    time.sleep(0.5)
    if picam2:
        picam2.stop()


if __name__ == "__main__":
    init(threading=True)
    while True:
        f = read_frame()
        if f is not None:
            cv2.imshow("frame", f)
        ch = cv2.waitKey(1) & 0xFF
        if ch == ord('q'):
            stop()
            break
    cv2.destroyAllWindows()
