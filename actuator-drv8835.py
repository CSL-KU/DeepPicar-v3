from gpiozero import PhaseEnableMotor, AngularServo
from gpiozero.pins.pigpio import PiGPIOFactory

MAX_SPEED = 480
CALIBRATION_FILE = "calibration.txt"
factory = PiGPIOFactory()

steer_motor = AngularServo(19, min_angle=-45, max_angle=45, pin_factory=factory)
drive_motor = PhaseEnableMotor(6, 13, pin_factory=factory)

speed_cap = 0

# init
def init(default_speed=0.5):
    global speed_cap
    speed_cap = default_speed
    steer_motor.value = 0
    drive_motor.stop()


def load_calibration():
    try:
        with open(CALIBRATION_FILE, 'r') as f:
            d = f.read().strip().split(',')
            steer = float(d[0])
            throttle = float(d[1]) if len(d) > 1 else 0
            return steer, throttle
    except (FileNotFoundError, ValueError, IndexError):
        return 0, 0

# throttle
def set_speed(speed):
    global speed_cap
    speed = max(-1, min(1, speed))
    if speed == 0:
        drive_motor.stop()
    elif speed > 0:
        drive_motor.forward(speed)
    else:
        drive_motor.backward(abs(speed))


def stop():
    drive_motor.stop()


# steering
def steer(angle, offset=0):
    offset, _ = load_calibration()

    target = (0 - angle) + offset

    if abs(target) < 1.0:
        target = 0

    steer_motor.angle = target


# exit
def turn_off():
    stop()
    steer_motor.detach()
