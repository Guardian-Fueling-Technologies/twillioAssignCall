from flask import Flask, render_template, redirect, url_for, request
import threading
import pandas as pd
from twilio.rest import Client
import time
from datetime import datetime, timezone, timedelta
from twilio.twiml.voice_response import Gather, VoiceResponse
import random
import string
import pyodbc
import pandas as pd
from twilio.twiml.voice_response import VoiceResponse, Gather
import os


server = os.environ.get("serverGFT")
database = os.environ.get("databaseGFT")
username = os.environ.get("usernameGFT")
password = os.environ.get("passwordGFT")
SQLaddress = os.environ.get("addressGFT")
account_sid = os.environ.get("account_sid")
auth_token = os.environ.get("auth_token")

conn_str = f"DRIVER={SQLaddress};SERVER={server};DATABASE={database};UID={username};PWD={password};TrustServerCertificate=yes;"
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

sql_query = '''
    SELECT * FROM [GFT].[dbo].[MR_T_TwilioOnCall]
    '''    

cursor.execute(sql_query)
columns = [column[0] for column in cursor.description]

result = cursor.fetchall()
data = [list(row) for row in result]
twiliodf = pd.DataFrame(data, columns=columns)
voice_response_str = ""

app = Flask(__name__)

@app.route('/')
def main_page():
    global twiliodf
    conn_str = f"DRIVER={SQLaddress};SERVER={server};DATABASE={database};UID={username};PWD={password};TrustServerCertificate=yes;"
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    sql_query = '''
        SELECT * FROM [GFT].[dbo].[MR_T_TwilioOnCall]
        '''    

    cursor.execute(sql_query)
    columns = [column[0] for column in cursor.description]

    result = cursor.fetchall()
    data = [list(row) for row in result]
    twiliodf = pd.DataFrame(data, columns=columns)
    table_html = twiliodf.to_html(classes='table table-bordered table-hover', index=False)
    return render_template('html/main.html', table_html=table_html)


@app.route('/get_voice_response')
def get_voice_response():
    global voice_response_str
    return jsonify(response=voice_response_str)

@app.route('/progress', methods=['GET', 'POST'])
def update_rows():
    threads = []
    global twiliodf
    print(twiliodf)
    for index, row in twiliodf.iterrows():
        assign_thread = threading.Thread(target=assignCall, args=(row,))
        threads.append(assign_thread)
        assign_thread.start()
    return render_template('html/call.html')

def assignCall(rows):
    global voice_response_str
    for index, row in twiliodf.iterrows():
        assignQuestion = row['assign_Message']
        tech_phone_number = row['technician_NMBR']
        manager_NMBR = row['manager_NMBR']
        twilio_number = row['twilio_NMBR']
        firstdelaytime=1
        callManagertime=2
        client = Client(account_sid, auth_token)
        call_timestamps = []
        # message method
        yes3CharWord = ''.join(random.choice(string.ascii_lowercase) for _ in range(3))
        no3CharWord = ''.join(random.choice(string.ascii_lowercase) for _ in range(3))
        message_timestamp = datetime.now(timezone.utc)
        message = client.messages.create(
            body=assignQuestion+f" If yes, please reply with '{yes3CharWord}'. If not, reply with '{no3CharWord}'.",
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
            if response:
                print(response[0].body, datetime.now(timezone.utc) - message_timestamp, message_timestamp_str)
                latest_response = response[0]
                if (
                    latest_response.body.lower() == yes3CharWord
                    and latest_response.date_sent > message_timestamp
                ):
                    message = client.messages.create(
                        body=f" you have accepted the call. Thank you",
                        from_=twilio_number,
                        to=tech_phone_number
                    )
                    print("Tech accepted the call.", latest_response.date_sent)
                    return 1, message_timestamp, latest_response.date_sent
                    break 
                elif (
                    latest_response.body.lower() == no3CharWord
                    and latest_response.date_sent > message_timestamp
                ):                
                    message = client.messages.create(
                        body=f" you have declined the call. Thank you",
                        from_=twilio_number,
                        to=tech_phone_number
                    )
                    print("Tech declined the call.")
                    return 2, message_timestamp, latest_response.date_sent
                    break
            else:
                print("never text before", datetime.now(timezone.utc) - message_timestamp, message_timestamp_str)
            # overtime
            if datetime.now(timezone.utc) - message_timestamp > timedelta(minutes=firstdelaytime):
                # print(datetime.now(timezone.utc) - message_timestamp)
                if len(call_timestamps) != 0 and datetime.now(timezone.utc) - message_timestamp > timedelta(minutes=callManagertime):
                    # text technician
                    message = client.messages.create(
                        body=f" We have elevate the call to your service manager due to overtime.",
                        from_=twilio_number,
                        to=tech_phone_number
                    )
                    print("call service manager")
                    call_timestamps.append(datetime.now(timezone.utc))
                    call = client.calls.create(
                        to=manager_NMBR,
                        from_="+18556258756",
                        url=f"https://handler.twilio.com/twiml/EHde6244b9fd963fe81b6c0fc467d07740?Name=Charlie&Date={message_timestamp_str}"
                    )
                    print("Initiating a phone call to elevate to acknowledge the call.")
                # call repeat or datetime.now(timezone.utc) - call_timestamps[0] == timedelta(minutes=10)
                    return 
                if len(call_timestamps) == 0:
                    call_timestamps.append(datetime.now(timezone.utc))
                    call = client.calls.create(
                        to=tech_phone_number,
                        from_="+18556258756",
                        url="https://twilliocall.guardianfueltech.com/voice"
                    )
                    print("Initiating a phone call to remind the tech to acknowledge the call.")

@app.route("/voice", methods=['GET', 'POST'])
def voice():
    # Start our TwiML response
    resp = VoiceResponse()
    global voice_response_str

    # If Twilio's request to our app included already gathered digits,
    # process them
    if 'Digits' in request.values:
        # Get which digit the caller chose
        choice = request.values['Digits']

        # <Say> a different message depending on the caller's choice
        if choice == '1':
            resp.say('You selected sales. Good for you!')
            voice_response_str = str(resp) 
            return voice_response_str
        elif choice == '2':
            resp.say('You need support. We will help!')
            voice_response_str = str(resp) 
            return voice_response_str
        elif choice == '3':
            resp.say('You pressed replay voice ')
            resp.redirect('/voice')
        else:
            # If the caller didn't choose 1 or 2, apologize and ask them again
            resp.say("Sorry, I don't understand that choice.")

    gather = Gather(num_digits=1)
    gather.say('To accept, press 1. To decline, press 2. To replay voice please press 3.')
    resp.append(gather)
    
    return str(resp)

if __name__ == "__main__":
    app.run(port=8000, host='0.0.0.0', threaded=True)
