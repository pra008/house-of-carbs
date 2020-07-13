from telegram.ext import Updater
from telegram.ext import CommandHandler  # this manage the /commands
from telegram.ext import MessageHandler, Filters  # this for regular message
from telegram.error import (TelegramError, Unauthorized, BadRequest, TimedOut, ChatMigrated, NetworkError)  # errors
from telegram.ext import (RegexHandler, ConversationHandler)
from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove)  # used for question
from Database import Database
from Nightscout import Nightscout
from ClassesAceLogic import UnitDiabetes
import logging
from datetime import datetime
from ClassesAceLogic import Dose
from ClassesAceLogic import JuiceData
from ClassesAceLogic import Patient
import math
from sqlite3 import IntegrityError

# Enable logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                    level=logging.INFO
                    )
logging.disable(logging.DEBUG)


# block conversation handler for hypoglycemia and hyperglycemia
ask_for_a_new_value = "please insert a new value\n/cancel to abort the operation"
ask_value_not_correct = "value not correct\ninsert a new one or /cancel to undo the operation"
notify_mistake = "Not possible!\nmodification undone"

# todo: modify the current juice
# block for conversation handler to modify the juice
ask_current_juice = "(current juice)\n"
ask_other_juice = "other juices"
par_carbo = "carbohydrates = "
par_amount = "amount = "

COMMANDS = [["/start", "Start the bot"],
            ["/help", "List commands"],
            # ["/changeb_patient", "Change the user of the machine"],
            ["/bg_thresholds", "Show blood glucose thresholds used"],
            ["/check_glucose", "Get the last glucose value"],
            ["/check_dose", "Get information about last dose received"],
            ["/change_info", "Change personal information of the current user"],
            ["/change_bg_unit", "Change unit to measure the blood glucose"],
            ["/change_nightscout", "Change the source of glucose data"],
            ["/change_juice_amount", "Change juice information: amount left"],
            ["/change_bg_thresholds", "Change the value to detect hypoglycemia or hyperglycemia"],
            ["/change_request_button", "Change the value used to enable the machine's distribution button"],
            ["/ask_dose", "Ask a Dose if it is possible"],
            ["/add_juice", "Add a new Juice inside the system"],
            ["/clear_pump", "Clear the pump"],
            ["/off", "Turn Off the System"]
            ]


def broadcast_message(bot, message):
    try:
        # phase 1 verify if the user is inside the file
        with open("bot_users.txt", "r") as file:
            lines = list(file)
            for line in lines:
                bot.send_message(chat_id=line, text=message)
    except FileNotFoundError:
        pass



def request_patient(patient_id):
    """
    this request the patient based on the id
    :param patient_id:
    :return:
    """
    db = Database()
    patient = db.pull_patient(patient_id)
    db.close()
    return patient


def request_juice(patient_id):
    """
    this request the patient based on the id
    :param patient_id:
    :return:
    """
    db = Database()
    juice = db.pull_last_juice(patient_id)
    db.close()
    return juice


def update_juice(new_juice):
    """
    This function update the juice
    :param new_juice: ClassesLogicAce Juice
    :return:
    """
    db = Database()
    db.update_juice(new_juice)
    db.close()


def update_patient_unit(new_unit, patient_id):
    """
    This function is a call to the database to update the system unit
    :param new_unit:
    :param patient_id:
    :return:
    """
    db = Database()
    db.update_patient_unit(new_unit, patient_id)
    db.close()


def number_or_not(text):
    """
    Given in input a string with comma or dot, it return the float value
    :param text:
    :return:
    """
    if '.' in text:
        pass
    elif ',' in text:
        if str.isdigit(text.replace(',', '', 1)):
            text = text.replace(',', '.', 1)

    new_value = None
    try:
        new_value = float(text)
        if new_value < 0:   # remove the negative number from further analysis
            raise ValueError

    except ValueError:
        new_value = None
    except Exception:  # any it's for security
        new_value = None
    finally:
        return new_value


def eval_value_hypo(bot, update, number, upper_limit, unit):
    if number >= upper_limit:
        text = "value " + str(number) + " " + unit + " too high\nmaximum value possible <" + str(upper_limit) + " " + unit
        bot.send_message(chat_id=update.message.chat_id, text=text)
        return False
    else:
        return True


def eval_value_hyper(bot, update, number, low_limit, unit):
    if number <= low_limit:
        text = "value:" + str(number) + " " + unit + " too low\nminimum value possible >" + str(low_limit) + " " + unit
        bot.send_message(chat_id=update.message.chat_id, text=text)
        return False
    else:
        return True


def eval_to_investigate_value(bot, update, number, low_limit, upper_limit):
    if number <= low_limit:
        text = "value too low: " + str(number)
        bot.send_message(chat_id=update.message.chat_id, text=text)
        return False
    elif number >= upper_limit:
        text = "value too high: " + str(number)
        bot.send_message(chat_id=update.message.chat_id, text=text)
        return False
    else:
        return True


def insert_bot_dose(bot, update, grams, patient_id, flags):
    db = Database()
    try:
        last_juice = db.pull_last_juice(patient_id)
        if last_juice is None:
            bot.send_message(chat_id=update.message.chat_id, text="no juice inside the system")
        else:
            dose = Dose(0, 0, grams, "g", patient_id, last_juice.id)
            db.push_dose(dose)
            flags.flag_bot_request_dose.set()

    except IntegrityError:
        bot.send_message(chat_id=update.message.chat_id,
                         text="insertion fail!\nThe dose previously requested is not yet delivered")
    else:
        bot.send_message(chat_id=update.message.chat_id,
                         text="dose insert inside the system\nmay require 1 minute")
    finally:
        db.close()


def translate_timestamp_to_str(timestamp_to_display):
    time_system = datetime.now(tz=None)  # get the current timestamp of the system
    time_cgm = datetime.fromtimestamp(timestamp_to_display, tz=None)  # get the timestamp of the data

    elapsed_time = time_system - time_cgm  # calculate the difference in seconds
    minutes = math.floor(elapsed_time.total_seconds() / 60)  # converts the differences in minutes

    if minutes == 0:
        min_text = "<1 minute ago"
    elif minutes < 60:
        min_text = str(minutes) + " minute ago"
    else:  # more than 60 minutes
        hours = int(round(minutes / 60))
        if hours > 1:
            min_text = str(hours) + " hours ago"
        else:
            min_text = str(hours) + " hour ago"

    return min_text


def translate_juice_to_str(juice):
    """
    This function is used to display the juice information
    :param juice:
    :return:
    """
    text = str(juice.carbohydrates) + "g on 100 ml\n"
    text = text + str(juice.amount) + " ml left\n"
    text = text + "last modified: " + str(datetime.fromtimestamp(juice.timestamp, tz=None))
    return text


def glucose_value_to_str(glucose_value, unit):
    return str(glucose_value) + " " + unit


class Bot:
    def __init__(self, token, patient_id, pump, flags):
        
        self.patient_id = patient_id
        self.pump = pump
        self.flags = flags
        self.updater = Updater(token=token)
        self.dispatcher = self.updater.dispatcher

        # handler errors
        self.dispatcher.add_error_handler(self.error_callback)

        # handler turn off the machine

        off_handler = CommandHandler('off', self.off)
        self.dispatcher.add_handler(off_handler)

        # handler command start
        self.START_INIT, self.START_NAME, self.START_DIABETES = range(3)
        start_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start_init, pass_chat_data=True)],
            states={
                self.START_INIT: [MessageHandler(Filters.text, self.start_init, pass_chat_data=True)],
                self.START_NAME: [MessageHandler(Filters.text, self.start_init_name, pass_chat_data=True)],
                self.START_DIABETES: [MessageHandler(Filters.text, self.start_init_diabetes, pass_chat_data=True)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.dispatcher.add_handler(start_handler)

        # # handler change patient
        # self.CHANGE_PATIENT_INIT, self.CHANGE_PATIENT_DONE = range(2)
        # change_patient_handler = ConversationHandler(
        #     entry_points=[CommandHandler('change_patient',
        #                                  partial(self.change_patient_init, patient_id=self.patient_id),
        #                                  pass_chat_data=True)],
        #     states={
        #         self.CHANGE_PATIENT_INIT: [MessageHandler(Filters.text, self.change_patient_init, pass_chat_data=True)],
        #         self.CHANGE_PATIENT_DONE: [MessageHandler(Filters.text, self.change_patient_done, pass_chat_data=True)]
        #     },
        #     fallbacks=[CommandHandler('cancel', self.cancel)]
        # )
        # self.dispatcher.add_handler(change_patient_handler)

        # handler change personal information
        self.CHANGE_INFO_INIT, self.CHANGE_INFO_TYPE, self.CHANGE_INFO_DONE = range(3)
        change_info_handler = ConversationHandler(
            entry_points=[CommandHandler('change_info', self.change_info_init, pass_chat_data=True)],
            states={
                self.CHANGE_INFO_INIT: [MessageHandler(Filters.text, self.change_info_init, pass_chat_data=True)],
                self.CHANGE_INFO_TYPE: [MessageHandler(Filters.text, self.change_info_type, pass_chat_data=True)],
                self.CHANGE_INFO_DONE: [MessageHandler(Filters.text, self.change_info_done, pass_chat_data=True)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.dispatcher.add_handler(change_info_handler)

        # handler command help
        help_handler = CommandHandler('help', self.helper)
        self.dispatcher.add_handler(help_handler)

        # handler command clear pump
        clear_handler = CommandHandler('clear_pump', self.clear_pump)
        self.dispatcher.add_handler(clear_handler)

        # handler command get_last_data
        get_last_cgm_data_handler = CommandHandler('check_glucose', self.get_last_cgm_data)
        self.dispatcher.add_handler(get_last_cgm_data_handler)

        # handler command get_last_dose
        get_last_dose_data_handler = CommandHandler('check_dose', self.check_dose)
        self.dispatcher.add_handler(get_last_dose_data_handler)

        # handler display hypoglycemia and hyperglycemia threshold
        show_thresholds_handler = CommandHandler('bg_thresholds', self.show_thresholds, pass_chat_data=True)
        self.dispatcher.add_handler(show_thresholds_handler)

        # Add conversation handler for modification of hypo/hyper threshold
        self.THRESHOLD_TYPE, self.THRESHOLD_WHICH, self.THRESHOLD_MOD_HYPO, self.THRESHOLD_MOD_HYPER = range(4)
        conversation_handler_hypo_hyper = ConversationHandler(
            entry_points=[CommandHandler('change_bg_thresholds', self.change_thresholds_init, pass_chat_data=True)],
            states={
                self.THRESHOLD_TYPE: [
                    RegexHandler('^(hypoglycemia|hyperglycemia)$', self.change_thresholds_init, pass_chat_data=True)],
                self.THRESHOLD_WHICH: [MessageHandler(Filters.text, self.which_threshold, pass_chat_data=True)],
                self.THRESHOLD_MOD_HYPO: [MessageHandler(Filters.text, self.mod_hypo_threshold, pass_chat_data=True)],
                self.THRESHOLD_MOD_HYPER: [MessageHandler(Filters.text, self.mod_hyper_threshold, pass_chat_data=True)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.dispatcher.add_handler(conversation_handler_hypo_hyper)

        # Add conversation handler for modification of dose request button behaviour
        self.MOD_TO_INVESTIGATE, self.MOD_TO_INVESTIGATE_WHICH, self.MOD_TO_INVESTIGATE_DONE = range(3)
        conversation_handler_modify_to_investigate = ConversationHandler(
            entry_points=[CommandHandler('change_request_button', self.change_to_investigate_init, pass_chat_data=True)],
            states={
                self.MOD_TO_INVESTIGATE: [MessageHandler(Filters.text, self.change_to_investigate_init, pass_chat_data=True)],
                self.MOD_TO_INVESTIGATE_WHICH: [
                    MessageHandler(Filters.text, self.change_to_investigate_which, pass_chat_data=True)],
                self.MOD_TO_INVESTIGATE_DONE: [MessageHandler(Filters.text, self.change_to_investigate_done, pass_chat_data=True)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.dispatcher.add_handler(conversation_handler_modify_to_investigate)

        # Add conversation handler for modification of unit
        self.MOD_BG, self.MOD_BG_DONE = range(2)
        conversation_handler_modify_unit = ConversationHandler(
            entry_points=[CommandHandler('change_bg_unit', self.change_unit_init, pass_chat_data=True)],
            states={
                self.MOD_BG: [MessageHandler(Filters.text, self.change_unit_init, pass_chat_data=True)],
                self.MOD_BG_DONE: [MessageHandler(Filters.text, self.change_unit_done, pass_chat_data=True)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.dispatcher.add_handler(conversation_handler_modify_unit)

        # Add conversation handler for modification of nightscout address
        self.HANDLER_ADDRESS_INIT, self.HANDLER_ADDRESS_DONE = range(2)
        
        conversation_handler_nightscout = ConversationHandler(
            entry_points=[CommandHandler('change_nightscout', self.change_data_source_init, pass_chat_data=True)],
            states={
                self.HANDLER_ADDRESS_INIT: [MessageHandler(Filters.text, self.change_data_source_init, pass_chat_data=True)],
                self.HANDLER_ADDRESS_DONE: [MessageHandler(Filters.text, self.change_data_source_done, pass_chat_data=True)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.dispatcher.add_handler(conversation_handler_nightscout)

        # Add conversation handler for juice modification
        self.INSERT_JUICE_INIT, self.INSERT_JUICE_GRAMS, self.INSERT_JUICE_AMOUNT, self.INSERT_JUICE_DONE = range(4)
        conversation_handler_add_juice = ConversationHandler(
            entry_points=[CommandHandler('add_juice', self.insert_juice_init, pass_chat_data=True)],
            states={
                self.INSERT_JUICE_INIT: [MessageHandler(Filters.text, self.insert_juice_init, pass_chat_data=True)],
                self.INSERT_JUICE_GRAMS: [MessageHandler(Filters.text, self.insert_juice_grams, pass_chat_data=True)],
                self.INSERT_JUICE_AMOUNT: [MessageHandler(Filters.text, self.insert_juice_amount, pass_chat_data=True)],
                self.INSERT_JUICE_DONE: [MessageHandler(Filters.text, self.insert_juice_done, pass_chat_data=True)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.dispatcher.add_handler(conversation_handler_add_juice)

        # Add conversation handler for request a dose
        self.ASK_DOSE_INIT, self.ASK_DOSE_GRAMS, self.ASK_DOSE_DONE = range(3)
        conversation_handler_ask_dose = ConversationHandler(
            entry_points=[CommandHandler('ask_dose', self.ask_dose_init, pass_chat_data=True)],
            states={
                self.ASK_DOSE_INIT: [MessageHandler(Filters.text, self.ask_dose_init, pass_chat_data=True)],
                self.ASK_DOSE_GRAMS: [MessageHandler(Filters.text, self.ask_dose_choice, pass_chat_data=True)],
                self.ASK_DOSE_DONE: [MessageHandler(Filters.text, self.ask_dose_done, pass_chat_data=True)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.dispatcher.add_handler(conversation_handler_ask_dose)

        #
        self.CHANGE_JUICE_LEFT_INIT, self.CHANGE_JUICE_LEFT_CHOICE, self.CHANGE_JUICE_LEFT_DONE = range(3)
        conversation_handler_change_juice_unit = ConversationHandler(
            entry_points=[CommandHandler('change_juice_amount', self.change_juice_left_init, pass_chat_data=True)],
            states={
                self.CHANGE_JUICE_LEFT_INIT: [MessageHandler(Filters.text,
                                                             self.change_juice_left_init, pass_chat_data=True)],
                self.CHANGE_JUICE_LEFT_CHOICE: [MessageHandler(Filters.text,
                                                               self.change_juice_left_choice, pass_chat_data=True)],
                self.CHANGE_JUICE_LEFT_DONE: [MessageHandler(Filters.text,
                                                             self.change_juice_left_done, pass_chat_data=True)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.dispatcher.add_handler(conversation_handler_change_juice_unit)


        # usage of a JobQueue (asynchronous thread for eval the flags)
        j = self.updater.job_queue
        self.job_machine_flags = j.run_repeating(self.check_flags, interval=5, first=0, context=True)
        self.job_machine_flags.flags = self.flags
        self.job_machine_flags.patient_id = self.patient_id
        # define all the possible mechanism for notification
        self.job_machine_flags.notify_distribution_start = False
        self.job_machine_flags.glass_inside = self.flags.flag_glass
        self.job_machine_flags.notify_distribution_done = False
        self.job_machine_flags.notify_glass_changes = False
        self.job_machine_flags.notify_distribution_dose_may_be_required = False

        # unknown_commands (this Handler must be added at the end)
        unknown_handler = MessageHandler(Filters.command, self.unknown)
        self.dispatcher.add_handler(unknown_handler)

    def run(self, flag_exit):
        """
        Main thread
        :param flag_exit:
        :return:
        """
        logging.info("BOT STARTS")
        self.updater.start_polling()
        while not flag_exit.is_set():
            flag_exit.wait(6)
        self.stop()
        logging.info("BOT ENDS")

    def stop(self):
        self.updater.stop()

    def idle(self):
        self.updater.idle()

    def check_flags(self, bot, job):
        """
        This functions has the goal to check the distribution
        :param bot:
        :param job:
        :return:
        """

        # the machine was turned off
        if job.flags.flag_exit.is_set():
            broadcast_message(bot, "the machine was turned off")

        # the next dose could not be enough juice
        if job.flags.flag_low_juice.is_set():
            db = Database()
            juice = db.pull_last_juice(self.patient_id)
            db.close()
            text_to_show = "Please fill up the juice container!\nonly " + str(juice.amount) + " ml left"
            broadcast_message(bot, text_to_show)
            job.flags.flag_low_juice.clear()

        if job.flags.flag_no_juice_left.is_set():
            db = Database()
            juice = db.pull_last_juice(self.patient_id)
            db.close()
            text_to_show = "Dose fails due to not enough juice!\nonly " + str(juice.amount) + " ml left"
            broadcast_message(bot, text_to_show)
            job.flags.flag_no_juice_left.clear()

        # the distribution is started
        if job.flags.flag_distribution_start.is_set() and not job.notify_distribution_start:
            broadcast_message(bot, "Your glass is now being filled up")
            job.notify_distribution_start = True
        elif not job.flags.flag_glass.is_set() and job.notify_distribution_start:
            job.notify_distribution_start = False

        if not job.notify_glass_changes and job.flags.flag_glass.is_set() and not job.glass_inside: # glass is here
            broadcast_message(bot, "Glass inside the system!")
            job.notify_glass_changes = True
            job.glass_inside = True
        elif not job.notify_glass_changes and not job.flags.flag_glass.is_set() and job.glass_inside:
            broadcast_message(bot, "Glass removed from the system!")
            job.notify_glass_changes = True
            job.glass_inside = False
        else:
            job.notify_glass_changes = False

        if job.flags.flag_fail_due_to_glass.is_set():
            broadcast_message(bot, "There is no glass!\nThe juice distribution fails!")
            job.flags.flag_fail_due_to_glass.clear()

        # the distribution is over
        if job.flags.flag_distribution_done.is_set() and not job.notify_distribution_done:
            broadcast_message(bot, "Your glass of juice can now be picked up")
            job.notify_distribution_done = True
        elif not job.flags.flag_distribution_done.is_set() and job.notify_distribution_done:
            job.notify_distribution_done = False

        if job.flags.flag_dose_may_be_required.is_set() and not job.notify_distribution_dose_may_be_required:
            db = Database()
            cgm = db.pull_last_cgm(self.patient_id)
            if cgm is not None:
                min_text = translate_timestamp_to_str(cgm.datetime_sgv)
                text_to_show = "Your glucose value is\n" + str(cgm.sgv) + " " + cgm.unit_bg + '\n' + min_text
                broadcast_message(bot, text_to_show)
            else:
                broadcast_message(bot, "Not available")
            db.close()
            # " Your glucose is: value\n and it falling, you are now able to fill up your glass of juice use /ask_dose"
            broadcast_message(bot, "you are now able to fill up your glass of juice\nuse /ask_dose")
            job.notify_distribution_dose_may_be_required = True
        elif not job.flags.flag_dose_may_be_required.is_set() and job.notify_distribution_dose_may_be_required:
            job.notify_distribution_dose_may_be_required = False

    def off(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id, text="everything will be turn off")
        bot.send_message(chat_id=update.message.chat_id, text="WARMING THE BOT WILL NO RESPONSE ANYMORE")
        self.flags.flag_exit.set()

    def clear_pump(self, bot, update):
        """
        :param bot:
        :param update:
        :return:
        """
        logging.info("User %s is trying to clear the pump", update.message.from_user.first_name)
        bot.send_message(chat_id=update.message.chat_id, text=" The pump will be activate soon for 10 seconds")
        if self.pump is None:
            pass
        else:
            self.pump.activate_for(10)
        return ConversationHandler.END

    def change_thresholds_init(self, bot, update, chat_data):
        """
        This is the function is the initial phase for modify hypo and hyper thresholds
        :param bot:
        :param update:
        :param chat_data:
        :return:
        """
        chat_data['user'] = update.message.from_user.first_name
        logging.info("User %s is trying to change hyper_hypo threshold", chat_data['user'])
        chat_data['patient'] = request_patient(self.patient_id)
        patient = chat_data['patient']

        chat_data['opt1'] = 'hypoglycemia\n\ncurrent value=' + glucose_value_to_str(patient.hypo_threshold,
                                                                                    patient.unit_bg)

        chat_data['opt2'] = 'hyperglycemia\n\ncurrent value=' + glucose_value_to_str(patient.hyper_threshold,
                                                                                     patient.unit_bg)
        reply_keyboard = [[chat_data['opt1'],
                           chat_data['opt2'],
                           ]]

        # display the possibilities
        ask_which_threshold = "BE CAREFUL!\nWRONG THRESHOLDS MAY COMPROMISE THE SYSTEM\n" \
                              "Which threshold do you want to modify?\nuse /cancel to undo the operation"
        bot.send_message(chat_id=update.message.chat_id, text=ask_which_threshold,
                         reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))

        return self.THRESHOLD_WHICH

    def which_threshold(self, bot, update, chat_data):
        # select with threshold should be checked
        text = update.message.text
        chat_data['choice'] = text

        # eval which one the user choice
        to_modify = str(chat_data['choice'])
        if chat_data['opt1'] in to_modify:
            logging.info("User %s asked to change the hypoglycemia threshold.", chat_data['user'])
            bot.send_message(chat_id=update.message.chat_id, text=ask_for_a_new_value)
            return self.THRESHOLD_MOD_HYPO

        elif chat_data['opt2'] in to_modify:
            logging.info("User %s asked to change the hyperglycemia threshold.", chat_data['user'])
            bot.send_message(chat_id=update.message.chat_id, text=ask_for_a_new_value)
            return self.THRESHOLD_MOD_HYPER

        else:  # all the other answers will kill the conversation
            bot.send_message(chat_id=update.message.chat_id, text=notify_mistake)
            chat_data.clear()
            return ConversationHandler.END

    def mod_hypo_threshold(self, bot, update, chat_data):
        chat_data['user'] = update.message.from_user.first_name

        # get the answer from the user
        chat_data['value'] = update.message.text
        patient = chat_data['patient']

        # check if the user has insert a number
        number_received = number_or_not(chat_data['value'])

        if number_received is None:
            del chat_data['value']
            bot.send_message(chat_id=update.message.chat_id, text=ask_value_not_correct)
            return self.THRESHOLD_MOD_HYPO

        # todo: take in account the unit inside the evaluation
        if patient.to_investigate_threshold is None:
            upper_limit = patient.hyper_threshold
        else:
            upper_limit = patient.to_investigate_threshold

        if eval_value_hypo(bot, update, number_received, upper_limit, patient.unit_bg):
            db = Database()
            db.update_patient_hypo_threshold(number_received, patient.id)
            db.close()
            text = "hypoglycemia threshold modified\nnew value=" + str(number_received) + " " + patient.unit_bg
            bot.send_message(chat_id=update.message.chat_id, text=text)
            logging.info("User %s changed the hypo threshold", chat_data['user'])
            chat_data.clear()
            return ConversationHandler.END
        else:
            bot.send_message(chat_id=update.message.chat_id,
                             text=ask_value_not_correct)
            return self.THRESHOLD_MOD_HYPO

    def mod_hyper_threshold(self, bot, update, chat_data):

        # get the answer from the user
        chat_data['value'] = update.message.text

        patient = chat_data['patient']
        # check if the user has insert a number
        number_received = number_or_not(chat_data['value'])

        # if was a not valid number ask it again
        if number_received is None:
            logging.info('it should redo the operation')
            bot.send_message(chat_id=update.message.chat_id,
                             text=ask_value_not_correct)
            del chat_data['value']
            return self.THRESHOLD_MOD_HYPER

        # check if the value can be stored
        # todo: take in account the unit
        if patient.to_investigate_threshold is None:
            lower_limit = patient.hypo_threshold
        else:
            lower_limit = patient.to_investigate_threshold

        if eval_value_hyper(bot, update, number_received, lower_limit, patient.unit_bg):
            del chat_data['choice']

            db = Database()
            db.update_patient_hyper_threshold(number_received, patient.id)
            db.close()
            text = "hyperglycemia threshold modified\nnew value=" + str(number_received) + " " + patient.unit_bg
            bot.send_message(chat_id=update.message.chat_id, text=text)
            logging.info("User %s changed the hyper threshold", chat_data['user'])
            chat_data.clear()
            return ConversationHandler.END
        else:
            bot.send_message(chat_id=update.message.chat_id,
                             text=ask_value_not_correct)
            return self.THRESHOLD_MOD_HYPER

    def change_to_investigate_init(self, bot, update, chat_data):
        # request the patient information (based on the database structure)
        chat_data['user'] = update.message.from_user.first_name
        logging.info("User %s is trying to change the to investigate threshold", chat_data['user'])

        patient = request_patient(self.patient_id)
        chat_data['patient'] = patient

        # handler the to investigate value handler
        ask_to_investigate = "please select the value that enable the dose button\n/cancel to abort the operation"
        chat_data['opt0'] = "Define a new value"
        chat_data['opt1'] = "Current value\nto be able to\nto request juice\n" + glucose_value_to_str(patient.to_investigate_threshold, patient.unit_bg)
        chat_data['opt2'] = "Disable\nthe possibility\nto request juice"

        if patient.to_investigate_threshold is None:
            reply_keyboard = [[chat_data['opt0']]]
        else:
            reply_keyboard = [[chat_data['opt1'],
                               chat_data['opt2']]]

        # display the possibilities
        bot.send_message(chat_id=update.message.chat_id, text=ask_to_investigate,
                         reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))

        return self.MOD_TO_INVESTIGATE_WHICH

    def change_to_investigate_which(self, bot, update, chat_data):

        chat_data['which'] = update.message.text
        patient = chat_data['patient']

        if chat_data['opt2'] in chat_data['which']:
            db = Database()
            db.update_patient_to_investigate_threshold(None, patient.id)
            db.close()
            bot.send_message(chat_id=update.message.chat_id, text="Value Update")
            logging.info("User %s has changed the to investigate threshold", chat_data['user'])
            chat_data.clear()
            return ConversationHandler.END
        elif chat_data['opt1'] in chat_data['which'] or chat_data['opt0'] in chat_data['which']:
            bot.send_message(chat_id=update.message.chat_id, text="please insert a new value")
            return self.MOD_TO_INVESTIGATE_DONE
        else:  # all the other answers will kill the conversation
            bot.send_message(chat_id=update.message.chat_id, text=notify_mistake)
            chat_data.clear()
            return ConversationHandler.END

    def change_to_investigate_done(self, bot, update, chat_data):
        # get the answer from the user
        chat_data['value'] = update.message.text
        patient = chat_data['patient']

        # check if the user has insert a number
        number_received = number_or_not(chat_data['value'])

        if number_received is None:
            del chat_data['value']
            bot.send_message(chat_id=update.message.chat_id,
                             text=ask_value_not_correct)
            return self.MOD_TO_INVESTIGATE_DONE

        if eval_to_investigate_value(bot, update, number_received, patient.hypo_threshold, patient.hyper_threshold):
            db = Database()
            db.update_patient_to_investigate_threshold(number_received, patient.id)
            db.close()
            bot.send_message(chat_id=update.message.chat_id, text='to investigate value updated')
            logging.info("User %s has changed the to investigate threshold", chat_data['user'])
            chat_data.clear()
            return ConversationHandler.END
        else:
            bot.send_message(chat_id=update.message.chat_id,
                             text=ask_value_not_correct)
            return self.MOD_TO_INVESTIGATE_DONE

    def cancel(self, bot, update):
        logging.info("User %s canceled the conversation.", update.message.from_user.first_name)
        bot.send_message(chat_id=update.message.chat_id, text='Modification undone', reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

# TODO: NEXT FIXING with more patient
    def start_init(self, bot, update, chat_data):

        # add the user to the bot list
        to_add = False
        try:
            # phase 1 verify if the user is inside the file
            with open("bot_users.txt", "r") as file:
                lines = list(file)
                if not str(update.message.chat_id) in lines:
                    to_add = True
        except FileNotFoundError:
            to_add = True
        finally:
            if to_add:
                with open("bot_users.txt", "a") as file:
                    file.write(str(update.message.chat_id) + "\n")

        # manager patient
        db = Database()
        patient = db.pull_patient(self.patient_id)

        if self.patient_id == 0:  # the machine was turned on for the first time
            bot.send_message(chat_id=update.message.chat_id, text="I'm a bot, please talk to me!\nWhat's your name?")
            patient = Patient(1, None, None, UnitDiabetes.MMOL.value, 3.9, 10, 5.9, "http.example.com")
            chat_data['patient'] = patient
            # patients = db.pull_all_patient()
            # if patients.shape[0] == 1:
            #     new_id = 1
            # else:
            #     new_id = patients['id'].max + 1  # insert a new patient based on the high id
            #     # todo: keep in mind what happen if you delete a patient
            #
            # self.patient_id = new_id
            # patient.id = new_id
            # chat_data['patient'] = patient
            # db.close()
            return self.START_NAME
        else:
            text = "Hi! " + str(patient.name)
            text = text + "\nREMEMBER:\n/help for show commands"
            text = text + "\n/change_info for modify your personal information"
            bot.send_message(chat_id=update.message.chat_id, text=text)
            db.close()
            return ConversationHandler.END

    def start_init_name(self, bot, update, chat_data):
        chat_data['name'] = update.message.text
        patient = chat_data['patient']
        patient.name = chat_data['name']
        text = "Hi " + str(patient.name) + "!\nremember with /change_info you can change your personal information "
        bot.send_message(chat_id=update.message.chat_id, text=text)

        reply_keyboard = [["TDM1",
                           "TDM2",
                           "OTHER",
                           ]]

        bot.send_message(chat_id=update.message.chat_id, text="Which type of Diabetes do you have?",
                         reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))

        return self.START_DIABETES

    def start_init_diabetes(self, bot, update, chat_data):
        chat_data['diabetes'] = update.message.text
        patient = chat_data['patient']
        if chat_data['diabetes'] in "TDM1" or chat_data['diabetes'] in "TDM2" or chat_data['diabetes'] in "OTHER":
            patient.diabetes_type = chat_data['diabetes']
        else:
            patient.diabetes_type = "OTHER"

        db = Database()
        self.patient_id = 1
        db.push_patient(patient)
        db.close()
        text = "Thank you for the information\nplease use /change_nightscout to set your nightscout address"
        text = text + "\n/help for see the bot commands"
        bot.send_message(chat_id=update.message.chat_id, text=text)
        chat_data.clear()
        return ConversationHandler.END

    def change_info_init(self, bot, update, chat_data):
        db = Database()
        patient = db.pull_patient(int(self.patient_id))
        chat_data['patient'] = patient
        text = "Hi! " + str(patient.name) + "\n"
        text = text + "Which personal information do you want to change?"
        text = text + "\n/cancel to undo the operation"

        opt1 = "Name\n(" + str(patient.name) + ")"
        opt2 = "Diabetes Type\n(" + str(patient.diabetes_type) + ")"
        chat_data['opt1'] = opt1
        chat_data['opt2'] = opt2

        reply_keyboard = [[opt1,
                           opt2,
                           ]]

        bot.send_message(chat_id=update.message.chat_id, text=text,
                         reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))

        return self.CHANGE_INFO_TYPE

    def change_info_type(self, bot, update, chat_data):

        chat_data['choice'] = update.message.text

        if chat_data['opt1'] in chat_data['choice']:
            bot.send_message(chat_id=update.message.chat_id,
                             text="Please insert your new name\n/cancel to undo the operation")
            return self.CHANGE_INFO_DONE

        elif chat_data['opt2'] in chat_data['choice']:
            reply_keyboard = [["TDM1",
                               "TDM2",
                               "OTHER",
                               ]]
            text = "Which type of Diabetes do you have?"
            text = text + "\n/cancel to undo the operation"
            bot.send_message(chat_id=update.message.chat_id,
                             text=text,
                             reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
            return self.CHANGE_INFO_DONE
        else:
            bot.send_message(chat_id=update.message.chat_id, text=notify_mistake)
            chat_data.clear()
            return ConversationHandler.END

    def change_info_done(self, bot, update, chat_data):

        value_to_insert = update.message.text
        patient = chat_data['patient']
        if "Diabetes Type" in chat_data['choice']:
            if value_to_insert in "TDM1" or value_to_insert in "TDM2" or value_to_insert in "OTHER":
                patient.diabetes_type = value_to_insert
            else:
                bot.send_message(chat_id=update.message.chat_id, text="Diabetes Type set to OTHER")
                patient.diabetes_type = "OTHER"
        else:
            patient.name = value_to_insert

        db = Database()
        db.push_patient(patient)
        db.close()
        bot.send_message(chat_id=update.message.chat_id, text="Modification done!")
        chat_data.clear()
        return ConversationHandler.END

    def helper(self, bot, update):
        text = " The following commands are available:\n"

        for command in COMMANDS:
            text += command[0] + " " + command[1] + "\n"
        bot.send_message(chat_id=update.message.chat_id, text=text)

    def unknown(self, bot, update):
        """
        This function reacts to unknown commands (each / not defined with an handler)
        :param bot:
        :param update:
        :return:
        """
        bot.send_message(chat_id=update.message.chat_id, text="Sorry, I didn't understand that command.")

    def error_callback(self, bot, update, error):
        """
        This function should manage the errors
        :param bot:
        :param update:
        :param error:
        :return:
        """
        try:
            raise error
        except Unauthorized as e:
            logging.warning(e.message)
            # remove update.message.chat_id from conversation list
        except BadRequest as e:
            # print(e)
            logging.warning(e.message)
            bot.send_message(chat_id=update.message.chat_id, text="BadRequest")
            # handle malformed requests - read more below!
        except TimedOut as e:
            # print(e)
            logging.warning(e.message)
            # handle slow connection problems
        except NetworkError as e:
            # print(e)
            logging.warning(e.message)
            # handle other connection problems
        except ChatMigrated as e:
            # print(e)
            logging.warning(e.message)
            # the chat_id of a group has changed, use e.new_chat_id instead
        except TelegramError as e:
            # print(e)
            logging.warning(e.message)
            # handle all other telegram related errors

    def get_last_cgm_data(self, bot, update):
        db = Database()
        cgm = db.pull_last_cgm(self.patient_id)
        if cgm is not None:
            min_text = translate_timestamp_to_str(cgm.datetime_sgv)
            text_to_show = "Your glucose value is\n" + str(cgm.sgv) + " " + cgm.unit_bg + '\n' + min_text
            bot.send_message(chat_id=update.message.chat_id, text=text_to_show)
        else:
            bot.send_message(chat_id=update.message.chat_id, text="Not available")
        db.close()

    def check_dose(self, bot, update):
        db = Database()
        try:
            dose = db.pull_last_dose(self.patient_id)

            # case 1: no dose was received previously
            if dose is None:
                bot.send_message(chat_id=update.message.chat_id, text="You have never received a dose!")
            # case 2: a bose was previoulsy insered
            else:
                juice = db.pull_juice(dose.juice_id)
                grams_delivered = math.floor((juice.carbohydrates * dose.amount_delivered) / 100) #todo: assumption = 100 ml unit
                min_text = translate_timestamp_to_str(dose.timestamp)
                text_to_show = "Last dose: " + str(grams_delivered) + "g (" + str(dose.amount_delivered) + " ml)\n"
                text_to_show = text_to_show + "received: " + min_text
                bot.send_message(chat_id=update.message.chat_id, text=text_to_show)

            # advise to the user that a dose may be delivered to the user
            if self.flags.flag_dose_may_be_required.is_set():
                bot.send_message(chat_id=update.message.chat_id,
                                 text="It is now possible to order a new dose\nuse /ask_dose to get a new one")
        finally:
            db.close()

    def ask_dose_init(self, bot, update, chat_data):
        chat_data['user'] = update.message.from_user.first_name
        logging.info("User %s is trying to ask for a new dose", chat_data['user'])
        if not self.flags.flag_dose_may_be_required.is_set():
            bot.send_message(chat_id=update.message.chat_id, text="It is not possible to request a dose")
            if not self.flags.flag_glass.is_set():
                bot.send_message(chat_id=update.message.chat_id, text="There is no glass inside the system")
            if not self.flags.flag_juice.is_set():
                bot.send_message(chat_id=update.message.chat_id, text="There is no juice inside the system")

            return ConversationHandler.END
        else:
            reply_keyboard = [["20 grams",
                               "15 grams",
                               "others",
                               ]]

            bot.send_message(chat_id=update.message.chat_id,
                             text="define grams to deliver\n/cancel to undo the operation",
                             reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))

            return self.ASK_DOSE_GRAMS

    def ask_dose_choice(self, bot, update, chat_data):
        # select with threshold should be checked
        text = update.message.text
        chat_data['choice'] = text

        # eval which one the user choice
        to_modify = str(chat_data['choice'])
        if "20 grams" in to_modify or "15 grams" in to_modify:
            if "20 grams" in to_modify:
                chat_data['grams'] = 20
            else:
                chat_data['grams'] = 15
            logging.info("User %s requests %s grams", chat_data['user'], str(chat_data['grams']))
            # insert a dose inside the system
            db = Database()
            juice = db.pull_last_juice(self.patient_id)
            amount = math.floor(float(chat_data['grams'] * 10 / juice.carbohydrates))
            if amount < juice.amount:
                logging.info("User %s requests %s grams", chat_data['user'], str(chat_data['grams']))
                # insert a dose inside the system
                insert_bot_dose(bot, update, chat_data['grams'], self.patient_id, self.flags)
                self.flags.flag_bot_request_dose.set()
            else:
                text = str(chat_data['grams']) + " g\nCannot be delivered, the juice is not enough"
                bot.send_message(chat_id=update.message.chat_id,
                                 text=text)
            chat_data.clear()
            return ConversationHandler.END

        elif "others" in to_modify:
            bot.send_message(chat_id=update.message.chat_id,
                             text="please define the grams requested\n/cancel to undo the operation")
            chat_data['grams'] = None
            return self.ASK_DOSE_DONE

        else:  # all the other answers will kill the conversation
            bot.send_message(chat_id=update.message.chat_id, text=notify_mistake)
            chat_data.clear()
            return ConversationHandler.END

    def ask_dose_done(self, bot, update, chat_data):
        # select with threshold should be check
        chat_data['value'] = update.message.text
        # check if the user has insert a number
        number_received = number_or_not(chat_data['value'])

        if number_received is None:
            del chat_data['value']
            bot.send_message(chat_id=update.message.chat_id,
                             text="Invalid number, please retry\n/cancel to undo the operation")
            return self.ASK_DOSE_GRAMS
        else:
            db = Database()
            juice = db.pull_last_juice(self.patient_id)
            amount = math.floor(float(number_received * 10 / juice.carbohydrates))
            if amount < juice.amount:
                logging.info("User %s requests %s grams", chat_data['user'], str(number_received))
                # insert a dose inside the system
                insert_bot_dose(bot, update, number_received, self.patient_id, self.flags)
                self.flags.flag_bot_request_dose.set()
            else:
                text = str(chat_data['value']) + " g\nCannot be delivered, the juice is not enough"
                bot.send_message(chat_id=update.message.chat_id,
                                 text=text)

            chat_data.clear()
            return ConversationHandler.END

    def show_thresholds(self, bot, update, chat_data):
        """
        :param bot:
        :param update:
        :param chat_data:
        :return:
        """
        chat_data['patient'] = request_patient(self.patient_id)
        patient = chat_data['patient']

        reply = "Thresholds currently in use\nhypoglycemia:" + str(patient.hypo_threshold) + " " + str(patient.unit_bg)
        reply = reply + "\nhyperglycemia:" + str(patient.hyper_threshold) + " " + str(patient.unit_bg)
        reply = reply + "\nrequest button:" + str(patient.to_investigate_threshold) + " " + str(patient.unit_bg)

        bot.send_message(chat_id=update.message.chat_id, text=reply)

    def change_data_source_init(self, bot, update, chat_data):
        chat_data['user'] = update.message.from_user.first_name
        logging.info("User %s is trying to change the source of data of the system.", chat_data['user'])

        # request the patient information (based on the database structure)
        chat_data['patient'] = request_patient(self.patient_id)
        patient = chat_data['patient']

        if patient.nightscout is None:  # no address was insert  # todo: is it really necessary?
            bot.send_message(chat_id=update.message.chat_id, text="Please insert your Nightscout address")
        else:
            reply = "Your current address is:" + str(patient.nightscout)
            reply = reply + "\ninsert a new one\n/cancel to undo the operation"
            bot.send_message(chat_id=update.message.chat_id, text=reply)

        return self.HANDLER_ADDRESS_DONE

    def change_data_source_done(self, bot, update, chat_data):
        patient = chat_data['patient']
        chat_data['new_address'] = update.message.text

        if not Nightscout.verify_address_error(chat_data['new_address']):  # in this case the address is working
            reply = "the address is working\n"
            found_unit = UnitDiabetes.MG.value
            if "units=mmol" in chat_data['new_address']:
                found_unit = UnitDiabetes.MMOL.value
                text_found_unit = UnitDiabetes.MMOL.value + " detected\n"
            elif "units=mg" in chat_data['new_address']:
                text_found_unit = UnitDiabetes.MG.value + " detected\n"
            else:
                text_found_unit = "Please verify data unit used\nIt will be used:" + UnitDiabetes.MG.value

            reply = reply + text_found_unit
            # update the patient address
            db = Database()
            db.update_patient_nightscout(chat_data['new_address'], patient.id)
            # update if necessary the system unit
            if not found_unit == patient.unit_bg:
                update_patient_unit(found_unit, patient.id)
            db.close()
            reply = reply + "\nuse /change_bg_unit to modify it"
            bot.send_message(chat_id=update.message.chat_id, text=reply)
            chat_data.clear()
            return ConversationHandler.END
        # no data are detected
        else:
            bot.send_message(chat_id=update.message.chat_id,
                             text="\nThe address is not working\nPlease verify if its correctness")
            bot.send_message(chat_id=update.message.chat_id, text=notify_mistake)

            chat_data.clear()
            return ConversationHandler.END

    def change_unit_init(self, bot, update, chat_data):
        chat_data['user'] = update.message.from_user.first_name
        logging.info("User %s is trying to change the system unit.", chat_data['user'])

        # request the patient information (based on the database structure)
        chat_data['patient'] = request_patient(self.patient_id)
        patient = chat_data['patient']

        # make the option variable on current unit
        if patient.unit_bg == UnitDiabetes.MMOL.value:
            other_unit = UnitDiabetes.MG.value
            chat_data['new_unit'] = UnitDiabetes.MG.value
        else:
            other_unit = UnitDiabetes.MMOL.value
            chat_data['new_unit'] = UnitDiabetes.MMOL.value

        reply_keyboard = [[str(patient.unit_bg) + "\n(in use)",
                           str(other_unit),
                           ]]

        ask_which_unit = "please select the system unit\n/cancel to abort the operation"
        bot.send_message(chat_id=update.message.chat_id, text=ask_which_unit,
                         reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))

        return self.MOD_BG_DONE

    def change_unit_done(self, bot, update, chat_data):

        # retrieve data from the chat
        patient = chat_data['patient']
        new_unit = chat_data['new_unit']

        # select with threshold should be checked
        text = update.message.text

        # case 1: the user select the keyboard
        if UnitDiabetes.MMOL.value in text or UnitDiabetes.MG.value in text:

            # case 1.1 the user has selected the same unit
            if str(patient.unit_bg) in text:
                bot.send_message(chat_id=update.message.chat_id, text='no modification performed')
                logging.info("User %s has NOT changed the unit.", chat_data['user'])

            # case 1.2 the user has selected a different unit
            else:
                update_patient_unit(new_unit, patient.id)
                text_to_display = 'system unit changed into: ' + text
                bot.send_message(chat_id=update.message.chat_id, text=text_to_display)
                logging.info("User %s has changed the unit to %s", chat_data['user'], text)

        # case 2: the user has selected other option
        else:
            logging.info("User %s fails the operation", chat_data['user'])
            bot.send_message(chat_id=update.message.chat_id, text=notify_mistake)

        chat_data.clear()
        return ConversationHandler.END

    # TODO: This part sucks
    def insert_juice_init(self, bot, update, chat_data):
        # request the patient information (based on the database structure)
        chat_data['patient'] = request_patient(self.patient_id)
        chat_data['user'] = update.message.from_user.first_name
        logging.info("User %s is trying to add a new juice", chat_data['user'])
        text = "Insert the carbohydrates inside the juice\n(unit to use: grams on 100 ml)"
        bot.send_message(chat_id=update.message.chat_id, text=text)
        return self.INSERT_JUICE_GRAMS

    def insert_juice_grams(self, bot, update, chat_data):
        chat_data['grams'] = str(update.message.text)
        value = number_or_not(chat_data['grams'])

        if value is None:
            bot.send_message(chat_id=update.message.chat_id, text=notify_mistake)
            chat_data.clear()
            return ConversationHandler.END
        else:
            chat_data['grams'] = value
            text = "Insert the AMOUNT inside the juice\n(unit to use: milliliters)"
            bot.send_message(chat_id=update.message.chat_id, text=text)
            return self.INSERT_JUICE_AMOUNT

    def insert_juice_amount(self, bot, update, chat_data):
        chat_data['amount'] = update.message.text
        value = number_or_not(chat_data['amount'])

        if value is None:
            bot.send_message(chat_id=update.message.chat_id, text=notify_mistake)
            chat_data.clear()
            return ConversationHandler.END
        else:
            text = "Juice to insert\n"
            text = text + "grams = " + str(chat_data['grams'])
            text = text + "\namount = " + str(chat_data['amount'])

            bot.send_message(chat_id=update.message.chat_id, text=text)
            chat_data['opt1'] = "YES\n(Insert Juice)"
            chat_data['opt2'] = "NO\n(Modify parameters)"
            reply_keyboard = [[chat_data['opt1'],
                               chat_data['opt2'],
                               ]]
            text = "Are the information correct?\nThe carbohydrates inside of the juice cannot be changed"
            bot.send_message(chat_id=update.message.chat_id, text=text,
                             reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
            return self.INSERT_JUICE_DONE

    # TODO: CAN BE improved
    def insert_juice_done(self, bot, update, chat_data):
        chat_data['option'] = update.message.text

        if chat_data['option'] in chat_data['opt1']:
            db = Database()
            juice = JuiceData(None,
                              int(datetime.now(tz=None).replace(microsecond=0).timestamp()),
                              chat_data['grams'],
                              chat_data['amount'],
                              self.patient_id)
            db.push_juice(juice)
            db.close()
            chat_data.clear()
            bot.send_message(chat_id=update.message.chat_id, text="Insertion complete")
            return ConversationHandler.END
        else:
            bot.send_message(chat_id=update.message.chat_id, text="Please retry: /add_juice")
            chat_data.clear()
            return ConversationHandler.END

    def change_juice_left_init(self, bot, update, chat_data):
        db = Database()
        juice = db.pull_last_juice(self.patient_id)
        chat_data['last_juice'] = juice

        if juice is None:
            bot.send_message(chat_id=update.message.chat_id, text="Please add a new juice\nuse /add_juice command")
        else:
            chat_data['opt1'] = "carbohydrates\n" + str(juice.carbohydrates) + " g"
            chat_data['opt2'] = "amount\n" + str(juice.amount) + " ml"

            reply_keyboard = [[chat_data['opt1'],
                               chat_data['opt2'],
                               ]]
            bot.send_message(chat_id=update.message.chat_id, text="Juice selected\n/cancel do undo the operation",
                             reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
            return self.CHANGE_JUICE_LEFT_CHOICE

    def change_juice_left_choice(self, bot, update, chat_data):
        chat_data['choice'] = update.message.text

        # eval current juice
        if chat_data['opt1'] in chat_data['choice']:
            text = "It is not possible to modify the carbohydrates inside the juice\nuse /add_juice to insert a new one"
            bot.send_message(chat_id=update.message.chat_id, text=text)
            chat_data.clear()
            return ConversationHandler.END

        elif chat_data['opt2'] in chat_data['choice']:
            bot.send_message(chat_id=update.message.chat_id,
                             text="please insert the new amount\n/cancel to undo the operation")
            return self.CHANGE_JUICE_LEFT_DONE
        else:
            bot.send_message(chat_id=update.message.chat_id, text=notify_mistake)
            chat_data.clear()
            return ConversationHandler.END

    def change_juice_left_done(self, bot, update, chat_data):
        chat_data['amount'] = str(update.message.text)
        value = number_or_not(chat_data['amount'])
        print(value)

        if value is None:
            bot.send_message(chat_id=update.message.chat_id, text=notify_mistake)
            chat_data.clear()
            return ConversationHandler.END
        else:
            juice = chat_data['last_juice']
            juice.amount = value
            db = Database()
            db.update_juice(juice)
            db.close()
            bot.send_message(chat_id=update.message.chat_id, text="Modification performed")
            chat_data.clear()
            return ConversationHandler.END

    # todo: finishing to developed
    def change_patient_init(self, bot, update, chat_data, patient_id):
        # chat_data['user'] = update.message.from_user.first_name
        # logging.info("User %s is trying to change the patient", chat_data['user'])
        #
        # chat_data['patient'] = request_patient(patient_id)
        # patient = chat_data['patient']
        # db = Database()
        # counter = db.pull_patient_counter()
        # print(counter)
        #
        # # case 1: there are already multiple patient selected
        # if counter > 1:
        #     chat_data['multy'] = True
        #     bot.send_message(chat_id=update.message.chat_id, text="Please insert the patient number\n")
        #     patients = db.pull_all_patient()
        #     print(patients)
        #     for row in patients.itertuples(index=True, name='Pandas'):
        #         index = getattr(row, "id")
        #         patient_name = getattr(row, "name")
        #         patient_diabetes = getattr(row, "diabetes_type")
        #
        #         if self.patient_id == index:
        #             text = "[CURRENT USER: " + str(index) + "] for " + str(patient_name) + " " + str(patient_diabetes)
        #             bot.send_message(chat_id=update.message.chat_id, text=text)
        #         if self.patient_id == 0 or index == 0:
        #             pass  # do nothing
        #         else:
        #             text = str(index) + " for " + str(patient_name) + " " + str(patient_diabetes)
        #             bot.send_message(chat_id=update.message.chat_id, text=text)
        # # case 2: there is just one patient inside the system
        # else:
        #     chat_data['opt1'] = "yes"
        #     chat_data['opt2'] = "No"
        #     chat_data['multy'] = False
        #
        #     reply_keyboard = [[chat_data['opt1'],
        #                        chat_data['opt2'],
        #                        ]]
        #     bot.send_message(chat_id=update.message.chat_id, text="Do you want to add a new user?",
        #                      reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        #
        # db.close()
        return self.CHANGE_PATIENT_DONE

# todo: finishing to developed
    def change_patient_done(self, bot, update, chat_data):
        # text = update.message.text
        # chat_data['choice'] = text
        #
        # if chat_data['multy'] or number_or_not(chat_data['choice']):
        #     db = Database()
        #     val = db.pull_patient(int(chat_data['choice']))
        #     if val is not None:
        #         self.patient_id = val.id
        #         text = "patient: " + val.name + " selected"
        #         bot.send_message(chat_id=update.message.chat_id, text=text)
        #     else:
        #         bot.send_message(chat_id=update.message.chat_id, text="the number inserted does not exist")
        #     db.close()
        #     chat_data.clear()
        #     return ConversationHandler.END
        # elif not chat_data['multy']:
        #     if chat_data['opt1'] in chat_data['choice']:  # a new user may be added
        #         bot.send_message(chat_id=update.message.chat_id, text="Use the command /start for the settings")
        #         self.patient_id = 0
        #     elif chat_data['opt2'] in chat_data['choice']:
        #         bot.send_message(chat_id=update.message.chat_id, text="No user added!")
        #     else:
        #         bot.send_message(chat_id=update.message.chat_id, text="Modification Not performed!")
        #
        #     chat_data.clear()
        #     return ConversationHandler.END
        #
        # else:
        #     bot.send_message(chat_id=update.message.chat_id, text=notify_mistake)
        #     chat_data.clear()
            return ConversationHandler.END
