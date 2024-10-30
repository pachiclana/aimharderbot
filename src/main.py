import argparse
import json
import os
import traceback
import logging
import logging.handlers as handlers
from datetime import datetime, timedelta

import telebot

from client import AimHarderClient
from exceptions import NoBookingGoal, NoTrainingDay, BoxClosed, AlreadyBooked

def get_booking_goal_time(day: datetime, booking_goals):
    #We take the future day we want to book the class on and check if it exists in the input json parameters
    try:
        time_goal = booking_goals[str(day.weekday())]["time"]
        name_goal = booking_goals[str(day.weekday())]["name"]
        logger.info(f"Found date ({day.strftime('%Y-%m-%d')}), time ({time_goal}) and name class ({name_goal}) to book.")
        return (
            time_goal,
            name_goal,
        )
    except KeyError:  # did not found a matching booking goal
        logger.error(f"Either the time or the name could not be found in the input parameters. There is no class to book on {day.strftime('%Y-%m-%d')}")
        raise NoTrainingDay
    
def get_booking_goal_data(hours_in_advance: int, booking_goals: dict) -> tuple[datetime, str, str, bool]:

    today = datetime.today()
    target_day = today + timedelta(hours=hours_in_advance)
    logger.info(f"Calculated target date: {target_day.strftime('%Y-%m-%d %H:%M:%S')}")
    for key, value in booking_goals.items():
        if str(target_day.weekday()) == key:
            target_time = value["time"]
            target_datetime = datetime(target_day.year, target_day.month, target_day.day, int(target_time[:2]), int(target_time[2:]))
            logger.info(f"Calculated target datetime: {target_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            diff = target_datetime - today
            diff_hours = diff.days * 24 + diff.seconds // 3600
            logger.info(f"Diff in hours between target datetime and now: {diff_hours} (hours-in-advance={hours_in_advance})")
            diff_minutes = (diff.seconds % 3600) // 60
            if (diff_hours == hours_in_advance and diff_minutes == 0) or (diff_hours < hours_in_advance):
                return (target_day, target_time, value["name"], True)
                # print(f"Target: {today.year}-{today.month}-{today.day} {today.hour}:{today.minute}:{today.second}")
                # print(f"Target: {target_datetime.year}-{target_datetime.month}-{target_datetime.day} {target_datetime.hour}:{target_datetime.minute}:{target_datetime.second}")
                # print(f"")
            else:
                return (None, None, None, False)
                # pass

    raise NoTrainingDay(target_day)


def get_class_to_book(classes: list[dict], target_time: str, class_name: str) -> dict:
    if len(classes) == 0:
        logger.error(f"Box is closed.")
        raise BoxClosed

    if any(target_time in s["timeid"] for s in classes):
        logger.info(f"Class found for time ({target_time})")
        if "OPEN" in class_name:
            found_classes = [s for s in classes if target_time in s["timeid"]]
        else:
            found_classes = [s for s in classes if target_time in s["timeid"] and 'OPEN' not in s['className']]
    else:
        logger.error(f"No class found for time ({target_time})")
        raise NoBookingGoal(target_time)

    if (len(found_classes)) > 1:
        if any(class_name in s["className"] for s in found_classes):
            logger.info(f"Class found for class name ({class_name})")
            found_classes = [s for s in found_classes if class_name in s["className"]]
        else:
            logger.error(f"No class found for class name ({class_name})")
            raise NoBookingGoal(class_name)
    
    logger.info(f"Class found: {found_classes[0]}")
    return found_classes[0]

def init_telegram_bot(telegram_bot_token):
    logger.info(f"Telegram notifications are enabled.")
    return telebot.TeleBot(telegram_bot_token, parse_mode='Markdown')

def main(email, password, booking_goals, box_name, box_id, hours_in_advance, notify_on_telegram, telegram_bot_token, telegram_chat_id):
    try:
        #If the Telegram notifications are enabled, we instantiate the Telegram Bot
        if notify_on_telegram and telegram_bot_token and telegram_chat_id:
            bot = init_telegram_bot(telegram_bot_token)
        else:
            notify_on_telegram = False

        target_day, target_time, target_name, success = get_booking_goal_data(hours_in_advance, booking_goals)
        
        if not success:
            logger.info(f"The class is not available yet or it is too late. Target date =  {target_day.strftime('%Y-%m-%d')}")
            return

        #We log in into AimHarder platform
        client = AimHarderClient(
            email=email, password=password, box_id=box_id, box_name=box_name
        )
        logger.debug("Client connected to AimHarder.")

        #We fetch the classes that are scheduled for the target day (normally, day on next week)
        classes = client.get_classes(target_day)
        
        #From all the classes fetched, we select the one we want to book.
        target_class = get_class_to_book(classes, target_time, target_name)
        
        #We book the class and notify to Telegram if required.
        if client.book_class(target_day, target_class):
            if notify_on_telegram:
                bot.send_message(telegram_chat_id, f"\U00002705 Booked! :) {target_day.strftime('%b')}-CW{target_day.strftime('%V')} _{target_day.strftime('%A')} - {target_day.strftime('%Y-%m-%d')}_ at {target_time} - {target_name} [{target_class["ocupation"]} / {target_class["limit"]}]")
            logger.debug(f"Training booked succesfully!! :) {target_day.strftime('%A')} - {target_day.strftime('%Y-%m-%d')} at {target_time} -  {target_name}")
        else:
            logger.debug(f"Booking of the training unsuccessfull. Target day: {target_day.strftime('%Y-%m-%d')}")
    except BoxClosed:
        logger.error("The box is closed!")
        if notify_on_telegram:
            bot.send_message(telegram_chat_id, f"\U00002714 The box is closed. Target: {target_day.strftime('%A')} - {target_day.strftime('%d %b %Y')}")
    except NoTrainingDay as e:
        logger.error("No training day today!")
        if notify_on_telegram:
            target_day = e.args[0]
            bot.send_message(telegram_chat_id, f"\U00002714 No training day. Target: {target_day.strftime('%A')} - {target_day.strftime('%d %b %Y')}")
    except AlreadyBooked as e:
        logger.error("The class was already booked!")
        if notify_on_telegram:
            target_day = e.args[0]
            bot.send_message(telegram_chat_id, f"\U00002705 Already Booked! :) {target_day.strftime('%b')}-CW{target_day.strftime('%V')} _{target_day.strftime('%A')} - {target_day.strftime('%Y-%m-%d')}_ at {target_time} - {target_name}")
    except NoBookingGoal as e:
        logger.error("There is no booking goal!")
        if notify_on_telegram:
            not_found = e.args[0]
            bot.send_message(telegram_chat_id, f"\U0000274C {not_found} was not found!: {target_day.strftime('%b')}-CW{target_day.strftime('%V')} _{target_day.strftime('%A')} - {target_day.strftime('%Y-%m-%d')}_ at {target_time} - {target_name}")
    
    except Exception as e:
        if notify_on_telegram:
            bot.send_message(telegram_chat_id, f"\U0000274C Something went wrong. Target: {target_day.strftime('%A')} - {target_day.strftime('%d %b %Y')}")
            bot.send_message(telegram_chat_id, traceback.format_exc(), parse_mode='None')
        logger.error(traceback.format_exc())

#We set up the loggers
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

    # Check whether the specified path exists or not
    isExist = os.path.exists(log_dir)
    if not isExist:
        # Create a new directory because it does not exist
        os.makedirs(log_dir)
        print("The new directory is created!")

    logHandler = handlers.RotatingFileHandler(log_fname, maxBytes=5242880, backupCount=1)
    logHandler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s - %(message)s')
    logHandler.setFormatter(formatter)

    logger.addHandler(logHandler)
    req_logger.addHandler(logHandler)
    url_logger.addHandler(logHandler)
    return logger


if __name__ == "__main__":
 
    logger = init_logger()

    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True, type=str)
    parser.add_argument("--password", required=True, type=str)
    parser.add_argument("--booking-goals", required=True, type=json.loads)
    parser.add_argument("--box-name", required=True, type=str)
    parser.add_argument("--box-id", required=True, type=int)
    parser.add_argument("--hours-in-advance", required=True, type=int, default=3)
    parser.add_argument("--notify-on-telegram", required=False, default=False, action='store_true')
    parser.add_argument("--telegram-bot-token", required=False, type=str, default='')
    parser.add_argument("--telegram-chat-id", required=False, type=str, default='abc')
    args = parser.parse_args()

    input = {key: value for key, value in args.__dict__.items() if value != ""}
    main(**input)
