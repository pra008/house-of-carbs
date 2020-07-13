import urllib.request
import urllib.error
import json
import math
from datetime import datetime
import ClassesAceLogic


class InvalidData(ValueError):
    """
    Class to define an invalid data
    """
    pass


class Nightscout:
    """ This class includes all the functionality necessary for fetch and eval data received from Nightscout
    - get_data -> get data from the web address
    - is_recent -> eval if the glucose data are recent respect the current server time
    - eval_sgv -> eval the glucose value and detect the anomalous situation """
    def __init__(self, patient):
        """
        :param patient: patient class
        """
        self.patient = patient

    @staticmethod
    def verify_address_error(address):
        """
        This function is used to check if the address receives data or not
        :param address:
        :return:
        """
        error = False
        try:
            with urllib.request.urlopen(address) as url:
                json.loads(url.read().decode())
        except urllib.error.HTTPError:
            error = True  # turn on the flag of errors
        except urllib.error.URLError:  # this error include content to short
            error = True
        except Exception:
            error = True

        return error

    def get_cgm(self):
        """
        This function return the cgm data extracted from the Nightscout platform
        The unit is not defined here
        :return: cgm Object or errors
        """
        with urllib.request.urlopen(self.patient.nightscout) as url:
                data = json.loads(url.read().decode())
                cgm = filtering_data(data)
                cgm.patient_id = self.patient.id
                cgm.unit_bg = self.patient.unit_bg
                return cgm

    @staticmethod
    def is_recent(cgm, limit):
        """
        is_recent evaluate if the timestamp of the CGM is inside the time limit
        :param cgm: Object CGM
        :param limit: int, seconds to consider a data recent
        :return: recent
        """

        time_server = datetime.fromtimestamp(cgm.timestamp, tz=None)
        time_data = datetime.fromtimestamp(cgm.datetime_sgv, tz=None)
        elapsed_time = time_server - time_data

        # evaluate the difference in seconds between them
        if elapsed_time.total_seconds() <= limit:
            # TODO additional evaluation about the server time
            return True
        else:
            return False

    @staticmethod
    def eval_sgv(cgm, hypo_value, hyper_value, to_investigate_value):
        """ This function evaluate the cmg.datetime_sgv
         there are 4 possible values:
         - HYPOGLYCEMIA
         - HYPERGLYCEMIA
         - NORMAL VALUE
         - TO INVESTIGATE
        :param cgm: Object cgm
        :param hypo_value: int, threshold for hypoglycemia
        :param hyper_value: int, threshold for hyperglycemia
        :param to_investigate_value: int, value that require an additional investigation
        :return: enum, ClassesAce.AnomalousSgv
        """

        if cgm.sgv >= hyper_value:
            return ClassesAceLogic.AnomalousSgv.HYPER
        elif cgm.sgv <= hypo_value:
            return ClassesAceLogic.AnomalousSgv.HYPO
        elif to_investigate_value is not None:
            # this value can be None
            if cgm.sgv <= to_investigate_value:
                return ClassesAceLogic.AnomalousSgv.TO_INVESTIGATE
            else:
                return ClassesAceLogic.AnomalousSgv.NORMAL
        else:
            return ClassesAceLogic.AnomalousSgv.NORMAL

    def eval_cgm(self, cgm):
        """
        This method evaluate the cgm data based on the patient threshold
        :param cgm: cgm to investigate
        :return:
        """
        if cgm.sgv >= self.patient.hyper_threshold:
            return ClassesAceLogic.AnomalousSgv.HYPER

        elif cgm.sgv <= self.patient.hypo_threshold:
            return ClassesAceLogic.AnomalousSgv.HYPO

        elif self.patient.to_investigate_threshold is not None:  # this value can be missed
            if cgm.sgv <= self.patient.to_investigate_threshold:
                return ClassesAceLogic.AnomalousSgv.TO_INVESTIGATE
            else:
                return ClassesAceLogic.AnomalousSgv.NORMAL
        else:
            return ClassesAceLogic.AnomalousSgv.NORMAL

    # TODO define an improvement
    @staticmethod
    def eval_severe_hypoglycemia(current_cgm, other_cgm):
        """
        This method evaluate the hypoglycemia.
        Based on that it delivers 15grams or 20 grams
        :param current_cgm:
        :param other_cgm:
        :return: True -> Severe Hypoglycemia, False -> Hypoglycemia
        """

        print(type(current_cgm), type(other_cgm))
        return True

    def under_treatment(self, dose, cgm, limit):
        """
        Evaluate if the patient is under treatment
        :param dose: last patient dose
        :param cgm: last cgm received
        :param limit: seconds to consider a dose recent
        :return: bool: true (patient is under treatment) false (patient is not under treatment)
        """
        if dose is None:
            # no dose
            return False

        if not dose.patient_id == self.patient.id:
            # the dose is not of the patient
            return False

        if dose.amount_defined == 0 or dose.amount_delivered == 0:
            return False
        else:
            time_data = datetime.fromtimestamp(cgm.datetime_sgv, tz=None)
            time_dose = datetime.fromtimestamp(dose.timestamp, tz=None)

            # difference between current sgv and dose inserted
            elapsed_time = time_data - time_dose

            if math.floor(elapsed_time.total_seconds()) <= limit:
                return True
            else:
                return False

    @staticmethod
    def rising_glucose(cgm):
        """
        This method eval the arrow from the glucose value
        TODO apply machine learning for a better detection of low level of blood glucose 
        :param cgm:
        :return: true - > the cgm is increased; false otherwise
        """
        arrow = cgm.direction
        if arrow == "SingleUp" or arrow == 'DoubleUp' or arrow == "FortyFiveUp":
            return True
        else:
            return False


def filtering_data(data):
    """
    This function receives the json from Nightscout and return all the necessary data for the current application
    :param data: JSON DATA received from Nightscout
    :return: CGM object according to the description (ONLY the parameters requested from this version)
    """
    # DATA: datetime_server -> Server Timestamp from Nightscout Data
    # milliseconds aren't considered (10 digit) but stored as a integer
    # any Exception at this point will be considered an empty data (None)
    try:
        datetime_server = data['status'][0]['now']
        # process
        datetime_server = str(datetime_server)[0: 10]
        datetime_server = int(datetime_server)
    except Exception:
        raise InvalidData

    # DATA: sgv -> blood glucose value in mmol/L  stored as a float
    # any Exception at this point will be considered an empty data (None)
    try:
        sgv = data['bgs'][0]['sgv']
        # casting string to float
        sgv = float(sgv)
        if sgv < 0:
            raise InvalidData
    except Exception:
        raise InvalidData

    # DATA: datetime_sgv -> Timestamp glucose value  from Nightscout Data
    # milliseconds aren't considered (10 digit) but stored as a integer
    # any Exception at this point will be considered an empty data (None)
    try:
        datetime_sgv = data['bgs'][0]['datetime']
        datetime_sgv = str(datetime_sgv)[0: 10]
        datetime_sgv = int(datetime_sgv)
    except Exception:  # every exception will lead to fail
        raise InvalidData
        
    try:
        trend = data['bgs'][0]['trend']
        trend = float(trend)
    except Exception:  # every exception will lead to None
        trend = None
        
    try:
        direction = data['bgs'][0]['direction']
        direction = str(direction)
    except Exception:  # every exception will lead to None
        direction = None

    try:
        bgdelta = data['bgs'][0]['bgdelta']
        bgdelta = float(bgdelta)
    except Exception:  # every exception will lead to None
        bgdelta = None

    try:
        iob = data['bgs'][0]['iob']
        iob = float(iob)
    except Exception:  # every exception will lead to None
        iob = None

    try:
        cob = data['bgs'][0]['cob']
        cob = float(cob)
    except Exception:  # every exception will lead to None
        cob = None

    return ClassesAceLogic.CGM(datetime_server, datetime_sgv, sgv, None,
                               trend, direction, bgdelta, iob, cob, None)




