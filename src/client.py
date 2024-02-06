from datetime import datetime
from http import HTTPStatus
from bs4 import BeautifulSoup
from requests import Session
import logging

from constants import (
    LOGIN_ENDPOINT,
    book_endpoint,
    classes_endpoint,
    ERROR_TAG_ID,
)
from exceptions import (
    BookingFailed,
    IncorrectCredentials,
    AlreadyBooked,
    TooManyWrongAttempts,
    MESSAGE_BOOKING_FAILED_UNKNOWN,
    MESSAGE_BOOKING_FAILED_NO_CREDIT,
)


class AimHarderClient:

    def __init__(self, email: str, password: str, box_id: int, box_name: str):
        self.logger = logging.getLogger('aimharder-bot')
        
        self.session = self._login(email, password)
        self.box_id = box_id
        self.box_name = box_name
        
    @staticmethod
    def _login(email: str, password: str):
        session = Session()
        response = session.post(
            LOGIN_ENDPOINT,
            data={
                "login": "Log in",
                "mail": email,
                "pw": password,
            },
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser").find(id=ERROR_TAG_ID)
        if soup is not None:
            if TooManyWrongAttempts.key_phrase in soup.text:
                raise TooManyWrongAttempts
            elif IncorrectCredentials.key_phrase in soup.text:
                raise IncorrectCredentials
        return session

    def get_classes(self, target_day: datetime):
        response = self.session.get(
            classes_endpoint(self.box_name),
            params={
                "box": self.box_id,
                "day": target_day.strftime("%Y%m%d"),
                "familyId": "",
            },
        )
        bookings = response.json().get("bookings")
        self.logger.info(f"Retrieved {len(bookings)} classes for day {target_day.strftime('%Y-%m-%d')}")
        return bookings

    def book_class(self, target_day: datetime, target_class: str) -> bool:
        response = self.session.post(
            book_endpoint(self.box_name),
            data={
                "id": target_class["id"],
                "day": target_day.strftime("%Y%m%d"),
                "insist": 0,
                "familyId": "",
            },
        )
        if response.status_code == HTTPStatus.OK:
            response = response.json()
            if "bookState" in response and response["bookState"] == -2:
                self.logger.error(f"Booking unsuccesful. There is no available credits. Max number of booked sessions reached.")
                raise BookingFailed(MESSAGE_BOOKING_FAILED_NO_CREDIT)
            if "bookState" in response and response["bookState"] == -12:
                self.logger.error(f"Booking unsuccesful. You cannot book the same session twice.")
                raise AlreadyBooked(target_day)
            if "errorMssg" not in response and "errorMssgLang" not in response:
                # booking went fine
                self.logger.info(f"Booking completed successfully.")
                return True
        self.logger.error(f"UNKNOWN ERROR!!!!!.")
        raise BookingFailed(MESSAGE_BOOKING_FAILED_UNKNOWN)
