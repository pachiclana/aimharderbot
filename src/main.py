import argparse
import json
import os
import traceback
import logging
import logging.handlers as handlers
from datetime import datetime, timedelta
import telebot

from client import AimHarderClient
from exceptions import NoBookingGoal, NoTrainingDay, BoxClosed

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


def get_class_to_book(classes: list[dict], target_time: str, class_name: str):
    if len(classes) == 0:
        logger.error(f"Box is closed.")
        raise BoxClosed

    if any(target_time in s["timeid"] for s in classes):
        logger.info(f"Class found for time ({target_time})")
        _classes = [s for s in classes if target_time in s["timeid"]]
    else:
        logger.error(f"No class found for time ({target_time})")
        raise NoBookingGoal

    if (len(_classes)) > 1:
        if any(class_name in s["className"] for s in _classes):
            logger.info(f"Class found for class name ({class_name})")
            _classes = [s for s in _classes if class_name in s["className"]]
        else:
            logger.error(f"No class found for class name ({class_name})")
            raise NoBookingGoal
    
    logger.info(f"Class found: {_classes[0]}")
    return _classes[0]["id"]

def init_telegram_bot(telegram_bot_token):
    logger.info(f"Telegram notifications are enabled.")
    return telebot.TeleBot(telegram_bot_token, parse_mode='Markdown')

def main(email, password, booking_goals, box_name, box_id, days_in_advance, notify_on_telegram, telegram_bot_token, telegram_chat_id):
    try:
        #If the Telegram notifications are enabled, we instantiate the Telegram Bot
        if notify_on_telegram and telegram_bot_token and telegram_chat_id:
            bot = init_telegram_bot(telegram_bot_token)
        else:
            notify_on_telegram = False

        target_day = datetime.today() + timedelta(days=days_in_advance)

        #We log in into AimHarder platform
        client = AimHarderClient(
            email=email, password=password, box_id=box_id, box_name=box_name
        )
        logger.debug("Client connected to AimHarder.")
        
        #We get the class time and name we want to book
        target_time, target_name = get_booking_goal_time(target_day, booking_goals)

        #We fetch the classes that are scheduled for the target day (normally, day on next week)
        classes = client.get_classes(target_day)
        
        #From all the classes fetched, we select the one we want to book.
        class_id = get_class_to_book(classes, target_time, target_name)
        
        #We book the class and notify to Telegram if required.
        if client.book_class(target_day, class_id):
            if notify_on_telegram:
                bot.send_message(telegram_chat_id, f"\U00002705 Booked! :) {target_day.strftime('%b')}-CW{target_day.strftime('%V')} _{target_day.strftime('%A')} - {target_day.strftime('%Y-%m-%d')}_ at {target_time} - {target_name}")
            logger.debug(f"Training booked succesfully!! :) {target_day.strftime('%A')} - {target_day.strftime('%Y-%m-%d')} at {target_time} -  {target_name}")
        else:
            logger.debug(f"Booking of the training unsuccessfull.")
    except BoxClosed:
        logger.error("The box is closed!")
        if notify_on_telegram:
            bot.send_message(telegram_chat_id, f"\U00002714 The box is closed. Target: {target_day.strftime('%A')} - {target_day.strftime('%d %b %Y')}")
    except NoTrainingDay:
        logger.error("No training day today!")
        if notify_on_telegram:
            bot.send_message(telegram_chat_id, f"\U00002714 No training day. Target: {target_day.strftime('%A')} - {target_day.strftime('%d %b %Y')}")
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
    parser.add_argument("--days-in-advance", required=True, type=int, default=3)
    parser.add_argument("--notify-on-telegram", required=False, default=False, action='store_true')
    parser.add_argument("--telegram-bot-token", required=False, type=str, default='')
    parser.add_argument("--telegram-chat-id", required=False, type=str, default='abc')
    args = parser.parse_args()

    input = {key: value for key, value in args.__dict__.items() if value != ""}
    main(**input)
