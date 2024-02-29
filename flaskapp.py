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
import re
from urllib.parse import quote

twiliodf = pd.DataFrame()

server = os.environ.get("serverGFT")
database = os.environ.get("databaseGFT")
username = os.environ.get("usernameGFT")
password = os.environ.get("passwordGFT")
SQLaddress = os.environ.get("addressGFT")
account_sid = os.environ.get("account_sid")
auth_token = os.environ.get("auth_token")


def read_number_digits(number):
    digits = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']
    return ' '.join(digits[int(digit)] for digit in str(number))

def replace_numbers_with_spoken(text):
    numbers = re.findall(r'\b\d+\b', text)
    
    for number in numbers:
        spoken_representation = read_number_digits(int(number))
        text = text.replace(number, spoken_representation)
    return text

def updateProc(ticket_no, order):
    conn_str = f"DRIVER={SQLaddress};SERVER={server};DATABASE={database};UID={username};PWD={password};TrustServerCertificate=yes;"
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    proc = f'''
        CALL [dbo].[MR_OnCall_Escalation_Path] (?, ?)
    '''    
    print((proc, (ticket_no, order)))
    cursor.execute(proc, (ticket_no, order))
    row = cursor.fetchone()
    print(row)
    conn.commit()
    cursor.close()
    conn.close()

def updateReport(row, status, message_timestamp, response_timestamp, ticket_no, escalation_Order):
    conn_str = f"DRIVER={SQLaddress};SERVER={server};DATABASE={database};UID={username};PWD={password};TrustServerCertificate=yes;"
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    update_query = f'''
        INSERT INTO [dbo].[MR_Report_TwilioOnCall] (
        [ticket_no]
        ,[Technician_ID]
        ,[technician_NMBR]
        ,[status]
        ,[escalation_Order]
        ,[message_timestamp]
        ,[response_timestamp]
        ,[calltime]
        ,[LastUpdated]
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    values = (
        ticket_no,
        row.get('Technician_ID', ''),
        row.get('technician_NMBR', ''),
        status,
        escalation_Order,
        message_timestamp,
        response_timestamp,
        row.get('calltime', ''),  # [calltime]
        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    )

    cursor.execute(update_query, values)
    conn.commit()
    cursor.close()
    conn.close()

app = Flask(__name__)
        
# Route to render the main page
@app.route('/')
def main_page():
    global twiliodf
    if len(twiliodf) > 0:
        table_html = twiliodf.to_html(classes='table table-bordered table-hover', index=False)
        return render_template('html/main.html', table_html=table_html)
    else:
        return render_template('html/mainNoData.html')
    # <form method="get" action="{{ url_for('update_rows') }}">
    #     <button type="submit" class="assign-call-button">Assign Call</button>
    # </form>

@app.route('/progress', methods=['GET', 'POST'])
def update_rows():
    threads = []
    global twiliodf
    for index, row in twiliodf.iterrows():
        assign_thread = threading.Thread(target=assignCall, args=(row,))
        threads.append(assign_thread)
        assign_thread.start()    
    return render_template('html/call.html')

def assignCall(row):
    voice_response_str = "0"
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
                    print(response[0].body, datetime.now(timezone.utc) - message_timestamp, message_timestamp_str)
                    latest_response = response[0]
                    # voice_response_str == "1" or 
                    if (
                        latest_response.body.lower().strip() == yes3CharWord
                        and latest_response.date_sent > message_timestamp
                    ):
                        message = client.messages.create(
                            body=f" you have acknowledged the call {ticket_no}. Thank you",
                            from_=twilio_number,
                            to=tech_phone_number
                        )
                        updateReport(row, 1, message_timestamp, latest_response.date_sent.strftime("%Y-%m-%d %H:%M:%S"), row['ticket_no'], 0)
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
                        updateReport(row, 2, message_timestamp, latest_response.date_sent.strftime("%Y-%m-%d %H:%M:%S"), row['ticket_no'], localEscalation+1)

                    # call repeat or datetime.now(timezone.utc) - call_timestamps[0] == timedelta(minutes=10)
                        return 
                    if len(call_timestamps) == 0:
                        call_timestamps.append(datetime.now(timezone.utc))
                        params = replace_numbers_with_spoken(row.get('voice_Message', ''))
                        encoded_params = quote(params)
                        call = client.calls.create(
                            to=tech_phone_number,
                            from_="+18556258756",
                            url = f"https://twilliocall.guardianfueltech.com/voice?callMessage={encoded_params}"
                            )
                        print("Initiating a phone call to remind the tech to acknowledge the call.")

@app.route("/voice", methods=['POST','GET'])
def voice():
    resp = VoiceResponse()
    callMessage = request.args.get('callMessage')
    if 'Digits' in request.values:
        choice = request.values['Digits']

        if choice == '1':
            resp.say('You have acknowledged the call. Good for you!')
            return str(resp)
            # You can handle the response here or save it to a global variable if needed
        else:
            resp.say('I did not get your response.')
            return str(resp)

    gather = Gather(timeout=5, num_digits=1)
    gather.say(f'{callMessage}To acknowledge, press 1. To replay voice please press 3.')
    resp.append(gather)
    resp.redirect(f'/voice')
    return str(resp)

    
if __name__ == "__main__":
    def fetch_and_update_data():
        conn_str = f"DRIVER={SQLaddress};SERVER={server};DATABASE={database};UID={username};PWD={password};TrustServerCertificate=yes;"
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        sql_query = '''
        SELECT
        [text_Message]
        ,[voice_Message]
        ,[Ack_Message]
        ,[overTime_message]
        ,[Max_Escalations]
        ,[Processed]
        ,[ticket_no]
        ,[Technician_ID]
        ,[technician_NMBR]
        ,[manager_NMBR]
        ,[twilio_NMBR]
        ,[status]
        ,[message_timestamp]
        ,[response_timestamp]
        ,[calltime]
        ,[callManagertime]
        ,[LastUpdated]
        FROM [GFT].[dbo].[MR_Staging_TwilioOnCall] WITH(NOLOCK)
        WHERE [technician_NMBR] <> ? AND Processed <> 1;
        '''

        cursor.execute(sql_query, "None")
        columns = [column[0] for column in cursor.description]

        result = cursor.fetchall()
        data = [list(row) for row in result]
        
        global twiliodf
        twiliodf = pd.DataFrame(data, columns=columns)
        update_query = '''
            UPDATE [GFT].[dbo].[MR_Staging_TwilioOnCall]
            SET Processed = 1
            WHERE Processed <> 1;
        '''

        cursor.execute(update_query)
        conn.commit()
        cursor.close()
        conn.close()
        print("processed also update", twiliodf)
    
    def unUpdate():
        conn_str = f"DRIVER={SQLaddress};SERVER={server};DATABASE={database};UID={username};PWD={password};TrustServerCertificate=yes;"
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        update_query = '''
            UPDATE [GFT].[dbo].[MR_Staging_TwilioOnCall]
            SET Processed = 0
            WHERE Processed = 1;
        '''

        cursor.execute(update_query)
        conn.commit()
        cursor.close()
        conn.close()
    def getTwillioStaging():
        while True:
            fetch_and_update_data()
            time.sleep(60*7)
    unUpdate()
    threading.Thread(target=getTwillioStaging, daemon=True).start()
    app.run(port=8000, host='0.0.0.0', threaded=True)
