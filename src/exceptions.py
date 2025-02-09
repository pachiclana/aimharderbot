from abc import ABC

MESSAGE_BOOKING_FAILED_NO_CREDIT = "No credit available"
MESSAGE_BOOKING_FAILED_UNKNOWN = "Unknown error"
MESSAGE_BOOKING_FAILED_MAX_WAIT_CAPACITY = "Max capacity of the waiting list overpassed"

class ErrorResponse(ABC, Exception):
    key_phrase = None

class TooManyWrongAttempts(ErrorResponse):
    key_phrase = "demasiadas veces"

class IncorrectCredentials(ErrorResponse):
    key_phrase = "incorrecto"

class BookingFailed(Exception):
    pass

class NoBookingGoal(Exception):
    pass

class NoTrainingDay(Exception):
    pass

class BoxClosed(Exception):
    pass

class AlreadyBooked(Exception):
    pass

class TooEarly(Exception):
    pass