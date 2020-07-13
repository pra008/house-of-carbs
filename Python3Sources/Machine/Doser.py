import math
import time
import threading
import logging
from datetime import datetime

from ClassesAceLogic import Dose


logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s',
                    )


class Doser:
    """
    This class define the dosing component
    the goal of this class is to manage a dose when an hypoglycemia is detected
    to build the doser class is necessary:
    patient_id: who is receiving the dose
    juice: which juice will be deliver to the patient
    """
    def __init__(self, button_distribution, peristaltic_pump, blinking_led, patient_id, juice):
        """
        initialize the doser component
        :param patient_id: patient identifier
        :param juice: which juice will be delivered
        """
        self.dose = Dose(None, None, None, None, patient_id, None)
        self.juice = juice
        self.patient = patient_id
        self.buttonDistribution = button_distribution
        self.peristalticPump = peristaltic_pump
        self.blinkingLed = blinking_led
        self.liquid_unit = 100

    def dose_calculation(self, grams, liquid_unit):
        # TODO: the calculation is working under the assumption of the liquid unit
        """
        This function perform the dose calculation based on the juice and the grams to deliver
        the calculation is based on the 15/15 rules
        it defines the class element (dose)
        but it does not define the timestamp, it will define only ad the end of the distribution
        :param grams: amount of carbohydrates to deliver
        :param liquid_unit: (this parameter is based on juice information)
        :return: the dose calculated
        """
        # calculation based on the 15/15 rule
        # the timestamp will be inserted only when the distribution is complete
        amount = math.floor(float(grams * liquid_unit / self.juice.carbohydrates))
        self.liquid_unit = liquid_unit
        self.dose.amount_defined = amount
        self.dose.unit = 'milliliters'
        self.dose.juice_id = self.juice.id
        logging.info('dose calculated')
        return self.dose

    def eval_dose(self):
        """
        This function eval if the juice is enough for the dose
        :return: Boolean (True = valid dose; False = non valid dose)
        """
        if self.juice.amount < self.dose.amount_defined:
            # the amount of juice left is not enough
            return False
        else:
            # the dose is valid so the fruit juice amount can be decreased
            return True
        
    def distribution(self, flags, display):
        """
        This function makes the distribution real!
        :param flags:
        :param display:
        :return:
        """
        # define the event that will stop the thread
        flag_distribution_finished = threading.Event()  # the distribution is over
        event_button_pressed = threading.Event()  # the dose button was pressed

        seconds_to_blink = 2
        
        # define the button thread
        distribution_thread = threading.Thread(name='thread button distribution',
                                               target=self.buttonDistribution.thread_button_pressed,
                                               args=(event_button_pressed, flags.flag_exit))
        
        # define the thread for make the led blinking
        blinking_thread = threading.Thread(name='thread_blinking',
                                           target=self.blinkingLed.thread_blinking,
                                           args=(seconds_to_blink, flag_distribution_finished, flags.flag_exit))

        amount = 0
        amount_todo = self.dose.amount_defined

        try:
            # eval if the glass is inside the system (the juice presence was evaluated before calling the method
            possible_start = wait_for_the_glass(flags.flag_glass, flag_distribution_finished, flags.flag_exit, display,
                                               flags.flag_fail_due_to_glass)

            if possible_start:
                distribution_thread.start()  # start the thread for listening the button
                start = time.time()
                time.clock()
                elapsed = 0
                self.peristalticPump.activate()  # activate the pump
                blinking_thread.start()  # start the thread for led
                display.notify_dose(amount, amount_todo, True)
                flags.flag_distribution_start.set()  # flag for bot
                # start the distribution
                while (math.floor(self.peristalticPump.ml_sec * elapsed) < amount_todo) and not flag_distribution_finished.is_set():
                    elapsed = time.time() - start
                    amount = math.floor(self.peristalticPump.ml_sec * elapsed)
                    display.notify_dose(amount, amount_todo, False)  # communicate the amount delivered

                    # check the events that may kill the dose distribution
                    if not flags.flag_glass.is_set() or flags.flag_exit.is_set() or event_button_pressed.is_set():
                        flag_distribution_finished.set()  # this will kill the distribution

                    flag_distribution_finished.wait(1)

                # the distribution is complete (set all the flags)
                self.peristalticPump.deactivate()  # turn off the pump
                self.dose.amount_delivered = amount  # determinate the amount delivered
                flag_distribution_finished.set()
                flags.flag_distribution_done.set()  # bot flag
                flags.flag_distribution_start.clear()  # bot flag
                grams_delivered = math.floor((self.juice.carbohydrates * amount) / self.liquid_unit)
                communicate_distribution_done(flags, amount, amount_todo, grams_delivered, display)
            else:  # the distribution fails
                logging.warning('raise Exception: the distribution cannot start') 
                raise Exception('the distribution cannot start')

        except Exception as e:
            logging.warning('an Exception during the distribution:%s', e)
            self.dose.amount_delivered = 0
            self.dose.amount_defined = 0
            logging.info('a invalid dose will be stored inside the system')
        finally:  # no matter what happen but you save the dose
            timestamp = datetime.now(tz=None)
            self.dose.timestamp = int(timestamp.timestamp())
            return self.dose  # return to the system the dose delivered to the system

    def update_juice(self, warming_limit):
        """
        Based on the amount delivered by dose, the amount inside the juice is update and also its timestamp
        :param warming_limit: limited considered insufficient to deliver a new dose
        :return: true or false if the amount is consider critic for a future dose
        """
        self.juice.amount = self.juice.amount - self.dose.amount_delivered
        timestamp = datetime.now(tz=None)
        self.juice.timestamp = int(timestamp.timestamp())

        if self.juice.amount < warming_limit:
            return True
        else:
            return False

    def clear_tube(self, seconds):
        """
        This function is used to clear the pump after the juice is changed
        :param seconds: seconds used to delivery the amount
        :return:
        """
        self.peristalticPump.activate_for(seconds)


def wait_for_the_glass(flag_glass, flag_distribution_finished, flag_exit, display, flag_fail_due_to_glass):
    """
    This function wait if no glass is detected inside the system there are two possible cases:
    1) the glass is insert so the distribution may continue
    2) the glass is not insert so the distribution is over
    :param flag_glass: threading.Event if set, a glass is detected
    :param flag_exit: threading.Event if set, this flag stops all the threads
    :param flag_distribution_finished: threading.Event, this event is set if the distribution cannot start
    :param display: device used to display information
    :param flag_fail_due_to_glass: threading.Event if set, a broadcast message will be send to the user
    :return:
    """
    counter = 0
    max_tries = 5
    check_glass = False

    # the system goes inside it, when no glass is detected during distribution's beginning
    while not flag_glass.is_set() and not flag_exit.is_set():
        if counter == max_tries:
            flag_distribution_finished.set()  # the distribution will not continue
            display.notify_error('Dose FAIL\nNO Glass Found')
            logging.warning('the distribution cannot continue\nNO GLASS DETECTED')
            flag_fail_due_to_glass.set()
            flag_exit.wait(5)
            return False
        else:
            check_glass = True
            counter = counter + 1
            logging.warning('check for the glass try %s on %s', str(counter), str(max_tries))
            display.notify_error('ADD a Glass\ntry:' + str(counter) + ' on ' + str(max_tries))
            flag_exit.wait(10)

    # if reached this point the glass is added during the message
    if not flag_distribution_finished.is_set() and check_glass:
        seconds = 10
        while not flag_exit.is_set():
            display.notify_error('Glass Detected\ndose in ' + str(seconds) + ' sec')
            seconds = seconds - 1
            if seconds == 0:
                logging.info('the distribution is starting')
                break
            else:
                flag_exit.wait(1)
    
    return True
        

def communicate_distribution_done(flags, amount, amount_todo, grams_delivered, display):
    """
    this function communicate the end of the dose
    :param flags: collection of global flags
    :param amount: int, milliliters delivered
    :param amount_todo: int, milliliters that should be delivered
    :param grams_delivered: int, grams of quick carbohydrates delivered
    :param display: device used to display data and information
    :return:
    """
    if amount < amount_todo:
        message_to_display = 'dose stopped\n' + str(amount) + ' on ' + str(amount_todo) + ' ml'
    else:
        message_to_display = 'dose complete\n' + str(amount_todo) + ' ml'

    # make the alternative remember the number of carbohydrates delivered
    while flags.flag_glass.is_set() and not flags.flag_exit.is_set():  # loop that wait that the user take the data
        display.send_text(message_to_display)
        flags.flag_exit.wait(2)
        display.send_text(str(grams_delivered) + 'g carbs ready\nTAKE THE GLASS!')
        flags.flag_exit.wait(2)

    # the juice was retrieved from the user
    flags.flag_distribution_done.clear()
