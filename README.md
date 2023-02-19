# FitBot

Python script to automate your booking sessions in [aimharder.com](http://aimharder.com) platform. The docker container is ready to run in Raspberry Pi 3b+

## Usage

Having docker installed you only need to do the following command:

`docker run -it --rm --name aimharderbot aimharderbot:v1 --email='mail@mail.com' --password='password' --booking-goals='{"1": {"time":"1730", "name":"NAME"},"2": {"time":"1730", "name":"NAME"},"4": {"time":"1730", "name":"NAME"}}' --box-name='boxname' --box-id=1234 --days-in-advance=7`

Explanation about the fields:

`email`: self-explanatory

`password`: self-explanatory

`booking_goals`: expects a json where as keys you would use the day of the week as integer from 0 to 6 (Monday to Friday) and the value should be the time (HHMM) of the class and the name of the class or part of it.
Unfortunately this structure needs to be crazy escaped, but here's an example:

Mondays at 18:15 class name should contain ARIBAU
Wednesdays at 18:15 class name should contain ARIBAU
```python
{
  "0": {"time":"1815", "name":"ARIBAU"},
  "2": {"time":"1815", "name":"ARIBAU"}
}
```

`box-name`: this is the sub-domain you will find in the url when accessing the booking list from a browser, something like _https://**lahuellacrossfit**.aimharder.com/schedule_

`box-id`: it's always the same one for your gym, you can find it inspecting the request made while booking a class from the browser:

<img src="https://raw.github.com/pablobuenaposada/fitbot/master/inspect.png" data-canonical-src="https://raw.github.com/pablobuenaposada/fitbot/master/inspect.png" height="300" />

`days-in-advance`: this is how many days in advance the script should try to book classes from, so for example, if this script is being run on a Monday and this field is set to 3 it's going to try book Thursday class from `booking_goals`


Enjoy!
