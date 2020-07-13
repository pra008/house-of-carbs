import sqlite3
import ClassesAceLogic
import pandas


# class python

# NOTES TYPOS PYTHON SQL

# NULL. The value is a NULL value.
# INTEGER. The value is a signed integer
# REAL. The value is a floating point value
# TEXT. The value is a text string
# BLOB. The value is a blob of data, stored exactly as it was input.

# TODO
# the function get_patient assume that there is only one patient


class Database(object):
    """
    Sqlite3 database class that holds prototypes record
    """
    DB_LOCATION = "/home/pi/System_ACE/Python3Sources/Machine/database.sqlite"

    # basic function
    def __init__(self):
        """
        Initialize db connection variable
        """
        self.connection = sqlite3.connect(Database.DB_LOCATION)

    def __enter__(self):
        return self

    def __exit__(self, ext_type, exc_value, traceback):
        """
        Close the connection and undo the operation in case of error
        """
        if isinstance(exc_value, Exception):
            self.connection.rollback()
        else:
            self.connection.commit()
        self.connection.close()

    def close(self):
        """
        Close sqlite3 connection
        """
        self.connection.close()

    def commit(self):
        """
        Commit changes to database
        """
        self.connection.commit()

    # TODO: MAKE THIS FUNCTION NOT AVAILABLE FOR OUTSIDE
    def create_table(self, create_table_sql):
        """
        Create a table from the create_table_sql statement
        :param create_table_sql: a CREATE TABLE statement
        :return:
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute(create_table_sql)
        except ValueError as e:
            print(e)
        finally:
            cursor.close()

    # TODO: THIS FUNCTION IS TO DELETE
    def alter_table(self):
        cursor = self.connection.cursor()
        operation_done = False
        try:

            # to avoid the SQL INJECTION
            cursor.execute("ALTER TABLE cgm_data ADD COLUMN iob real")
            self.commit()
            cursor.execute("ALTER TABLE cgm_data ADD COLUMN cob real")
            operation_done = True
        except ValueError as e:
            print(e)
        except Exception as e:
            print(e)

        finally:
            cursor.close()
            return operation_done

    def init_database_table(self):
        """Temporary method to create all the table"""
        sql_create_patient_table = """ CREATE TABLE IF NOT EXISTS patient (
                                            id integer PRIMARY KEY,
                                            name text,
                                            diabetes_type text,
                                            unit_bg text NOT NULL,
                                            hypo_threshold real NOT NULL,
                                            hyper_threshold real NOT NULL,
                                            to_investigate_threshold real,
                                            nightscout text NOT NULL
                                        ); """

        sql_create_cgm_data_table = """CREATE TABLE IF NOT EXISTS cgm_data (
                                        timestamp integer PRIMARY KEY,
                                        datetime_sgv integer NOT NULL,
                                        sgv real NOT NULL,
                                        unit_bg text NOT NULL,
                                        trend real,
                                        direction text,
                                        bgdelta real,
                                        iob real,
                                        cob real,
                                        patient_id integer NOT NULL,
                                        FOREIGN KEY (patient_id) REFERENCES patient (id)
                                    );"""

        sql_create_juice_data_table = """CREATE TABLE IF NOT EXISTS juice_data (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        timestamp integer NOT NULL,
                                        carbohydrates real NOT NULL,
                                        amount real NOT NULL,
                                        patient_id integer NOT NULL,
                                        FOREIGN KEY (patient_id) REFERENCES patient (id)
                                    );"""

        sql_create_dose_table = """CREATE TABLE IF NOT EXISTS dose (
                                        timestamp integer PRIMARY KEY,
                                        amount_delivered real NOT NULL,
                                        amount_defined real NOT NULL,
                                        unit text NOT NULL,
                                        patient_id integer NOT NULL,
                                        juice_id integer NOT NULL,
                                        FOREIGN KEY (patient_id) REFERENCES patient (id),
                                        FOREIGN KEY (juice_id) REFERENCES juice_data (id)
                                    );"""
        self.create_table(sql_create_patient_table)
        self.create_table(sql_create_cgm_data_table)
        self.create_table(sql_create_juice_data_table)
        self.create_table(sql_create_dose_table)

    # todo: remove INSERT OR REPLACE INTO in  cursor.execute
    def push_patient(self, patient):
        """
        insert a new patient in the database
        :param patient: patient from ClassesAce
        :return: bool (operation completed)
        """
        cursor = self.connection.cursor()
        operation_done = False
        try:

            # to avoid the SQL INJECTION
            cursor.execute("INSERT OR REPLACE INTO patient VALUES"
                           "(:id, :name, :diabetes_type, :unit_bg, :hypo_threshold, :hyper_threshold, "
                           ":to_investigate_threshold, :nightscout)",
                           {'id': patient.id, 'name': patient.name, 'diabetes_type': patient.diabetes_type,
                            'unit_bg': patient.unit_bg, 'hypo_threshold': patient.hypo_threshold,
                            'hyper_threshold': patient.hyper_threshold,
                            'to_investigate_threshold': patient.to_investigate_threshold,
                            'nightscout': patient.nightscout})
            self.commit()
            operation_done = True
        except ValueError as e:
            print(e)
        except Exception as e:
            print(e)

        finally:
            cursor.close()
            return operation_done

    def pull_patient_counter(self):
        """
        Return the number of patient (without counting the patient 0)
        :return:
        """
        cursor = self.connection.cursor()
        counter_patient = 0
        try:
            # check if there is data inside it
            cursor.execute("""SELECT count(*) FROM patient""")
            counter_patient = cursor.fetchone()
            counter_patient = int(counter_patient[0]) - 1
        except Exception:
            pass
        finally:
            cursor.close()
            return counter_patient


    def pull_all_patient(self):
        """
        Return all the patient stored inside the datastore
        :return: pandas dataframe
        """
        cursor = self.connection.cursor()
        pd = None
        try:
            cursor.execute("""SELECT * FROM patient""")
            names = [x[0] for x in cursor.description]
            rows = cursor.fetchall()
            pd = pandas.DataFrame(rows, columns=names)
        except Exception:
            pass
        finally:
            cursor.close()
            return pd

    def pull_patient(self, patient_id):
        """
        :return:
        """
        cursor = self.connection.cursor()
        result = None
        try:
            cursor.execute("""SELECT * FROM patient WHERE id = :patient_id""",
                           {'patient_id': patient_id})
            rows = cursor.fetchone()

            result = ClassesAceLogic.Patient(rows[0], rows[1], rows[2], rows[3], rows[4], rows[5], rows[6], rows[7])
        except Exception as e:
            print("query", e)
            pass
        finally:
            cursor.close()
            return result

    def pull_last_patient(self):
        """
        Retrieves the last patient based on the last patient data
        :return:
        """
        cursor = self.connection.cursor()
        result = None
        try:
            cursor.execute("""SELECT patient_id FROM cgm_data ORDER BY timestamp DESC""")
            result = cursor.fetchone()
            result = result[0]
        finally:
            cursor.close()
            return result

    def update_patient_hypo_threshold(self, new_value, patient_id):
        """
        This operation change the hypoglycemia using the patient id
        :param new_value: float or int to insert
        :param patient_id: patient id
        :return: bool -> operation complete or not
        """
        operation_done = False
        cursor = self.connection.cursor()
        try:
            # check if the new value is a numbers
            if type(new_value) is int:
                new_value = float(new_value)
            elif type(new_value) is not float:
                raise ValueError('NO NUMBER')
            # a number is insert
            cursor.execute("""UPDATE patient SET hypo_threshold = :new_value WHERE id = :id""",
                           {'new_value': new_value, 'id': patient_id})
            self.commit()
            operation_done = True
        except ValueError:
            pass  # the operation is not done
        except Exception as e:
            print(e)
            pass
        finally:
            cursor.close()
            return operation_done

    def update_patient_hyper_threshold(self, new_value, patient_id):
        """
        This operation change the hyperglycemia using the patient id
        :param new_value: float or int to insert
        :param patient_id: patient id
        :return: bool -> operation complete or not
        """
        operation_done = False
        cursor = self.connection.cursor()
        try:
            # check if the new value is a numbers
            if type(new_value) is int:
                new_value = float(new_value)
            elif type(new_value) is not float:
                raise ValueError('NO NUMBER')
            # a number is insert
            cursor.execute("""UPDATE patient SET hyper_threshold = :new_value WHERE id = :id""",
                           {'new_value': new_value, 'id': patient_id})
            self.commit()
            operation_done = True
        except ValueError:
            pass  # the operation is not done
        finally:
            cursor.close()
            return operation_done

    def update_patient_to_investigate_threshold(self, new_value, patient_id):
        """
        This operation change the hyperglycemia using the patient id
        :param new_value: float or int to insert
        :param patient_id: patient id
        :return: bool -> operation complete or not
        """
        operation_done = False
        cursor = self.connection.cursor()
        try:
            # check if the new value is a numbers
            if new_value is None:
                new_value = None
            elif type(new_value) is int:
                new_value = float(new_value)
            elif type(new_value) is float:
                pass
            else:
                raise ValueError('NO NUMBER')
            # a number is insert
            cursor.execute("""UPDATE patient SET to_investigate_threshold = :new_value WHERE id = :id""",
                           {'new_value': new_value, 'id': patient_id})
            self.commit()
            operation_done = True
        except ValueError:
            pass  # the operation is not done
        finally:
            cursor.close()
            return operation_done

    def update_patient_nightscout(self, new_address, patient_id):
        """
        This function change the nighscout address
        NOT INPUT VERIFICATION IS DONE!
        :param new_address: float or int to insert
        :param patient_id: patient id
        :return: bool -> operation complete or not
        """
        operation_done = False
        cursor = self.connection.cursor()
        try:
            # check if the new value is a numbers
            # a number is insert
            cursor.execute("""UPDATE patient SET nightscout = :new_address WHERE id = :id""",
                           {'new_address': new_address, 'id': patient_id})
            self.commit()
            operation_done = True
        except Exception:
            pass  # the operation is not done
        finally:
            cursor.close()
            return operation_done

    def update_patient_unit(self, new_unit, patient_id):
        """
        This function return the unit
        :param new_unit: ClassesAceLogic.UnitDiabetes
        :param patient_id: patient identifier
        :return:
        """
        operation_done = False
        cursor = self.connection.cursor()
        try:
            patient = self.pull_patient(patient_id)
            to_investigate = None
            if new_unit == ClassesAceLogic.UnitDiabetes.MG or new_unit == ClassesAceLogic.UnitDiabetes.MG.value:
                unit = ClassesAceLogic.UnitDiabetes.MG.value
                hypo = ClassesAceLogic.UnitDiabetes.convert_mmol_to_mg(patient.hypo_threshold)
                hyper = ClassesAceLogic.UnitDiabetes.convert_mmol_to_mg(patient.hyper_threshold)

                if patient.to_investigate_threshold is not None:
                    to_investigate = ClassesAceLogic.UnitDiabetes.convert_mmol_to_mg(patient.to_investigate_threshold)

            elif new_unit == ClassesAceLogic.UnitDiabetes.MMOL or new_unit == ClassesAceLogic.UnitDiabetes.MMOL.value:
                unit = ClassesAceLogic.UnitDiabetes.MMOL.value
                hypo = ClassesAceLogic.UnitDiabetes.convert_mg_to_mmol(patient.hypo_threshold)
                hyper = ClassesAceLogic.UnitDiabetes.convert_mg_to_mmol(patient.hyper_threshold)

                if patient.to_investigate_threshold is not None:
                    to_investigate = ClassesAceLogic.UnitDiabetes.convert_mg_to_mmol(patient.to_investigate_threshold)
            else:
                raise ValueError('NO UNIT')

            cursor.execute("""UPDATE patient SET 
            unit_bg = :new_unit_bg,
            hypo_threshold = :new_hypo,
            hyper_threshold = :new_hyper,
            to_investigate_threshold = :new_to_investigate WHERE id = :id""",
                           {'new_unit_bg': unit,
                            'new_hypo': hypo,
                            'new_hyper': hyper,
                            'new_to_investigate': to_investigate,
                            'id': patient_id})
            self.commit()
            operation_done = True
        except ValueError:
            pass  # the operation is not done
        finally:
            cursor.close()
            return operation_done

    # GROUP OF FUNCTION FRO CGM DATA
    def push_cgm(self, cgm):
        """
        insert a new patient in the database
        :param cgm: Object cgm
        :return: error if detected
        """
        cursor = self.connection.cursor()
        try:
            # to avoid the SQL INJECTION
            cursor.execute(
                "INSERT INTO cgm_data VALUES "
                "(:timestamp, :datetime_sgv, :sgv, :unit_bg, :trend, :direction, :bgdelta, :iob, :cob, :patient_id)",
                {'timestamp': cgm.timestamp, 'datetime_sgv': cgm.datetime_sgv, 'sgv': cgm.sgv,
                 'unit_bg': cgm.unit_bg, 'trend': cgm.trend, 'direction': cgm.direction,
                 'bgdelta': cgm.bgdelta, 'iob': cgm.iob, 'cob':cgm.cob, 'patient_id': cgm.patient_id})
            self.commit()
        except ValueError as e:
            print(e)
        finally:
            cursor.close()

    def push_unique_cgm(self, cgm):
        """
        Insert a cgm data with a unique sgv.timestamp
        :param cgm: cgm Object to insert
        :return: bool if coperation is complete
        """
        cursor = self.connection.cursor()
        operation_done = False
        try:
            # check if there is data inside it
            cursor.execute("""SELECT count(*) FROM cgm_data WHERE datetime_sgv = :time""", {'time': cgm.datetime_sgv})
            counter = cursor.fetchone()
            if int(counter[0]) == 0:
                self.push_cgm(cgm)
                operation_done = True
        except ValueError as e:
            print(e)
        finally:
            cursor.close()
            return operation_done

    def pull_last_cgm(self, patient_id):
        """
        This function return the last cgm data retrieved from the patient
        :param patient_id:
        :return:
        """
        cursor = self.connection.cursor()
        try:
            # check if there is data inside it
            cursor.execute("""SELECT count(*) FROM cgm_data WHERE patient_id = :patient_id""", {'patient_id': patient_id})
            counter_doses = cursor.fetchone()
            if int(counter_doses[0]) == 0:
                return None
            else:
                cursor.execute("""SELECT * FROM cgm_data WHERE patient_id = :patient_id ORDER BY timestamp DESC""",
                               {'patient_id': patient_id})
                result = cursor.fetchone()
                return ClassesAceLogic.CGM(result[0], result[1], result[2], result[3], result[4], result[5],
                                           result[6], result[7], result[8], result[9])
        finally:
            cursor.close()

    def pull_all_cgm(self, patient_id):
        """
        This function return all the cgm data of a patient into a pandas dataframe
        :param patient_id:
        :return:
        """
        cursor = self.connection.cursor()
        pd = None
        try:
            cursor.execute("""SELECT * FROM cgm_data WHERE patient_id = :patient_id""",
                           {'patient_id': patient_id})
            names = [x[0] for x in cursor.description]
            rows = cursor.fetchall()
            pd = pandas.DataFrame(rows, columns=names)
        except Exception:
            pass
        finally:
            cursor.close()
            return pd

    def pull_cgm_from(self, timestamp_sgv, patient_id):
        """
        Based on patient and timestamp, it selects the cgm data using their sgv timestamp
        :param timestamp_sgv:
        :param patient_id:
        :return:
        """
        cursor = self.connection.cursor()
        pd = None
        try:
            cursor.execute("""SELECT * FROM cgm_data WHERE :timestamp <= datetime_sgv AND patient_id = :patient_id""",
                           {'patient_id': patient_id, 'timestamp': timestamp_sgv})

            names = [x[0] for x in cursor.description]
            rows = cursor.fetchall()
            pd = pandas.DataFrame(rows, columns=names)
        except Exception:
            pass
        finally:
            cursor.close()
            return pd

    def pull_cgm_from_to(self, from_timestamp_sgv, to_timestamp_sgv, patient_id):
        """
        retunn the cgm data from a patient where the timestamp_sgv is between the timestamps defined
        :param from_timestamp_sgv: initial timestamp define
        :param to_timestamp_sgv: final timestamp defined
        :param patient_id: patient identifier
        :return: pandas dataframe
        """
        cursor = self.connection.cursor()
        pd = None
        try:
            cursor.execute("""SELECT * FROM cgm_data 
            WHERE patient_id = :patient_id AND
            datetime_sgv BETWEEN :timestamp_low AND :timestamp_high""",
                           {'patient_id': patient_id,
                            'timestamp_low': from_timestamp_sgv,
                            'timestamp_high': to_timestamp_sgv})

            names = [x[0] for x in cursor.description]
            rows = cursor.fetchall()
            pd = pandas.DataFrame(rows, columns=names)
        except Exception:
            pass
        finally:
            cursor.close()
            return pd

    # FUNCTION FOR DOSE
    def push_dose(self, dose):
        """
        Insert a new dose in the database
        :param dose: dose Object
        :return: error if detected
        """
        cursor = self.connection.cursor()
        try:
            # to avoid the SQL INJECTION
            cursor.execute("INSERT INTO dose VALUES (:timestamp, :amount, :amount_b, :unit, :patient_id, :juice_id)",
                           {'timestamp': dose.timestamp,
                            'amount': dose.amount_delivered, 'amount_b': dose.amount_defined,
                            'unit': dose.unit,
                            'patient_id': dose.patient_id, 'juice_id': dose.juice_id})
            self.commit()
        except ValueError as e:
            print(e)
        finally:
            cursor.close()
            
    def remove_dose(self, dose):
        cursor = self.connection.cursor()
        try:
            if dose is not None:
                # to avoid the SQL INJECTION
                cursor.execute("DELETE FROM dose WHERE timestamp = :timestamp",
                           {'timestamp': dose.timestamp})
                self.commit()
        except ValueError as e:
            print(e)
        finally:
            cursor.close()

    def pull_last_dose(self, patient_id):
        """
        This function retrieves the last dose based on the timestamp
        :return: None or ClassesAce.Dose
        """
        cursor = self.connection.cursor()
        try:
            # check if there is data inside it
            cursor.execute("""SELECT count(*) FROM dose WHERE patient_id = :patient_id""", {'patient_id': patient_id})
            counter_doses = cursor.fetchone()
            if int(counter_doses[0]) == 0:
                return None
            else:
                cursor.execute("""SELECT * FROM dose WHERE patient_id = :patient_id ORDER BY timestamp DESC""",
                               {'patient_id': patient_id})
                result = cursor.fetchone()
                return ClassesAceLogic.Dose(result[0], result[1], result[2], result[3], result[4], result[5])
        finally:
            cursor.close()

    def pull_bot_dose(self, patient_id):
        """
        :param patient_id:
        :return:
        """
        cursor = self.connection.cursor()
        try:
            # check if there is data inside it
            cursor.execute("""SELECT count(*) FROM dose WHERE patient_id = :patient_id""", {'patient_id': patient_id})
            counter_doses = cursor.fetchone()
            if int(counter_doses[0]) == 0:
                return None
            else:
                cursor.execute("""SELECT * FROM dose WHERE patient_id = :patient_id and timestamp = 0""",
                               {'patient_id': patient_id})
                result = cursor.fetchone()
                return ClassesAceLogic.Dose(result[0], result[1], result[2], result[3], result[4], result[5])
        finally:
            cursor.close()

    def pull_all_dose(self, patient_id):
        """
        This function return all the doses
        :param patient_id:
        :return: pandas dataframe
        """
        cursor = self.connection.cursor()
        pd = None
        try:
            cursor.execute("""SELECT * FROM dose WHERE patient_id = :patient_id""", {'patient_id': patient_id})
            names = [x[0] for x in cursor.description]
            rows = cursor.fetchall()
            pd = pandas.DataFrame(rows, columns=names)
        except Exception:
            pass
        finally:
            cursor.close()
            return pd

    def pull_dose_from(self, timestamp, patient_id):
        """
        return all the doses from selected timestamp
        :param timestamp: timestamp from which select the data
        :param patient_id: patient identifier
        :return: pandas.DataFrame with results
        """
        cursor = self.connection.cursor()
        pd = None
        try:
            cursor.execute("""SELECT * FROM dose WHERE :time <= timestamp AND patient_id = :patient_id""",
                           {'patient_id': patient_id, 'time': timestamp})
            names = [x[0] for x in cursor.description]
            rows = cursor.fetchall()
            pd = pandas.DataFrame(rows, columns=names)
        except Exception:
            pass
        finally:
            cursor.close()
            return pd

    def pull_dose_from_to(self, from_timestamp, to_timestamp, patient_id):
        """
        :param from_timestamp: timestamp of beggining
        :param to_timestamp: timestamp at the end
        :param patient_id: patient identifier
        :return: pandas.DataFrame with results
        """
        cursor = self.connection.cursor()
        pd = None
        try:
            cursor.execute("""SELECT * FROM dose 
            WHERE patient_id = :patient_id AND
            timestamp BETWEEN :timestamp_low AND :timestamp_high""",
                           {'patient_id': patient_id,
                            'timestamp_low': from_timestamp,
                            'timestamp_high': to_timestamp})

            names = [x[0] for x in cursor.description]
            rows = cursor.fetchall()
            pd = pandas.DataFrame(rows, columns=names)
        except Exception:
            pass
        finally:
            cursor.close()
            return pd

    # FUNCTION FOR JUICE

    def push_juice(self, juice_data):
        """
        Insert a new juice_data in the database
        :param juice_data: juice_data Object to insert
        :return: error if detected
        """
        cursor = self.connection.cursor()
        try:
            if juice_data.id is None: # use the autoincrement
                # to avoid the SQL INJECTION
                cursor.execute("""INSERT INTO juice_data(timestamp, carbohydrates, amount, patient_id)
                   VALUES (:timestamp, :carbohydrates, :amount, :patient_id)""",
                               {'timestamp': juice_data.timestamp,
                                'carbohydrates': juice_data.carbohydrates, 'amount': juice_data.amount,
                                'patient_id': juice_data.patient_id})
            else:
                cursor.execute("INSERT INTO juice_data VALUES (:id, :timestamp, :carbohydrates, :amount, :patient_id)",
                               {'id': juice_data.id, 'timestamp': juice_data.timestamp,
                                'carbohydrates': juice_data.carbohydrates, 'amount': juice_data.amount,
                                'patient_id': juice_data.patient_id})

            self.commit()
        except ValueError as e:
            print(e)
        finally:
            cursor.close()

    def pull_all_juice(self, patient_id):
        cursor = self.connection.cursor()
        pd = None
        try:
            cursor.execute("""SELECT * FROM juice_data 
                WHERE patient_id = :patient_id""",
                           {'patient_id': patient_id})

            names = [x[0] for x in cursor.description]
            rows = cursor.fetchall()
            pd = pandas.DataFrame(rows, columns=names)
        except Exception:
            pass
        finally:
            cursor.close()
            return pd

    def pull_juice(self, juice_id):
        """
        Return the juice based on the juice ID
        :param juice_id:
        :return:
        """
        cursor = self.connection.cursor()
        try:
            # check if there is data inside it
            cursor.execute("""SELECT count(*) FROM juice_data WHERE id = :juice_id""",
                           {'juice_id': juice_id})
            counter_juices = cursor.fetchone()
            if int(counter_juices[0]) == 0:
                return None
            else:
                cursor.execute("SELECT * FROM juice_data WHERE id = :juice_id",
                               {'juice_id': juice_id})
                result = cursor.fetchone()
                return ClassesAceLogic.JuiceData(result[0], result[1], result[2], result[3], result[4])
        finally:
            cursor.close()


    def pull_last_juice(self, patient_id):
        """
        This function retrieves the last juice based on the timestamp
        :return: None or ClassesAce.juice
        """
        cursor = self.connection.cursor()
        try:
            # check if there is data inside it
            cursor.execute("""SELECT count(*) FROM juice_data WHERE patient_id = :patient_id""", {'patient_id': patient_id})
            counter_juices = cursor.fetchone()
            if int(counter_juices[0]) == 0:
                return None
            else:
                cursor.execute("SELECT * FROM juice_data WHERE patient_id = :patient_id ORDER BY timestamp DESC", {'patient_id': patient_id})
                result = cursor.fetchone()
                return ClassesAceLogic.JuiceData(result[0], result[1], result[2], result[3], result[4])
        finally:
            cursor.close()

    def pull_last_juice_machine(self):
        """
        This function retrieves the last juice based on the timestamp
        :return: None or ClassesAce.juice
        """
        cursor = self.connection.cursor()
        try:
            # check if there is data inside it
            cursor.execute("""SELECT count(*) FROM juice_data""")
            counter_juices = cursor.fetchone()
            if int(counter_juices[0]) == 0:
                return None
            else:
                cursor.execute("""SELECT * FROM juice_data ORDER BY timestamp DESC""")
                result = cursor.fetchone()
                return ClassesAceLogic.JuiceData(result[0], result[1], result[2], result[3], result[4])
        finally:
            cursor.close()

    def update_juice(self, juice):
        cursor = self.connection.cursor()
        try:
            cursor.execute("""UPDATE juice_data SET amount = :amount, timestamp = :timestamp, carbohydrates= :carb
            WHERE id = :id AND patient_id = :patient_id""",
                           {'amount': juice.amount, 'timestamp': juice.timestamp, 'carb': juice.carbohydrates,
                            'id': juice.id, 'patient_id': juice.patient_id})
            self.commit()
        finally:
            cursor.close()

    def select_all_juice(self):
        """
        Debug only, it returns all the juices
        """
        cursor = self.connection.cursor()
        try:
            cursor.execute("SELECT * FROM juice_data")
            return cursor.fetchall()
        finally:
            cursor.close()
