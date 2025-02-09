LOGIN_ENDPOINT = "https://aimharder.com/login"

ERROR_TAG_ID = "loginErrors"


def book_endpoint(box_name):
    return f"https://{box_name}.aimharder.com/api/book"


def classes_endpoint(box_name):
    return f"https://{box_name}.aimharder.com/api/bookings"

def cancel_endpoint(box_name):
    #id: 86199208
    #late: 0
    #familyId: 
    return f"https://{box_name}.aimharder.com/api/cancelBooking"
