# Download the helper library from https://www.twilio.com/docs/python/install
import os
from twilio.rest import Client
import time
from datetime import datetime, timezone, timedelta
import csv
import random
import string

def assignCall(account_sid, auth_token, assignQuestion, tech_phone_number,twilio_number, firstdelaytime=1, callManagertime=3):
    client = Client(account_sid, auth_token)
    call_timestamps = []
    # message method
    yes3CharWord = ''.join(random.choice(string.ascii_lowercase) for _ in range(3))
    no3CharWord = ''.join(random.choice(string.ascii_lowercase) for _ in range(3))
    message_timestamp = datetime.now(timezone.utc)
    message = client.messages.create(
        body=assignQuestion+f"If yes, please reply with '{yes3CharWord}'. If not, reply with '{no3CharWord}'.",
        from_=twilio_number,
        to=tech_phone_number
    )
    while True:
        # check every 10 sec
        time.sleep(10)

        response = client.messages.list(
            from_=tech_phone_number,
            to=twilio_number,
            limit=1
        )
        message_timestamp_str = message_timestamp.strftime("%Y-%m-%d%H:%M")
        print(response[0].body, datetime.now(timezone.utc) - message_timestamp, message_timestamp_str)
        if datetime.now(timezone.utc) - message_timestamp > timedelta(minutes=firstdelaytime):
            print(datetime.now(timezone.utc) - message_timestamp)
            if len(call_timestamps) != 0 and datetime.now(timezone.utc) - message_timestamp > timedelta(minutes=callManagertime):
                print("call service manager")
                # call_timestamps.append(datetime.now(timezone.utc))
                # call = client.calls.create(
                #     to=tech_phone_number,
                #     from_="+18556258756",
                #     url=f"https://handler.twilio.com/twiml/EHde6244b9fd963fe81b6c0fc467d07740?Name=Charlie&Date={message_timestamp_str}"
                # )
                # print("Initiating a phone call to remind the tech to acknowledge the call.")
            # call repeat or datetime.now(timezone.utc) - call_timestamps[0] == timedelta(minutes=10) 
            if len(call_timestamps) == 0:
                call_timestamps.append(datetime.now(timezone.utc))
                call = client.calls.create(
                    to=tech_phone_number,
                    from_="+18556258756",
                    url=f"https://handler.twilio.com/twiml/EHde6244b9fd963fe81b6c0fc467d07740?Name=Charlie&Date={message_timestamp_str}"
                )
    #             <Gather numDigits="1" action="/handle-key" method="POST">
    #     <Say>To accept the call, press 1. To decline the call, press 2.</Say>
    # </Gather>
                print("Initiating a phone call to remind the tech to acknowledge the call.")
        if response:
            latest_response = response[0]
            if (
                latest_response.body.lower() == yes3CharWord
                and latest_response.date_sent > message_timestamp
            ):
                print("Tech accepted the call.")
                return 1, message_timestamp, latest_response.date_sent
                break 
            elif (
                latest_response.body.lower() == no3CharWord
                and latest_response.date_sent > message_timestamp
            ):
                print("Tech declined the call.")
                return 0, message_timestamp, latest_response.date_sent
                break

with open("assignCall.csv", 'r') as csv_file:
    csv_reader = csv.DictReader(csv_file)

    for row in csv_reader:
        account_sid = row['account_sid']
        auth_token = row['auth_token']
        assignQuestion = row['assignMessage']
        tech_phone_number = row['tech_phone_number']
        twilio_number = row['twilio_number']
        assignCall(account_sid, auth_token, assignQuestion, tech_phone_number, twilio_number)
    