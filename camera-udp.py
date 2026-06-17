import cv2
import time
from picamera2 import Picamera2
from threading import Thread, Lock
import socket

import params

frame = None
lock = Lock()

running = False
picam2 = None
thread = None
need_flip = False


def _capture_loop(sock, udp_ip, udp_port):
    global frame, running, picam2

    while running:
        f = picam2.capture_array()

        if need_flip:
            f = cv2.flip(f, -1)

        with lock:
            frame = f.copy()

        _, jpg = cv2.imencode(
            ".jpg",
            f,
            [int(cv2.IMWRITE_JPEG_QUALITY), 70]
        )

        try:
            sock.sendto(jpg.tobytes(), (udp_ip, udp_port))
        except Exception as e:
            print("UDP send error:", e)
            break


def init(res=(320, 240), fps=30, flip=False,
         udp_ip=params.dest_ip, udp_port=5000):

    global running, picam2, thread, need_flip

    need_flip = flip
    running = True

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)

    picam2 = Picamera2()

    config = picam2.create_video_configuration(
        main={"size": res, "format": "RGB888"},
        controls={"FrameRate": fps}
    )

    picam2.configure(config)
    picam2.start()

    time.sleep(0.5)

    thread = Thread(
        target=_capture_loop,
        args=(sock, udp_ip, udp_port),
        daemon=True
    )
    thread.start()

def stop():
        global running, picam2, thread

        running = False

        if thread:
            thread.join(timeout=2)

        if picam2:
            picam2.stop()

def read_frame():
    global frame
    with lock:
        if frame is None:
            return None
        return frame.copy()
