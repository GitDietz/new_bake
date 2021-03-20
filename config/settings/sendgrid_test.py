# using SendGrid's Python Library
# https://github.com/sendgrid/sendgrid-python
import environ
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

env = environ.Env()
environ.Env.read_env()

message = Mail(
    from_email='asharpsystems@gmail.com',
    to_emails='africanmeats@gmail.com',
    subject='Sending with Twilio SendGrid is Fun',
    html_content='<strong>and easy to do anywhere, even with Python</strong>')
try:
    sg = SendGridAPIClient(env('MAIL_KEY'))
    response = sg.send(message)
    print(response.status_code)
    print(response.body)
    print(response.headers)
    print('completed! ')
except Exception as e:
    print(e.message)
