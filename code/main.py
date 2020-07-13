import os
import os.path
import threading
from ClassesAceHardware import PeristalticPump
import thread_machine
from Database import Database  # file name "database.sqlite"
from thread_bot import Bot
from ClassesAceLogic import Patient
from ClassesAceLogic import UnitDiabetes
from ClassesAceLogic import JuiceData
from datetime import datetime

TOKEN = 'whire your token here' # CHANGE FOR THE BOT

PATH = os.path.abspath(os.path.dirname(__file__))
DB_FILE =  PATH + "/data/database.sqlite"
"""
Hardware used inside the system only pins
"""
# VOLTAGE BOARD
MAX_VOLTAGE_MOTOR1 = 18
VOLT_MOTOR1 = 12

# MOTOR 1: PERISTALTIC PUMP
PUMP_ml_min = 85  # VELOCITY based on the pump tested
peristalticPump = PeristalticPump(PUMP_ml_min, VOLT_MOTOR1, 1, MAX_VOLTAGE_MOTOR1) # todo: put PUMP_ml_min as least argument


class GlobalFlags:
    """ Class that includes all the shared flags inside the system"""
    def __init__(self, f_exit, glass, juice, dose_may_be_required, distribution_start, distribution_done,
                 bot_request_dose, low_juice, no_juice_left, fail_due_to_glass):
        """
        :param f_exit: flag exit
        :param glass: flag glass
        :param juice:  flag juice
        :param dose_may_be_required: flag dose may be required
        :param distribution_start: flag distribution stat
        :param distribution_done:
        :param bot_request_dose:
        :param low_juice:
        :param no_juice_left:
        :param fail_due_to_glass:
        """
        self.flag_exit = f_exit
        self.flag_glass = glass
        self.flag_juice = juice
        self.flag_dose_may_be_required = dose_may_be_required
        self.flag_distribution_start = distribution_start
        self.flag_distribution_done = distribution_done
        self.flag_bot_request_dose = bot_request_dose
        self.flag_low_juice = low_juice
        self.flag_no_juice_left = no_juice_left
        self.flag_fail_due_to_glass = fail_due_to_glass


# definition button_listener for on/off
flag_exit = threading.Event()
flag_glass = threading.Event()  # definition glass IR
flag_juice = threading.Event()  # definition juice IR

# todo: define event used for next step (to make the bot talk with the machine
flag_distribution_start = threading.Event()
flag_distribution_done = threading.Event()
flag_dose_may_be_required = threading.Event()
flag_bot_request_dose = threading.Event()
flag_low_juice = threading.Event()
flag_no_juice_left = threading.Event()
flag_fail_due_to_glass = threading.Event()

#flag_glass instead of true
SYSTEM_FLAGS = GlobalFlags(flag_exit, flag_glass, flag_juice, flag_dose_may_be_required,
                           flag_distribution_start, flag_distribution_done, flag_bot_request_dose,
                           flag_low_juice, flag_no_juice_left, flag_fail_due_to_glass)

# verifies the patients inside the database
if not os.path.exists(DB_FILE):  # the file doesn't exist
    db = Database(DB_FILE)
    db.init_database_table()
    # define a general patient
    #patient = Patient(0,"Change your name", "TDM1", UnitDiabetes.MMOL.value, 3.9, 10, 5.9, "http.example.com",)
    #db.push_patient(patient)
    # define a general juice
    #juice = JuiceData(1, datetime.now(tz=None).replace(microsecond=0).timestamp(), 0, 0, patient.id)
    #db.push_juice(juice)
    db.close()


db = Database(DB_FILE)
last_patient = db.pull_last_patient()
if last_patient == None: #data never received
    PATIENT_ID = 0
else:
    PATIENT_ID = last_patient  
        

# define the machine thread
machine_thread = threading.Thread(name='machine thread', target=thread_machine.main_machine,
                                  args=(PATIENT_ID, peristalticPump, SYSTEM_FLAGS, DB_FILE),
                                  daemon=False)


bot = Bot(TOKEN, PATIENT_ID, peristalticPump, SYSTEM_FLAGS, DB_FILE)
# define the bot thread
bot_thread = threading.Thread(name='bot thread', target=bot.run,
                              args=(flag_exit,),
                              daemon=False)
machine_thread.start()
bot_thread.start()

while not flag_exit.is_set():
    pass
os.system("sudo shutdown -a now")


