import time
import urllib.error

# import classes system (behaviour management)
import ClassesAceLogic  # this contains all the classes of the system
import ClassesAceHardware
import Database
from Notifier import Notifier
from Nightscout import Nightscout
from Doser import Doser
from ClassesAceLogic import AnomalousSgv
from SerialWrapper import SerialWrapper

from ClassesAceHardware import ButtonPower
from ClassesAceHardware import ButtonRequest

import threading
import sys

import logging

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s',
                    )

# PORT USB FOR DISPLAY

# definition button_listener for on/off
exit_flag = threading.Event()


# Glass IR sensor
flag_glass = threading.Event()
IR_glass = ClassesAceHardware.SensorIr(26)

thread_glass = threading.Thread(name='check glass',
                                target=IR_glass.thread_check_object,
                                args=(flag_glass, exit_flag),
                                daemon=False)

flag_juice = threading.Event()
IR_juice = ClassesAceHardware.SensorIr(13)

thread_juice = threading.Thread(name='check juice box',
                                target=IR_juice.thread_check_object,
                                args=(flag_juice, exit_flag), daemon=False)

thread_glass.start()
thread_juice.start()


# BUTTONS
power_button = ButtonPower(9, 10)  # button for rTURN OFF THE MACHINE
request_button = ButtonRequest(19, 20)  # button for requesting a new dose


flag_request_dose = threading.Event()  # definition request dose for on/off
flag_stop_request = threading.Event()  # definition request dose for on/off

# definition button_listener for on/off
thread_machine_on = threading.Thread(name='on_off_button',target=power_button.thread_button_pressed,args=(exit_flag ,),daemon=False)
thread_machine_on.start()

# definition request dose for on/off
thread_dose_request = threading.Thread(name='request dose button',target=request_button.thread_button_pressed,args=(flag_request_dose, flag_stop_request, exit_flag ), daemon=False)
thread_dose_request.start()