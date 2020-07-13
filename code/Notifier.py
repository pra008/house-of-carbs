import threading
import math
from datetime import datetime

from ClassesAceLogic import AnomalousSgv
from SerialWrapper import SerialWrapper


# DISPLAY USED
# Adafruit-USB-Serial-RGB-Character-Backpack
# 16x2 LCD:
ROWS = 2
COLS = 16

# runtimeError may be raised if you use a locked object


class Notifier:
    def __init__(self, port):
        try:
            self.display = SerialWrapper(port, COLS, ROWS)
            self.display.cls()  # delete any previous text
            self.display.light_white()  # reset the light
            self.display.light_on()

        except Exception as e:
            print(e)
            self.display = None

    def notify_value(self, anomaly, under_treatment, cgm):
        # TODO ARROW, color variable
        """
        This is the main function to manage the notification of value
        the notification involves 3
        :param anomaly: the evaluation of sgv performed
        :param under_treatment: true if the patient in under treatment
        :param cgm: value to display
        :return: False only if data are incorrect, True otherwise
        """
        

        # part 1: define the color based on the anomaly
        if anomaly == AnomalousSgv.HYPER:
            self.display.light_purple()
            
        elif anomaly == AnomalousSgv.NORMAL or anomaly == AnomalousSgv.TO_INVESTIGATE:
            self.display.light_green()
            
        elif anomaly == AnomalousSgv.HYPO:
            self.display.light_red()

        # part 2: define the test to display #can be improved
        time_system = datetime.now(tz=None)  # get the current timestamp of the system
        time_cgm = datetime.fromtimestamp(cgm.datetime_sgv, tz=None)  # get the timestamp of the data

        elapsed_time = time_system - time_cgm  # calculate the difference in seconds
        minutes = math.floor(elapsed_time.total_seconds() / 60)  # converts the differences in minutes

        if minutes < 0:
            self.notify_error('Data incorrect')
            return False
        elif minutes == 0:
            min_text = "<1 min ago"
        elif minutes < 60:
            min_text = str(minutes) + " min ago"
        else:  # more than 60 minutes
            hours = int(round(minutes / 60))
            if hours > 1:
                min_text = str(hours) + " hs ago"
            else:
                min_text = str(hours) + " h ago"

        text_to_show = "BG=" + str(cgm.sgv) + " " + cgm.unit_bg + '\n' + min_text

        if under_treatment:
            text_to_show = text_to_show + " DOSE"

        self.send_text(text_to_show)

        # part 3 define the light intensity
        if minutes <= 15:
            self.display.set_light_intensity(255 - minutes * 2)
        elif minutes <= 30:
            self.display.set_light_intensity(127 - minutes * 2)
        elif minutes < 60:
            self.display.set_light_intensity(64 - minutes)
        else:
            self.display.set_light_intensity(2)

        return True

    def notify_dose(self, amount, amount_todo, begin):
        """
        This function print the dose distribution
        :param amount: ml current
        :param amount_todo: ml to deliver in total
        :param begin: if True prints the delivering at the beginning, otherwise it overwrites the second line
        :return:
        """
        if begin:
            self.display.light_white()
            text = "delivering"
            self.send_text(text)
        else:
            text = str(amount) + " on " + str(amount_todo) + " ml"
            self.display.new_line()  # position the cursor in the second row
            self.display.write_text(text)  # it uses this methods because it doesn't contain the cls

    def notify_error(self, text):
        """
        This function is used to notify an error
        :param text:
        :return:
        """
        self.display.light_white()
        self.send_text(text)

    def notify_error_connection(self, text, begin):
        """
        This function is called when an error is detected based on the connection
        the message is divided into parts:
        first line: motivation
        second line: display the number of tries
        :param text:
        :param begin:
        :return:
        """
        if begin:
            self.display.light_white()
            self.send_text(text)
        else:
            self.display.new_line()  # position the cursor in the second row
            self.display.write_text(text)  # it uses this methods because it doesn't contain the cls

    def turn_off(self):
        """
        This function is used when the display is turned off.
        It clear the screen, reset light and close the serial communication
        :return:
        """
        self.display.cls()
        self.display.light_white()  # reset the light to the default color
        self.display.light_off()
        self.display.close()
        
    def send_text(self, text):
        """
        This function overwrites the text and writes a new one
        :param text:
        :return:
        """
        self.display.cls()
        self.display.write_text(text)


