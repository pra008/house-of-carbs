# IMPORT MOTOR MANAGEMENT
from dual_g2_hpmd_rpi import motors, MAX_SPEED
import time

import logging
# BUTTON PIN MANAGEMENT
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)

logging.basicConfig(level=logging.DEBUG,
                    format='[%(levelname)s] (%(threadName)-10s) %(message)s',
                    )


class PeristalticPump:
    """ This class represent the pump for the distribution"""
    def __init__(self, ml_min, voltage, peristaltic_motor, motor_max_volt):
        """
        :param ml_min: ml_min: milliliters deliver per minute (common unit for pumps)
        :param voltage: volt to deliver to the pump
        :param peristaltic_motor: number of motor connected (1 or 2)
        :param motor_max_volt: maximum voltage delivered by board
        """
        # raise an exception is voltage is not positive or logic errors
        if voltage > motor_max_volt or voltage <= 0 or motor_max_volt <= 0:
            raise Exception('not possible')

        self.ml_min = ml_min
        self.ml_sec = float(ml_min * 0.017)

        if peristaltic_motor == 1:
            self.motor = motors.motor1  # import from library
        elif peristaltic_motor == 2:
            self.motor = motors.motor2  # import from library
        else:
            self.motor = None

        motor_speed = int((MAX_SPEED * voltage) / motor_max_volt)  # MAX_SPEED from library
        self.motor.setSpeed(motor_speed)
        self.on_off = False
        self.motor.disable()

    def activate_for(self, activation_time):
        """
        This function activate the pump for the seconds defined by its activation time
        :param activation_time: activation time (in seconds)
        """
        self.activate()
        start = time.time()
        time.clock()
        elapsed = 0

        while int(elapsed) <= activation_time:
            elapsed = time.time() - start
            time.sleep(0.1)

        self.deactivate()

    def activate(self):
        """
        This function turn on the motor without any time limit
        """
        if not self.on_off:  # in this case the motor is NOT already activate
            self.motor.enable()
            self.on_off = True

    def deactivate(self):
        """
        This function turn off
        :return:
        """
        if self.on_off:
            self.motor.disable()
            self.on_off = False


class BlinkingLed:
    """
    This class represent the led connected to the board (used during the distribution)
    """

    def __init__(self, voltage, peristaltic_motor, motor_max_volt):
        """
        :param voltage: volt to deliver to the led
        :param peristaltic_motor: number of motor connected (1 or 2)
        :param motor_max_volt: maximum voltage delivered by board
        """
        # raise an exception is voltage is not positive or logic errors
        if voltage > motor_max_volt or voltage <= 0 or motor_max_volt <= 0:
            raise Exception('not possible')

        if peristaltic_motor == 1:
            self.motor = motors.motor1  # import from library
        elif peristaltic_motor == 2:
            self.motor = motors.motor2  # import from library
        else:
            self.motor = None

        motor_speed = int((MAX_SPEED * voltage) / motor_max_volt)  # MAX_SPEED from library
        self.motor.setSpeed(motor_speed)
        self.on_off = False
        self.motor.disable()

    def turn_on(self):
        """
        This function turns on the led without any limit of time
        """
        if not self.on_off:  # in this case the motor is NOT already activate
            self.motor.enable()
            self.on_off = True

    def turn_off(self):
        """
        This function turns off the led
        """
        if self.on_off:
            self.motor.disable()
            self.on_off = False

    def thread_blinking(self, interval_time, stop_flag, exit_flag):
        """
        This function start the blinking but without any limit of time
        the function stops when the event is set
        :param interval_time: seconds of alternative blinking
        :param stop_flag: threading.Event if set, the thread is forced to stop
        :param exit_flag: threading.Event that stop all the threads
        :return:
        """
        logging.info('Starting')
        start = time.time()
        time.clock()

        while not exit_flag.is_set():

            if stop_flag.is_set():
                break

            elapsed = time.time() - start
            if int(elapsed) % interval_time == 0:
                self.turn_on()
            else:
                self.turn_off()

            exit_flag.wait(0.1)

        # stop the led blinking
        self.turn_off()
        logging.info('Exiting')


class ButtonDistribution:
    """
    This class represent the button used for the distribution (it used to stop the distribution)
    """
    def __init__(self, pin_p, pin_n):
        """
        :param pin_p: positive pin
        :param pin_n: negative pin
        """
        self.pin_p = pin_p
        self.pin_n = pin_n
        GPIO.setup(pin_p, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(pin_n, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    def thread_button_pressed(self, event_button_pressed, flag_exit):
        """
        This thread when dies means that the distribution is over
        :param event_button_pressed: threading.Event if set, the button was pressed
        :param flag_exit: threading.Event that stop all the threads
        :return:
        """
        logging.info('Starting')
        event_button_pressed.clear()

        while not flag_exit.is_set():

            if GPIO.input(self.pin_n) == 1:  # the button was pressed
                flag_exit.wait(1)
                if GPIO.input(self.pin_n) == 1:
                    event_button_pressed.set()
                    logging.info('the button was pressed')
                    break

            flag_exit.wait(0.1)

        # out of loop
        logging.info('Exiting')


class ButtonPower:
    """
    This class is used to stop the machine and turn off all the system
    """
    def __init__(self, pin_p, pin_n):
        """
        :param pin_p: positive pin
        :param pin_n: negative pin
        """
        self.pin_p = pin_p
        self.pin_n = pin_n
        GPIO.setup(pin_p, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(pin_n, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    def thread_button_pressed(self, exit_flag):
        """
        If the button is pressed than the event is set
        :param exit_flag: threading.Event if set, this flag stops all the threads
        :return:
        """
        logging.info('Starting')
        exit_flag.clear()

        while not exit_flag.is_set():
            if GPIO.input(self.pin_n) == 1:
                exit_flag.wait(1)  # it was 0.1 before
                if GPIO.input(self.pin_n) == 1:
                    break

        # the button was pressed
        exit_flag.set()
        logging.info('Exiting')


class SensorIr:
    """
    This class represent the sensor used to verify if a juice or a glass is available
    """

    def __init__(self, pin):
        """
        :param pin: Pin used to read the input
        """
        self.pin = pin
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def thread_check_object(self, event_object, exit_flag):
        """
        The thread is interrupted when the beam is interrupted and it also set an event
        :param event_object: threading.Event if set: object is detected
        :param exit_flag: threading.Event if set, this flag stops all the threads
        :return:
        """
        logging.info('Starting')
        event_object.clear()

        while not exit_flag.is_set():
            if GPIO.input(self.pin) == 1:  # the beam is NOT interrupted (NO OBJECT)
                if event_object.is_set():
                    event_object.clear()
                    logging.info('No object detected')
                
            if GPIO.input(self.pin) == 0:  # the beam is interrupted
                if not event_object.is_set():
                    event_object.set()
                    logging.info('The object is detected')
              
            exit_flag.wait(0.1)

        # out of the loop
        event_object.clear()
        logging.info('Exiting')


class ButtonRequest:
    """
    This button represent the possibility to ask for a dose
    """
    def __init__(self, pin_p, pin_n):
        """
        :param pin_p: positive pin
        :param pin_n: negative pin
        """
        self.pin_p = pin_p
        self.pin_n = pin_n
        GPIO.setup(pin_p, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(pin_n, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    def thread_button_pressed(self, event_button_pressed, stop_flag, exit_flag):
        """
        this thread checks if the button it is pressed
        :param event_button_pressed: threading.Event if set, the button is pressed
        :param stop_flag: threading.Event if set, the thread is forced to stop
        :param exit_flag: threading.Event if set, this flag stops all the threads
        :return:
        """
        logging.info('Starting')
        event_button_pressed.clear()
        stop_flag.clear()

        while not exit_flag.is_set():
            
            if GPIO.input(self.pin_n) == 1:
                exit_flag.wait(1)  # it was 0.1 before
                if GPIO.input(self.pin_n) == 1:
                    event_button_pressed.set()
                    stop_flag.set()
                    logging.info('the button was pressed')
            exit_flag.wait(0.2)

        stop_flag.set()

        logging.info('Exiting')





