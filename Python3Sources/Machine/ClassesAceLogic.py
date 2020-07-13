"""
This file contains the classes that support the system ACE
"""
from enum import Enum


class Patient:
    """ This class represents the main user of the system (patient) """
    def __init__(self, id, name, diabetes_type, unit_bg, hypo_threshold, hyper_threshold, to_investigate_threshold, nightscout):
        """
        :param id: identifier
        :param name: Patient Name
        :param diabetes_type: TDM1 o TDM2
        :param unit_bg: mmlol or mg
        :param hypo_threshold: hypoglycemia threshold
        :param hyper_threshold: hypoglicemia threshold
        :param nightscout: web address of CGM data
        """
        self.id = id
        self.name = name
        self.diabetes_type = diabetes_type
        self.unit_bg = unit_bg
        self.hypo_threshold = hypo_threshold
        self.hyper_threshold = hyper_threshold
        self.to_investigate_threshold = to_investigate_threshold
        self.nightscout = nightscout

    def __repr__(self):
        return "Patient('{}', '{}', '{}', '{}','{}', '{}', '{}', '{}')".format(self.id, self.name, self.diabetes_type,
                                                                               self.unit_bg, self.hypo_threshold,
                                                                               self.hyper_threshold,
                                                                               self.to_investigate_threshold,
                                                                               self.nightscout)


class CGM:
    """ Nightscout Data class """
    def __init__(self, timestamp, datetime_sgv, sgv, unit_bg, trend, direction, bgdelta, iob, cob, patient_id):
        """
        :param timestamp: timestamp server
        :param datetime_sgv: timestamp glucose value
        :param sgv: glucose value
        :param unit_bg: unit of measure
        :param trend: it is used for the prediction
        :param direction: Displays the trend direction
        :param bgdelta: Calculates and displays the change between the last 2 BG values
        :param iob: Insulin on Ratio
        :param cob: Carbohydrates on Ration
        :param patient_id: patient ID reference
        """
        self.timestamp = timestamp
        self.datetime_sgv = datetime_sgv
        self.sgv = sgv
        self.unit_bg = unit_bg
        self.trend = trend
        self.direction = direction
        self.bgdelta = bgdelta
        self.iob = iob
        self.cob = cob
        self.patient_id = patient_id

    def __repr__(self):
        return "CGM('{}', '{}', '{}', '{}', '{}', '{}', '{}','{}','{}','{}')".format(self.timestamp, self.datetime_sgv,
                                                                                     self.sgv, self.unit_bg,
                                                                                     self.trend, self.direction,
                                                                                     self.bgdelta, self.iob, self.cob,
                                                                                     self.patient_id)


class JuiceData:
    """ Juice Data class """
    def __init__(self, id, timestamp, carbohydrates, amount, patient_id):
        """
        :param id: fruit juice ID
        :param timestamp: timestamp of last modification
        :param carbohydrates: carbohydrates contained in the juice (unit ml on grams)
        :param amount: quantity (unit = Milliliters mL)
        :param patient_id: patient ID reference
        """
        self.id = id
        self.timestamp = timestamp
        self.carbohydrates = carbohydrates
        self.amount = amount
        self.patient_id = patient_id

    def __repr__(self):
        return "JuiceData('{}', '{}', '{}', '{}', '{}')".format(self.id, self.timestamp, self.carbohydrates, self.amount, self.patient_id)

    def convert_carbo_unit(self, carbohydrates, carbo_unit):
        # TODO: function to finish
        """
        This function converts each unit used by the user into
        g on ml
        :param carbohydrates: amount of carbohydrates contained
        :param carbo_unit: unit measure selected by the system
        :return: update the carbohydrates inside the class
        """

        # TODO: some magic calculus based on the carbo unit
        # some calculation are necessary based on the unit
        self.carbohydrates = carbohydrates

    def convert_amount_unit(self, amount, amount_unit):
        # TODO: function to finish
        """
        This function converts each unit used by the user into
        ml
        :param amount: amount of carbohydrates contained
        :param amount_unit: unit measure selected by the system
        :return: update the carbohydrates inside the class
        """
        # TODO: some magic calculus based on the carbo unit
        # some calculation are necessary based on the unit
        self.amount = amount


class Dose:
    """ Dose class """
    def __init__(self, timestamp, amount_delivered, amount_defined, unit, patient_id, juice_id):
        """
        :param timestamp: timestamp dose creation
        :param amount_delivered: juice delivered
        :param amount_defined: teorical amount to deliver
        :param unit: unit of measure
        :param juice_id: juice ID reference
        :param patient_id: patient ID reference
        """
        self.timestamp = timestamp
        self.amount_delivered = amount_delivered
        self.amount_defined = amount_defined
        self.unit = unit
        self.juice_id = juice_id
        self.patient_id = patient_id

    def __repr__(self):
        return "Dose('{}', '{}', '{}', '{}', '{}', '{}')".format(
            self.timestamp, self.amount_delivered, self.amount_defined, self.unit, self.patient_id, self.juice_id)


class Threshold:
    """Threshold class"""
    def __init__(self, sec_recent, sec_dose, sec_fetch, sec_investigation, sec_error):
        """
        :param sec_recent: seconds to consider a data recent
        :param sec_fetch:  seconds to consider to request data from Nightscout
        :param sec_dose: seconds to consider a dose as valid
        :param sec_error: seconds to try the reconnection if problem is detected
        :param sec_investigation: seconds to check when more investigation should be performed
        """
        self.sec_recent = sec_recent
        self.sec_dose = sec_dose
        self.sec_fetch = sec_fetch
        self.sec_investigation = sec_investigation
        self.sec_error = sec_error

    def __repr__(self):
        return "Threshold('{}', '{}', '{}', '{}', '{}')".format(
            self.sec_recent, self.sec_dose, self.sec_fetch, self.sec_investigation, self.sec_error)


class AnomalousSgv(Enum):
    """ This class represent the anomalous situation based on glucose value"""
    NORMAL = 0
    HYPO = 1
    HYPER = 2
    TO_INVESTIGATE = 3


class UnitDiabetes(Enum):
    """
    This class represent the measurement unit for both
    """
    MMOL = 'mmol/l'
    MG = 'mg/dl'

    @staticmethod
    def convert_mmol_to_mg(mmol):
        """
        Formula to calculate mg/dl from mmol/l: mg/dl = 18 × mmol/l
        :param mmol: Millimoles per litre
        :return: mg Milligrams per 100 millilitres
        """
        return round(18 * mmol, 1)

    @staticmethod
    def convert_mg_to_mmol(mg):
        """
        Formula to calculate mmol/l from mg/dl: mmol/l = mg/dl / 18
        :param mg: Milligrams per 100 millilitres
        :return: mmol
        """
        return round(mg / 18, 1)

    @staticmethod
    def convert_str_enum(string):
        """
        This method converts the string into the matched enum
        :param string:
        :return:
        """
        if string == UnitDiabetes.MG.value:
            unit = UnitDiabetes.MG
        elif string == UnitDiabetes.MMOL.value:
            unit = UnitDiabetes.MMOL
        else:
            unit = None

        return unit








    
        
        







