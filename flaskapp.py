from flask import Flask, render_template, redirect, url_for, request, jsonify
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
from urllib.parse import quote

voice_response_str = "firsttime"
twiliodf = pd.DataFrame()

server = os.environ.get("serverGFT")
database = os.environ.get("databaseGFT")
username = os.environ.get("usernameGFT")
password = os.environ.get("passwordGFT")
SQLaddress = os.environ.get("addressGFT")
account_sid = os.environ.get("account_sid")
auth_token = os.environ.get("auth_token")


def updateTwilio(row, status, message_timestamp, response_timestamp, ticket_no):
    conn_str = f"DRIVER={SQLaddress};SERVER={server};DATABASE={database};UID={username};PWD={password};TrustServerCertificate=yes;"
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    update_query = f'''
        INSERT INTO [dbo].[MR_Report_TwilioOnCall] (
            [text_Message],
            [voice_Message],
            [escalation_Message],
            [ticket_no],
            [Technician_ID],
            [technician_NMBR],
            [manager_NMBR],
            [twilio_NMBR],
            [status],
            [message_timestamp],
            [response_timestamp],
            [calltime],
            [callManagertime],
            [LastUpdated]
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    values = (
        row.get('text_Message', ''),
        row.get('voice_Message', ''), 
        row.get('escalation_Message', ''),
        ticket_no,
        row.get('Technician_ID', ''),
        row.get('technician_NMBR', ''),
        row.get('manager_NMBR', ''),
        row.get('twilio_NMBR', ''),
        status,
        message_timestamp,
        response_timestamp,
        row.get('calltime', ''),  # [calltime]
        row.get('callManagertime', ''),  # [callManagertime]
        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    )
    
    cursor.execute(update_query, values)
    conn.commit()
    cursor.close()
    conn.close()

app = Flask(__name__)
@app.route('/')
def main_page():
    global twiliodf
    conn_str = f"DRIVER={SQLaddress};SERVER={server};DATABASE={database};UID={username};PWD={password};TrustServerCertificate=yes;"
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    sql_query = '''
        SELECT * FROM [dbo].[MR_Staging_TwilioOnCall]
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

def assignCall(row):
    global voice_response_str
    assignQuestion = row.get('text_Message', '')
    tech_phone_number = row.get('technician_NMBR', '')
    twilio_number = row.get('twilio_NMBR', '')
    firstdelaytime = row.get('calltime', '')
    callManagertime = row.get('callManagertime', '')
    ticket_no = row.get('ticket_no', '')
    Max_Escalations = row.get('Max_Escalations', '')
    escalation_Order = row.get('escalation_Order', '')
    client = Client(account_sid, auth_token)
    call_timestamps = []
    # first time message method
    print(Max_Escalations)
    for localEscalation in range(0, Max_Escalations+1):
        if localEscalation == 0:
            yes3CharWord = ''.join(random.choice(string.ascii_lowercase) for _ in range(3))
            message_timestamp = datetime.now(timezone.utc)
            message = client.messages.create(
                body=assignQuestion+f" If yes, please reply with '{yes3CharWord}'.",
                from_=twilio_number,
                to=tech_phone_number
            )
            while True:
                # check every 10 sec
                time.sleep(5)

                response = client.messages.list(
                    from_=tech_phone_number,
                    to=twilio_number,
                    limit=1
                )
                message_timestamp_str = message_timestamp.strftime("%Y-%m-%d %H:%M:%S")
                if response:
                    print(voice_response_str, response[0].body, datetime.now(timezone.utc) - message_timestamp, message_timestamp_str)
                    latest_response = response[0]
                    if (voice_response_str == "1" or 
                        latest_response.body.lower().strip() == yes3CharWord
                        and latest_response.date_sent > message_timestamp
                    ):
                        message = client.messages.create(
                            body=f" you have acknowledged the call {ticket_no}. Thank you",
                            from_=twilio_number,
                            to=tech_phone_number
                        )
                        updateReport(row, 1, message_timestamp, latest_response.date_sent.strftime("%Y-%m-%d %H:%M:%S"), row['ticket_no'])
                        voice_response_str = "initial"
                        break 
                else:
                    print("never text before", datetime.now(timezone.utc) - message_timestamp, message_timestamp_str)
                # overtime
                if datetime.now(timezone.utc) - message_timestamp > timedelta(minutes=firstdelaytime):
                    if len(call_timestamps) != 0 and datetime.now(timezone.utc) - message_timestamp > timedelta(minutes=callManagertime):
                        # text technician
                        message = client.messages.create(
                            body=f" We have elevate the call to your service manager due to overtime.",
                            from_=twilio_number,
                            to=tech_phone_number
                        )
                        updateProc(ticket_no, localEscalation+1)
                        updateReport(row, 2, message_timestamp, latest_response.date_sent.strftime("%Y-%m-%d %H:%M:%S"), row['ticket_no'])

                    # call repeat or datetime.now(timezone.utc) - call_timestamps[0] == timedelta(minutes=10)
                        return 
                    if len(call_timestamps) == 0:
                        call_timestamps.append(datetime.now(timezone.utc))
                        params = replace_numbers_with_spoken(row.get('voice_Message', ''))
                        encoded_params = quote(params)
                        call = client.calls.create(
                            to=tech_phone_number,
                            from_="+18556258756",
                            url = f"https://twilliocall.guardianfueltech.com/voice/{ticket_no}?callMessage={encoded_params}"
                            )
                        voice_response_str = call._context
                        print("Initiating a phone call to remind the tech to acknowledge the call.")
                        

@app.route('/progress/<ticket_no>', methods=['GET', 'POST'])
def trigger_update_rows():
    update_rows()
    return render_template('html/call.html')

@app.route("/voice/<ticket_no>", methods=['GET', 'POST'])
def voice():
    resp = VoiceResponse()
    callMessage = request.args.get('callMessage')
    if 'Digits' in request.values:
        choice = request.values['Digits']

        if choice == '1':
            resp.say('You have accepted the call. Good for you!')
            voice_response_str = "1"
            return "1" 
        elif choice == '2':
            resp.say('You have declined the call. We will help!')
            voice_response_str = "2"
            return "2" 
        else:
            resp.say('I did not get your response.')

    gather = Gather(timeout=5, num_digits=1)
    gather.say(f'{callMessage}To accept, press 1. To decline, press 2. To replay voice please press 3.')
    resp.append(gather)
    resp.redirect('/voice')
    return str(resp)
    
if __name__ == "__main__":
    app.run(port=8000, host='0.0.0.0', threaded=True)
