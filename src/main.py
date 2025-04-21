import argparse
import os
import traceback
import logging
import logging.handlers as handlers
from datetime import datetime, timedelta

import telebot
import yaml

from client import AimHarderClient
from exceptions import NoBookingGoal, NoTrainingDay, BoxClosed, AlreadyBooked, TooEarly

def init_logger():

    logger = logging.getLogger('aimharder-bot')
    logger.setLevel(logging.DEBUG)
    req_logger = logging.getLogger("requests")
    req_logger.setLevel(logging.DEBUG)
    url_logger = logging.getLogger("urllib3")
    url_logger.setLevel(logging.DEBUG)

    #20Mb = 20971520 bytes
    #15Mb = 15728640 bytes
    #5Mb = 5242880 bytes

    #We set the logs folder directory to be on the same folder of the execution file
    log_dir = os.path.join(os.path.normpath(os.getcwd() + os.sep), 'logs')
    log_fname = os.path.join(log_dir, 'aimharder-bot.log')

    #Create folder if it does not exist
    create_folder_if_not_exists(log_dir)

    logHandler = handlers.RotatingFileHandler(log_fname, maxBytes=5242880, backupCount=1)
    logHandler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s - %(message)s')
    logHandler.setFormatter(formatter)

    logger.addHandler(logHandler)
    req_logger.addHandler(logHandler)
    url_logger.addHandler(logHandler)
    return logger

def load_yaml_config(filename: str):
    with open(os.path.join('./config', filename), 'r') as file:
        loaded_config = yaml.safe_load(file)
    return loaded_config

def create_folder_if_not_exists(folder):
    if not os.path.exists(folder):
        os.makedirs(folder)

def get_booking_goal(booking_goals: dict) -> tuple[datetime, str, str, bool]:

    #Assuming that my class time is at 10.00am and the hours in advance is 49 hours. Given different examples, the results are the following ones:
    # today = datetime(2025,1,26,8,59,59,999999) => class datetime is 2025-01-28 10:00:00, diff_hours = 49, diff_minutes = 0,  diff_seconds = 3600,  diff_microseconds = 1.         Success = False
    # today = datetime(2025,1,26,9,0,0,000000)   => class datetime is 2025-01-28 10:00:00, diff_hours = 49, diff_minutes = 0,  diff_seconds = 3600,  diff_microseconds = 0.         Success = True
    # today = datetime(2025,1,26,9,0,0,000001)   => class datetime is 2025-01-28 10:00:00, diff_hours = 48, diff_minutes = 59,  diff_seconds = 3599, diff_microseconds = 999999.    Success = True
    # today = datetime(2025,1,26,9,0,1,000000)   => class datetime is 2025-01-28 10:00:00, diff_hours = 48, diff_minutes = 59, diff_seconds = 3599,  diff_microseconds = 0.         Success = True

    today = datetime.today()
    # today = datetime(2025,2,8,20,2,0,000000) 

    #We iterate over the booking goals to find the one that matches the target day
    for goal in booking_goals:
        user_goal_day_str = goal.split(',')[0]
        user_goal_time_str = goal.split(',')[1]
        user_goal_class_name_str = goal.split(',')[2]
        hours_in_advance = int(goal.split(',')[3])

        target_day = today + timedelta(hours=hours_in_advance)

        logger.info(f"Calculated target date: {target_day.strftime('%Y-%m-%d %H:%M:%S')}")
        # print(f"Calculated target date: {target_day.strftime('%Y-%m-%d %H:%M:%S')}")

        #We check if today+hours_in_advance is the same day as the user goal day
        if str(target_day.strftime("%A")).lower() == user_goal_day_str.lower():

            #We calculate the datetime where we want to book the class
            class_datetime = datetime(target_day.year, target_day.month, target_day.day, int(user_goal_time_str[:2]), int(user_goal_time_str[2:]))
            logger.info(f"Calculated class to book datetime: {class_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            # print(f"Calculated class to book datetime: {class_datetime.strftime('%Y-%m-%d %H:%M:%S')}")

            #We calculate the difference in hours between the datetime of the class and now
            diff = class_datetime - today
            diff_hours = diff.days * 24 + diff.seconds // 3600
            logger.info(f"Diff in hours between class datetime and now: {diff_hours} (hours-in-advance={hours_in_advance})")
            # print(f"Diff in hours between class datetime and now: {diff_hours} (hours-in-advance={hours_in_advance})")

            #There are 2 conditions, one when it is exactly time o'clock (09:00:00:000000) and another one when the time is
            # over o'clock (09:00:00:000001). With this condition we skip the case when the time is immediately before o'clock (08:59:59:999999)
            if (diff_hours == hours_in_advance and diff.microseconds == 0) or (diff_hours < hours_in_advance):
                return (target_day, user_goal_time_str, user_goal_class_name_str, True)
            else:
                return (target_day, user_goal_time_str, user_goal_class_name_str, False)

    raise NoTrainingDay(target_day)

def get_class_to_book(classes: list[dict], target_time: str, class_name: str) -> dict:
    if len(classes) == 0:
        logger.error(f"{user_name} - Box is closed.")
        raise BoxClosed

    if any(target_time in s["timeid"] for s in classes):
        logger.info(f"{user_name} - Class found for time ({target_time})")
        if "OPEN" in class_name:
            found_classes = [s for s in classes if target_time in s["timeid"]]
        else:
            found_classes = [s for s in classes if target_time in s["timeid"] and 'OPEN' not in s['className']]
    else:
        logger.error(f"{user_name} - No class found for time ({target_time})")
        raise NoBookingGoal(target_time)

    if (len(found_classes)) > 1:
        if any(class_name in s["className"] for s in found_classes):
            logger.info(f"{user_name} - Class found for class name ({class_name})")
            found_classes = [s for s in found_classes if class_name in s["className"]]
        else:
            logger.error(f"{user_name} - No class found for class name ({class_name})")
            raise NoBookingGoal(class_name)

    logger.info(f"{user_name} - Class found: {found_classes[0]}")
    return found_classes[0]

def init_telegram_bot(telegram_bot_token):
    logger.info(f"{user_name} - Telegram notifications are enabled.")
    return telebot.TeleBot(telegram_bot_token, parse_mode='Markdown')

def parse_config_params(config):
    try:
        email = config["email"]
        password = config["password"]
        box_name = config["box-name"]
        box_id = config["box-id"]
        booking_goals = config["booking-goals"]
        exceptions = config["exceptions"]
        notify_on_telegram = True if "telegram" in config else False
        if notify_on_telegram:
            telegram_bot_token = config["telegram"]["telegram-bot-token"]
            telegram_chat_id = config["telegram"]["telegram-chat-id"]
        return email, password, box_name, box_id, booking_goals, exceptions, notify_on_telegram, telegram_bot_token, telegram_chat_id
    except Exception as e:
        logger.error(f"{user_name} - Error parsing configuration parameters: {e}")
        raise e

def main(current_user, configuration):
    try:
        #We parse the configuration parameters
        email, password, box_name, box_id, booking_goals, exceptions, notify_on_telegram, telegram_bot_token, telegram_chat_id = parse_config_params(configuration)

        #If the Telegram notifications are enabled, we instantiate the Telegram Bot
        if notify_on_telegram and telegram_bot_token and telegram_chat_id:
            bot = init_telegram_bot(telegram_bot_token)
        else:
            notify_on_telegram = False

        class_day, class_time, class_name, success = get_booking_goal(booking_goals)

        if not success:
            logger.info(f"{current_user} - The class is not available yet or it is too late. Target date = {class_day.strftime('%Y-%m-%d')}. Class at: {class_time}")
            return

        #We log in into AimHarder platform
        client = AimHarderClient(email=email, password=password, box_id=box_id, box_name=box_name)
        logger.debug(f"{current_user} - Client connected to AimHarder.")

        #We fetch the classes that are scheduled for the target day
        classes = client.get_classes(class_day)

        #We check if there is already a class booked on the target day. If so, we skip the booking process.
        #bookState = 0 => class is already booked, bookState = 1 => class is booked but you are in the waiting list
        if any((class_item['bookState'] == 1 or class_item['bookState'] == 0) for class_item in classes):
            logger.error(f"{current_user} - The target class or another class is already booked on the target day!")
            raise AlreadyBooked(class_day)

        #From all the classes fetched, we select the one we want to book.
        target_class = get_class_to_book(classes, class_time, class_name)

        #We book the class and notify to Telegram if required.
        if client.book_class(class_day, target_class):
            if notify_on_telegram:
                bot.send_message(telegram_chat_id, f"\U00002705 {class_name}! _{class_day.strftime('%A')}_ {class_day.strftime('%d.%m.%Y')} at {class_time[:2]}:{class_time[2:]} - [{target_class["ocupation"]}/{target_class["limit"]}] ({target_class["id"]})")
            logger.debug(f"{current_user} - Training booked successfully!! {class_day.strftime('%A')} - {class_day.strftime('%Y-%m-%d')} at {class_time} -  {class_name}")
        else:
            logger.debug(f"{current_user} - Booking of the training unsuccessful. Target day: {class_day.strftime('%Y-%m-%d')}")
    except BoxClosed as e:
        logger.error("The box is closed!")
        # if notify_on_telegram:
            # bot.send_message(telegram_chat_id, f"\U00002714 The box is closed. Target: {class_day.strftime('%A')} - {class_day.strftime('%d %b %Y')}")
    except NoTrainingDay as e:
        logger.error("No training day today!")
        # if notify_on_telegram:
        #     class_day = e.args[0]
            # bot.send_message(telegram_chat_id, f"\U00002714 No training day. Target: {class_day.strftime('%A')} - {class_day.strftime('%d %b %Y')}")
    except TooEarly as e:
        logger.error("Too early to book the class!")
        # if notify_on_telegram:
        #     class_day = e.args[0]
            # bot.send_message(telegram_chat_id, f"\U0000274C Too early to book the class. Target: {class_day.strftime('%A')} - {class_day.strftime('%d %b %Y')}")
    except AlreadyBooked as e:
        logger.error("The class was already booked!")
        # if notify_on_telegram:
        #     class_day = e.args[0]
            # bot.send_message(telegram_chat_id, f"\U00002705 Already Booked! :) {class_day.strftime('%b')}-CW{class_day.strftime('%V')} _{class_day.strftime('%A')} - {class_day.strftime('%Y-%m-%d')}_ at {class_time} - {class_name}")
    except NoBookingGoal as e:
        logger.error("There is no booking goal!")
        # if notify_on_telegram:
        #     not_found = e.args[0]
            # bot.send_message(telegram_chat_id, f"\U0000274C {not_found} was not found!: {class_day.strftime('%b')}-CW{class_day.strftime('%V')} _{class_day.strftime('%A')} - {class_day.strftime('%Y-%m-%d')}_ at {class_time} - {class_name}")
    except Exception as e:
        if notify_on_telegram:
            bot.send_message(telegram_chat_id, f"\U0000274C Something went wrong. Target: {class_day.strftime('%A')} - {class_day.strftime('%d %b %Y')}")
            bot.send_message(telegram_chat_id, traceback.format_exc(), parse_mode='None')
        logger.error(f"{current_user} - {traceback.format_exc()}")
        print(traceback.format_exc())

#We set up the loggers

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--config-filename", required=True, type=str)
    args = parser.parse_args()

    config_file = os.path.normpath(args.config_filename)
    logger = init_logger()

    for config in load_yaml_config(config_file):
        for user_name, user_config in config.items():
            try:
                main(user_name, user_config)
            except Exception as e:
                print(e)

