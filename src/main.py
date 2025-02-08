import os
import traceback
import logging
import logging.handlers as handlers
from datetime import datetime, timedelta

import telebot
import yaml

from client import AimHarderClient
from exceptions import NoBookingGoal, NoTrainingDay, BoxClosed, AlreadyBooked, TooEarly

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
    print(f"Calculated target date: {target_day.strftime('%Y-%m-%d %H:%M:%S')}")
    for key, value in booking_goals.items():
        if str(target_day.weekday()) == key:
            target_time = value["time"]
            target_datetime = datetime(target_day.year, target_day.month, target_day.day, int(target_time[:2]), int(target_time[2:]))
            logger.info(f"Calculated target datetime: {target_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Calculated target datetime: {target_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            diff = target_datetime - today
            diff_hours = diff.days * 24 + diff.seconds // 3600
            logger.info(f"Diff in hours between target datetime and now: {diff_hours} (hours-in-advance={hours_in_advance})")
            print(f"Diff in hours between target datetime and now: {diff_hours} (hours-in-advance={hours_in_advance})")
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

def get_booking_goal_data_yaml(booking_goals: dict) -> tuple[datetime, str, str, bool]:

    #Assuming that my class time is at 10.00am and the hours in advance is 49 hours. Given different examples, the results are the following ones:
    # today = datetime(2025,1,26,8,59,59,999999) => class datetime is 2025-01-28 10:00:00, diff_hours = 49, diff_minutes = 0,  diff_seconds = 3600,  diff_microseconds = 1.         Success = False
    # today = datetime(2025,1,26,9,0,0,000000)   => class datetime is 2025-01-28 10:00:00, diff_hours = 49, diff_minutes = 0,  diff_seconds = 3600,  diff_microseconds = 0.         Success = True
    # today = datetime(2025,1,26,9,0,0,000001)   => class datetime is 2025-01-28 10:00:00, diff_hours = 48, diff_minutes = 59,  diff_seconds = 3599, diff_microseconds = 999999.    Success = True
    # today = datetime(2025,1,26,9,0,1,000000)   => class datetime is 2025-01-28 10:00:00, diff_hours = 48, diff_minutes = 59, diff_seconds = 3599,  diff_microseconds = 0.         Success = True
    
    # today = datetime(2025,1,26,8,59,59,999999)
    # today = datetime(2025,1,26,9,0,0,0)
    # today = datetime(2025,1,26,9,0,0,1)
    # today = datetime(2025,1,26,9,0,1,0)

    # today = datetime.today()
    today = datetime(2025,2,9,9,33,0,0)


    #We iterate over the booking goals to find the one that matches the target day
    for goal in booking_goals:
        user_goal_day_str = goal.split(',')[0]
        user_goal_time_str = goal.split(',')[1]
        user_goal_class_name_str = goal.split(',')[2]
        hours_in_advance = int(goal.split(',')[3])

        target_day = today + timedelta(hours=hours_in_advance)

        logger.info(f"Calculated target date: {target_day.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Calculated target date: {target_day.strftime('%Y-%m-%d %H:%M:%S')}")

        #We check if today+hours_in_advance is the same day as the user goal day
        if str(target_day.strftime("%A")).lower() == user_goal_day_str.lower():

            #We calculate the datetime where we want to book the class
            class_datetime = datetime(target_day.year, target_day.month, target_day.day, int(user_goal_time_str[:2]), int(user_goal_time_str[2:]))
            logger.info(f"Calculated class to book datetime: {class_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Calculated class to book datetime: {class_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            
            #We calculate the difference in hours between the datetime of the class and now
            diff = class_datetime - today
            diff_hours = diff.days * 24 + diff.seconds // 3600
            logger.info(f"Diff in hours between class datetime and now: {diff_hours} (hours-in-advance={hours_in_advance})")
            print(f"Diff in hours between class datetime and now: {diff_hours} (hours-in-advance={hours_in_advance})")

            #There are 2 conditions, one when it is exactly time o'clock (09:00:00:000000) and another one when the time is 
            # over o'clock (09:00:00:000001). With this condition we skip the case when the time is immediately before o'clock (08:59:59:999999)
            if (diff_hours == hours_in_advance and diff.microseconds == 0) or (diff_hours < hours_in_advance):
                return (target_day, user_goal_time_str, user_goal_class_name_str, True)
            else:
                return (None, None, None, False)

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

def main(user, configuration):
    try:
        user = user
        email = configuration["email"]
        password = configuration["password"]
        box_name = configuration["box-name"]
        box_id = configuration["box-id"]
        booking_goals = configuration["booking-goals"]
        # hours_in_advance = configuration["hours-in-advance"]
        exceptions = configuration["exceptions"]
        notify_on_telegram = True if "telegram" in configuration else False
        if notify_on_telegram:
            telegram_bot_token = configuration["telegram"]["telegram-bot-token"]
            telegram_chat_id = configuration["telegram"]["telegram-chat-id"]

        #If the Telegram notifications are enabled, we instantiate the Telegram Bot
        if notify_on_telegram and telegram_bot_token and telegram_chat_id:
            bot = init_telegram_bot(telegram_bot_token)
        else:
            notify_on_telegram = False

        # target_day, target_time, target_name, success = get_booking_goal_data(hours_in_advance, booking_goals)
        class_day, class_time, class_name, success = get_booking_goal_data_yaml(booking_goals)
        
        if not success:
            logger.info(f"The class is not available yet or it is too late. Target date = {class_day.strftime('%Y-%m-%d')}")
            return

        #We log in into AimHarder platform
        client = AimHarderClient(
            email=email, password=password, box_id=box_id, box_name=box_name
        )
        logger.debug("Client connected to AimHarder.")

        #We fetch the classes that are scheduled for the target day
        classes = client.get_classes(class_day)

        # bookState = None => class is not booked and ready to be booked
        # bookState = 1 => class is already booked
        # bookState = 0 => class is booked but you are in the waiting list
        # waitlist = -1 => there is no max capacity on the waiting list
        # waitlist = 6 => the max capacity on the waiting list is 6
        
        #From all the classes fetched, we select the one we want to book.
        target_class = get_class_to_book(classes, class_time, class_name)
        
        #bookState = 0 => class is already booked, bookState = 1 => class is booked but you are in the waiting list
        # if target_class["bookState"] == 0 or target_class["bookState"] == 1:
        #     raise AlreadyBooked(class_day)

        #We book the class and notify to Telegram if required.
        if client.book_class(class_day, target_class):
            if notify_on_telegram:
                bot.send_message(telegram_chat_id, f"\U00002705 Booked! :) {class_day.strftime('%b')}-CW{class_day.strftime('%V')} _{class_day.strftime('%A')} - {class_day.strftime('%Y-%m-%d')}_ at {class_time} - {class_name} [{target_class["ocupation"]} / {target_class["limit"]}]")
            logger.debug(f"Training booked successfully!! :) {class_day.strftime('%A')} - {class_day.strftime('%Y-%m-%d')} at {class_time} -  {class_name}")
        else:
            logger.debug(f"Booking of the training unsuccessful. Target day: {class_day.strftime('%Y-%m-%d')}")
    except BoxClosed:
        logger.error("The box is closed!")
        if notify_on_telegram:
            bot.send_message(telegram_chat_id, f"\U00002714 The box is closed. Target: {class_day.strftime('%A')} - {class_day.strftime('%d %b %Y')}")
    except NoTrainingDay as e:
        logger.error("No training day today!")
        if notify_on_telegram:
            class_day = e.args[0]
            bot.send_message(telegram_chat_id, f"\U00002714 No training day. Target: {class_day.strftime('%A')} - {class_day.strftime('%d %b %Y')}")
    except TooEarly as e:
        logger.error("Too early to book the class!")
        if notify_on_telegram:
            class_day = e.args[0]
            bot.send_message(telegram_chat_id, f"\U0000274C Too early to book the class. Target: {class_day.strftime('%A')} - {class_day.strftime('%d %b %Y')}")
    except AlreadyBooked as e:
        logger.error("The class was already booked!")
        if notify_on_telegram:
            class_day = e.args[0]
            bot.send_message(telegram_chat_id, f"\U00002705 Already Booked! :) {class_day.strftime('%b')}-CW{class_day.strftime('%V')} _{class_day.strftime('%A')} - {class_day.strftime('%Y-%m-%d')}_ at {class_time} - {class_name}")
    except NoBookingGoal as e:
        logger.error("There is no booking goal!")
        if notify_on_telegram:
            not_found = e.args[0]
            bot.send_message(telegram_chat_id, f"\U0000274C {not_found} was not found!: {class_day.strftime('%b')}-CW{class_day.strftime('%V')} _{class_day.strftime('%A')} - {class_day.strftime('%Y-%m-%d')}_ at {class_time} - {class_name}")
    except Exception as e:
        if notify_on_telegram:
            bot.send_message(telegram_chat_id, f"\U0000274C Something went wrong. Target: {class_day.strftime('%A')} - {class_day.strftime('%d %b %Y')}")
            bot.send_message(telegram_chat_id, traceback.format_exc(), parse_mode='None')
        logger.error(traceback.format_exc())
        print(traceback.format_exc())

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

def load_yaml_config():
    with open('./config/aimharderbot_config.yaml', 'r') as file:
        loaded_config = yaml.safe_load(file)
    print(loaded_config)
    return loaded_config

if __name__ == "__main__":
 
    logger = init_logger()

    for config in load_yaml_config():
        for key, value in config.items():
            try:
                main(key, value)
            except Exception as e:
                print(e)
        
