import threading
import logging
import urllib.error  # error catching cgm data
from Notifier import Notifier  # display notification
from ClassesAceLogic import Threshold  # timing threshold of the system
from Database import Database  # database sqlite functionality
from Nightscout import Nightscout  # parser and checker CGM data from Nightscout (pebble)
from ClassesAceLogic import AnomalousSgv  # enum that contains the possible evaluation of data
from datetime import datetime, timedelta
from Doser import Doser
from ClassesAceHardware import ButtonPower
from ClassesAceHardware import ButtonRequest
from ClassesAceHardware import SensorIr
from ClassesAceHardware import BlinkingLed
from ClassesAceHardware import ButtonDistribution

# SYSTEM THRESHOLDS
SEC_RECENT = 900        # seconds to consider a data recent, DEFAULT = 15 minutes (900 seconds)
SEC_FETCH = 300         # seconds to consider to request data from Nightscout, DEFAULT = 5 minutes
SEC_DOSE = 900          # seconds to consider the patient under treatment, DEFAULT = 15 minutes
SEC_ERROR = 60          # seconds to re-try the connection
SEC_INVESTIGATION = 60  # seconds to check important situation
THRESHOLD = Threshold(SEC_RECENT, SEC_DOSE, SEC_FETCH, SEC_INVESTIGATION, SEC_ERROR)

"""
Display settings via usb
"""
PORT_DISPLAY = '/dev/ttyACM0'
SEC_ALT_MESS = 5  # seconds used for alternative message
ALT_MESSAGE_MAX = 5  # times that the message will be display
# total time of alternative messages = SEC_ALT_MESS * ALT_MESSAGE_MAX


# todo: add the log file
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s',
                    )

# parameters for try the reconnection in case of server problems
MAX_TRIES = 5
# BUTTONS
power_button = ButtonPower(9, 10)  # button for rTURN OFF THE MACHINE
request_button = ButtonRequest(19, 20)  # button for requesting a new dose
distribution_button = ButtonDistribution(19, 20)
# IR SENSORS
ir_glass = SensorIr(26)
ir_juice = SensorIr(21)
# MOTOR 2: BLINKING LED
MAX_VOLTAGE_MOTOR2 = 18
VOLT_MOTOR2 = 4
request_led = BlinkingLed(VOLT_MOTOR2, 2, MAX_VOLTAGE_MOTOR2)  # LED distribution button


flag_request_dose = threading.Event()  # definition request dose for on/off
flag_stop_request = threading.Event()  # definition request dose for on/off


def main_machine(patient_id, peristaltic_pump, flags, DB_FILE):
    """
    :param patient_id: patient identifier to assign the machine to someone else
    :param peristaltic_pump: peristaltic_pump by the system
    :param flags: flags defined by the system
    :return:
    """
    logging.info("thread of the machine starts")
    # definition button_listener for on/off
    thread_machine_on = threading.Thread(name='on_off_button',
                                         target=power_button.thread_button_pressed,
                                         args=(flags.flag_exit,),
                                         daemon=False)
    # definition request dose for on/off
    thread_dose_request = threading.Thread(name='request dose button',
                                           target=request_button.thread_button_pressed,
                                           args=(flag_request_dose, flag_stop_request, flags.flag_exit),
                                           daemon=False)
    # definition glass IR
    thread_glass = threading.Thread(name='check glass',
                                    target=ir_glass.thread_check_object,
                                    args=(flags.flag_glass, flags.flag_exit),
                                    daemon=False)
    # definition juice IR
    thread_juice = threading.Thread(name='check juice box',
                                    target=ir_juice.thread_check_object,
                                    args=(flags.flag_juice, flags.flag_exit),
                                    daemon=False)

    # no error at the beginning
    errors = False
    counter_error = 0

    # starting the listener for pressing the exit button
    thread_machine_on.start()

    # starting the thread for pressing the dose request
    thread_dose_request.start()

    # todo: uncomment the next lines
    # starting the thread for check the glass
    thread_glass.start()

    # starting the thread for check the juice
    # thread_juice.start()

    # define the display used for notify data
    display = Notifier(PORT_DISPLAY)
    # infinite loop wait for shutdown button
    while not flags.flag_exit.is_set():
        db = Database(DB_FILE)
        patient = db.pull_patient(patient_id)
        logging.info(patient)
        source_cgm = Nightscout(patient)

        flag_request_dose.clear()
        flag_stop_request.clear()
        flags.flag_juice.set()  # todo: remove it
        #flags.flag_glass.set()  # todo: remove it

        try:  # retrieve the glucose value -> with management of error
            cgm = source_cgm.get_cgm()  # retrieve data from Nightscout (based on patient settings)

        except urllib.error.HTTPError:
            logging.warning('HTTP ERROR')
            errors = True  # turn on the flag of errors
            request_led.turn_off()  # turn off the led for dose request
            flags.flag_dose_may_be_required.clear()
            display.notify_error_connection("HTTP ERROR!", True)  # display the head of the error

        except urllib.error.URLError:  # this error include content to short
            logging.warning('URL ERROR')
            errors = True
            request_led.turn_off()  # turn off the led for dose request
            flags.flag_dose_may_be_required.clear()
            display.notify_error_connection("URL ERROR!", True)  # display the head of the error
        # todo: except the invalid data

        except Exception as e:
            logging.warning('Checkout this error',e)
            errors = True
            request_led.turn_off()  # turn off the led for dose request
            flags.flag_dose_may_be_required.clear()
            display.notify_error_connection("NO DATA!", True)  # display the head of the error

        else:  # no errors are detected
            errors = False  # reset any error from previous
            counter_error = 0  # reset error counter
            db.push_unique_cgm(cgm)  # store the glucose value
            anomaly = source_cgm.eval_cgm(cgm)  # eval data value based on the threshold
            recent = source_cgm.is_recent(cgm, THRESHOLD.sec_recent)  # eval data recent or not
            last_dose = db.pull_last_dose(patient.id)  # retrieve the last dose received from the patient
            treatment_ingoing = source_cgm.under_treatment(last_dose, cgm, THRESHOLD.sec_dose)
            cgm_increased = source_cgm.rising_glucose(cgm)

            # case 1: data recent and hypoglycemia is detected
            if (not cgm_increased and not treatment_ingoing) and anomaly == AnomalousSgv.HYPO and recent:
                request_led.turn_off()  # turn off the led for dose request
                flags.flag_dose_may_be_required.clear()

                # eval the hypoglycemia (severe =  20 grams, not_severe = 15 grams)
                last_hour_date_time = datetime.now(tz=None) - timedelta(hours=2)
                last_hour_date_time = int(last_hour_date_time.timestamp())
                other_cgm = db.pull_cgm_from(patient.id, last_hour_date_time)
                severe_hypo = source_cgm.eval_severe_hypoglycemia(cgm, other_cgm)

                # try to deliver the juice (if it's possible)
                result = manager_hypo(db, severe_hypo, patient.id, display, flags, peristaltic_pump)
                if not result:  # the distribution failed
                    # display data and wait another iteration
                    display.notify_value(anomaly, treatment_ingoing, cgm)
                    # todo: verify the feedback
                    flags.flag_exit.wait(
                        THRESHOLD.sec_investigation / 2)  # in case of not successful distribution display data

            # case 2: data recent and the patient may ask for a dose
            elif (not cgm_increased and not treatment_ingoing) and anomaly == AnomalousSgv.TO_INVESTIGATE and recent:
                request_led.turn_on()
                flags.flag_dose_may_be_required.set()
                display.notify_value(anomaly, treatment_ingoing, cgm)  # display data
                flag_stop_request.wait(THRESHOLD.sec_investigation)

                # case 2.1 the patient request a dose (he press the button) or use the bot
                if flag_request_dose.is_set() or flags.flag_bot_request_dose.is_set():
                    request_led.turn_off()
                    flags.flag_dose_may_be_required.clear()
                    severe_hypo = True
                    success = manager_hypo(db, severe_hypo, patient.id, display, flags, peristaltic_pump)
                    # when the bot request a dose, it it early insert into the system
                    if flags.flag_bot_request_dose.is_set() and not success:
                        fail_dose = db.pull_last_dose(patient.id)
                        db.remove_dose(fail_dose)

                    flags.flag_bot_request_dose.clear()

                    # treatment_ingoing = manager_hypo(db, severe_hypo, patient.id, display, flags)
                    # display.notify_value(anomaly, treatment_ingoing, cgm)

            # case 3: data are recent and into a normal range, no hurry to evaluate them
            elif anomaly == AnomalousSgv.NORMAL and recent:  # todo: add arrow down
                request_led.turn_off()
                flags.flag_dose_may_be_required.clear()
                request_timing = THRESHOLD.sec_fetch

                if request_timing > 60:
                    refresh = request_timing / 60
                    count = 1
                    while count <= refresh:
                        display.notify_value(anomaly, treatment_ingoing, cgm)
                        flags.flag_exit.wait(60)
                        count = count + 1

            # case others: display data and update them (no error was detected)
            else:

                request_led.turn_off()  # turn off the led for dose request
                flags.flag_dose_may_be_required.clear()

                display.notify_value(anomaly, treatment_ingoing, cgm)
                flags.flag_exit.wait(THRESHOLD.sec_investigation)

        finally:
            # close the connection with the db in this way the update from the bot may be performed
            db.close()
            # something went wrong
            if errors:
                counter_error = counter_error + 1

                if counter_error <= MAX_TRIES:
                    display.notify_error_connection("err: " + str(counter_error) + " on " + str(MAX_TRIES), False)
                    flags.flag_exit.wait(THRESHOLD.sec_error)
                else:
                    logging.warning('Too many error the machine will be turned off')
                    display.notify_error('Too many errors!\nMachine OFF')
                    flags.flag_exit.wait(10)  # give the user the possibility to see the message
                    flags.flag_exit.set()  # stop the main and kill the machine
                    break
            # todo add a reminder for glass and juice

    # out from the loop
    request_led.turn_off()
    flags.flag_dose_may_be_required.clear()
    display.turn_off()
    logging.info("the thread of the machine arrives at the end")


def manager_hypo(db, severe_hypo, patient_id, display, flags, peristaltic_pump):
    # retrieve the last juice
    juice = db.pull_last_juice(patient_id)

    liquid_unit = 100  # we are using milliliters

    # case 0: the machine is not able to find any juice (it's only at the beginning)
    if juice is None:
        logging.warning('No juice is inserted,the dose distribution is stopped')
        display.notify_error('Add a Juice\nvia Telegram Bot')
        flags.flag_exit.wait(THRESHOLD.sec_error)  # make user able to read the message
        return False

    # case 1: the machine cannot detect the juice using the IR sensors
    elif not flags.flag_juice.is_set():
        counter = 0
        while not flags.flag_juice.is_set() and not flags.flag_exit.is_set():
            if counter == MAX_TRIES:
                display.notify_error('Dose FAIL\nNO Juice Found')
                logging.warning('the distribution cannot continue\nNO Juice DETECTED')
                flags.flag_exit.wait(10)  # make possible see the message for the user
                logging.warning('the dose distribution is stopped')
                return False
            else:
                counter = counter + 1
                logging.warning('check for the juice try %s on %s', str(counter), str(MAX_TRIES))
                display.notify_error('Place a Juice\ntry:' + str(counter) + ' on ' + str(MAX_TRIES))
                flags.flag_exit.wait(10)  # before there was the juice
        # todo: test it
        # the juice was added in the middle so, let's try a new time the method
        if not flags.flag_exit.is_set():
            print('occhio al loop')
            manager_hypo(db, severe_hypo, patient_id, display, flags, peristaltic_pump)
        else:
            return False
        
    # case 2: a juice is stored in the machine and detected using the IR sensors
    else:
        dosing = Doser(distribution_button, peristaltic_pump, request_led, patient_id, juice)
        if flags.flag_bot_request_dose.is_set():
            # retrieve the last dose (insert by bot)
            dose_added = db.pull_bot_dose(patient_id)
            carbo_to_deliver = dose_added.amount_defined
            db.remove_dose(dose_added)
        elif severe_hypo:
            carbo_to_deliver = 20
        else:
            carbo_to_deliver = 15

        dosing.dose_calculation(carbo_to_deliver, liquid_unit)

        # case 2.1 a dose is evaluated as possible delivered
        if dosing.eval_dose():
            # dose distribution and calculated
            dose = dosing.distribution(flags, display)

            # once that the delivering is performed the juice can be update
            possible_warming = dosing.update_juice(dose.amount_defined)
            db.update_juice(dosing.juice)
            db.push_dose(dosing.dose)

            # display the insertion
            print('\nJUICE UPDATED:', db.pull_last_juice(patient_id))
            print('\nDOSE INSERTED', db.pull_last_dose(patient_id))

            # if the amount of juice is critic fot the next dose
            if possible_warming:
                logging.warning('THE NEXT DOSE MAY REQUIRE MORE JUICE THAN THE AVAILABLE')
                display.notify_error('Add Juice\n' + str(juice.amount) + ' ml left')
                flags.flag_low_juice.set()
                flags.flag_exit.wait(THRESHOLD.sec_error)  # make user able to read the message

            # case 2.1.1 the dose was not delivered
            if dose.amount_defined == 0:
                return False
            # case 2.1.2 the dose was deliver
            else:
                return True  # the dose was successfully delivered

        # case 2.2: with the juice available is not possible deliver the juice
        else:
            logging.warning('the machine is communicating to the user that there is no juice left for a new dose')
            flags.flag_no_juice_left.set()
            count = 0
            juice_left = juice.amount
            while count < MAX_TRIES:
                display.notify_error('Not enough juice!\n' + str(juice_left) + ' ml left!')
                flags.flag_exit.wait(SEC_ALT_MESS)
                display.notify_error('Dose Error!\nChange Juice!')
                flags.flag_exit.wait(SEC_ALT_MESS)
                count = count + 1
            logging.warning('the dose distribution fail due to the missing juice')
            return False  # the dose was not successfully delivered
