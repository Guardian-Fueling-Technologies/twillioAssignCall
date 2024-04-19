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
import pytz
from twilio.twiml.voice_response import VoiceResponse, Gather
import os
import re
from urllib.parse import quote
from collections import namedtuple

# global var and db info
global twiliodf
twiliodf = pd.DataFrame()
global responseArr
responseArr = [None] * 1000
twiliodf_lock = threading.Lock()

# configured global var
server = os.environ.get("serverGFT")
database = os.environ.get("databaseGFT")
username = os.environ.get("usernameGFT")
password = os.environ.get("passwordGFT")
SQLaddress = os.environ.get("addressGFT")
account_sid = os.environ.get("account_sid")
auth_token = os.environ.get("auth_token")

class messageEditor():
    def read_number_digits(number):
        digits = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']
        return ' '.join(digits[int(digit)] for digit in str(number))

    def replace_numbers_with_spoken(text):
        numbers = re.findall(r'\b\d+\b', text)
        
        for number in numbers:
            spoken_representation = messageEditor.read_number_digits(int(number))
            text = text.replace(number, spoken_representation)
        return text

class serverFunct():
    def getTwillioStaging():
        while True:
            try:
                conn_str = f"DRIVER={SQLaddress};SERVER={server};DATABASE={database};UID={username};PWD={password};TrustServerCertificate=yes;"
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()

                sql_query = '''
                EXEC [dbo].[MR_P_TwilioOnCall] @Technician_ID = 'CAR426';
                '''

                cursor.execute(sql_query)
                columns = [column[0] for column in cursor.description]

                result = cursor.fetchall()
                data = [list(row) for row in result]

                global twiliodf
                with twiliodf_lock:
                    if twiliodf is not None and not twiliodf.empty and len(data) != 0 :
                        new_data_df = pd.DataFrame(data, columns=columns)
                        twiliodf = pd.concat([twiliodf, new_data_df], ignore_index=True)
                    else:                    
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
            except Exception as e:
                print(f"An error occurred: {e}")  
            progress()
            time.sleep(60*7)

    def unUpdateStaging():
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

    # return namedtuple
    def updateProc(ticket_no, order):
        conn_str = f"DRIVER={SQLaddress};SERVER={server};DATABASE={database};UID={username};PWD={password};TrustServerCertificate=yes;"
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        proc = '''
            EXEC [GFT].[dbo].[MR_OnCall_Escalation_Path] @TicketID = ?, @CurrentEscalationOrder = ?;
        '''
        cursor.execute(proc, (ticket_no, order))
        row = cursor.fetchone()
        Row = namedtuple('Row', ['Action','Phone','message','escalationOrder'])
        escalationData = Row(*row)
        conn.commit()
        cursor.close()
        conn.close()
        return escalationData

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
    with twiliodf_lock:
        if len(twiliodf) > 0:
            table_html = twiliodf.to_html(classes='table table-bordered table-hover', index=False)
            return render_template('html/main.html', table_html=table_html)
        else:
            return render_template('html/mainNoData.html')


# initial thread for tehnician oncall
@app.route('/visual/progress', methods=['GET'])
def visualprogress():
    global twiliodf
    with twiliodf_lock:
        return render_template('html/call.html', twiliodf=twiliodf)

def progress():
    threads = []
    global twiliodf
    with twiliodf_lock:
        if not twiliodf.empty:
            twiliodf_filtered = twiliodf[twiliodf['status'] == 0]
            for index, row in twiliodf_filtered.iterrows():
                assign_thread = threading.Thread(target=assignCall, args=(row,))
                threads.append(assign_thread)
                assign_thread.start()
        else:
            print("Empty dataframe")

    # return render_template('html/call.html')

# Technician oncall independent thread function
def assignCall(row):
    assignQuestion = row.get('text_Message', '')
    tech_phone_number = row.get('technician_NMBR', '')
    twilio_number = row.get('twilio_NMBR', '')
    firstdelaytime = row.get('calltime', '')
    escalation_time = row.get('escalation_time', '')
    ticket_no = row.get('ticket_no', '')
    Max_Escalations = row.get('Max_Escalations', '')
    client = Client(account_sid, auth_token)
    call_timestamps = []
    localEscalation = 0
    escalationData = ()
    
    global twiliodf
    with twiliodf_lock:
        twiliodf.loc[twiliodf['ticket_no'] == ticket_no, 'status'] = 1
    while localEscalation <= Max_Escalations:
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
                with twiliodf_lock:
                    twiliodf.loc[twiliodf['ticket_no'] == ticket_no, 'status'] = 2
                
                message_timestamp_str = message_timestamp.strftime("%Y-%m-%d %H:%M:%S")
                if response:
                    global responseArr
                    print((int)(ticket_no.split("-")[1]), responseArr[(int)(ticket_no.split("-")[1])], response[0].body, datetime.now(timezone.utc) - message_timestamp, message_timestamp_str)
                    latest_response = response[0] 
                    if (
                        latest_response.body.lower().strip() == yes3CharWord
                        and latest_response.date_sent > message_timestamp or responseArr[(int)(ticket_no.split("-")[1])] == 1
                    ):
                        message = client.messages.create(
                            body=f" you have acknowledged the call {ticket_no}. Thank you",
                            from_=twilio_number,
                            to=tech_phone_number
                        )
                        responseArr[(int)(ticket_no.split("-")[1])] = None
                        with twiliodf_lock:
                            twiliodf.loc[twiliodf['ticket_no'] == ticket_no, 'status'] = 99
                        serverFunct.updateReport(row, 1, message_timestamp, latest_response.date_sent.strftime("%Y-%m-%d %H:%M:%S"), row['ticket_no'], 0)
                        twiliodf = twiliodf.drop(twiliodf[twiliodf['ticket_no'] == ticket_no].index)
                        # end of case
                        return 
                else:
                    print("never text before", datetime.now(timezone.utc) - message_timestamp, message_timestamp_str)
                # overtime
                if datetime.now(timezone.utc) - message_timestamp > timedelta(minutes=firstdelaytime):
                    if len(call_timestamps) != 0 and datetime.now(timezone.utc) - message_timestamp > timedelta(minutes=escalation_time):
                        # text technician
                        with twiliodf_lock:
                            twiliodf.loc[twiliodf['ticket_no'] == ticket_no, 'status'] = 4
                        message = client.messages.create(
                            body=f" We have elevate the call to your manager due to overtime.",
                            from_=twilio_number,
                            to=tech_phone_number
                        )
                        localEscalation += 1
                        # serverFunct.updateReport(row, 2, message_timestamp, latest_response.date_sent.strftime("%Y-%m-%d %H:%M:%S"), row['ticket_no'], localEscalation+1)
                        break
                    # call repeat or datetime.now(timezone.utc) - call_timestamps[0] == timedelta(minutes=10)
                    if len(call_timestamps) == 0:
                        with twiliodf_lock:
                            twiliodf.loc[twiliodf['ticket_no'] == ticket_no, 'status'] = 3
                        call_timestamps.append(datetime.now(timezone.utc))
                        params = messageEditor.replace_numbers_with_spoken(row.get('voice_Message', ''))
                        encoded_params = quote(params)
                        call = client.calls.create(
                            to=tech_phone_number,
                            from_="+18556258756",
                            url = f"https://twilliocall.guardianfueltech.com/voice/{ticket_no}?callMessage={encoded_params}"
                            )
                    
        else:
            escalationData = serverFunct.updateProc(ticket_no, localEscalation)
            if escalationData.Phone:
                print(localEscalation, escalationData)
                if(escalationData.Action=="Call"):
                    params = messageEditor.replace_numbers_with_spoken(escalationData.message)
                    encoded_params = quote(params)
                    # print(encoded_params)
                    call = client.calls.create(
                        to=escalationData.Phone,
                        # to=tech_phone_number,
                        from_="+18556258756",
                        url = f"https://twilliocall.guardianfueltech.com/voice/{ticket_no}?callMessage={encoded_params}"
                        )
                    start_time = time.time()
                    while True:
                        with twiliodf_lock:
                            if (twiliodf.loc[twiliodf['ticket_no'] == ticket_no, 'status'] == 4).any():
                                twiliodf.loc[twiliodf['ticket_no'] == ticket_no, 'status'] = 5
                            else:
                                twiliodf.loc[twiliodf['ticket_no'] == ticket_no, 'status'] = 6
                        time.sleep(5)
                        print("escalated",(int)(ticket_no.split("-")[1]), responseArr[(int)(ticket_no.split("-")[1])], time.time() - start_time)
                        if (responseArr[(int)(ticket_no.split("-")[1])] == 1):
                            message = client.messages.create(
                                body=f"you have acknowledged the call {ticket_no}. Thank you",
                                from_=twilio_number,
                                to=escalationData.Phone,
                                # to=tech_phone_number,
                            )
                            responseArr[(int)(ticket_no.split("-")[1])] = None
                            with twiliodf_lock:
                                twiliodf.loc[twiliodf['ticket_no'] == ticket_no, 'status'] = 99
                            serverFunct.updateReport(row, 2, message_timestamp, latest_response.date_sent.strftime("%Y-%m-%d %H:%M:%S"), row['ticket_no'], 0)
                            twiliodf = twiliodf.drop(twiliodf[twiliodf['ticket_no'] == ticket_no].index)
                            # end of case
                            return 
                        if time.time() - start_time >= 120:
                            break
                elif(escalationData.Action=="Message"):
                    yes3CharWord = ''.join(random.choice(string.ascii_lowercase) for _ in range(3))
                    message_timestamp = datetime.now(timezone.utc)
                    message = client.messages.create(
                        body=assignQuestion+f" If yes, please reply with '{yes3CharWord}'.",
                        from_=twilio_number,
                        to=escalationData.Phone
                    )
                    while True:
                        time.sleep(5)
                        response = client.messages.list(
                            from_=escalationData.Phone,
                            to=twilio_number,
                            limit=1
                        )
                        message_timestamp_str = message_timestamp.strftime("%Y-%m-%d %H:%M:%S")
                        if response:
                            print(response[0].body, datetime.now(timezone.utc) - message_timestamp, message_timestamp_str)
                            latest_response = response[0]
                            # voice_response_str == "1" or 
                        if (latest_response.body.lower().strip() == yes3CharWord
                            and latest_response.date_sent > message_timestamp or responseArr[(int)(ticket_no.split("-")[1])] == 1):
                            message = client.messages.create(
                                body=f" you have acknowledged the call {ticket_no}. Thank you",
                                from_=twilio_number,
                                to=escalationData.Phone
                            )
                            responseArr[(int)(ticket_no.split("-")[1])] = None
                            with twiliodf_lock:
                                twiliodf.loc[twiliodf['ticket_no'] == ticket_no, 'status'] = 99
                            serverFunct.updateReport(row, 2, message_timestamp, latest_response.date_sent.strftime("%Y-%m-%d %H:%M:%S"), row['ticket_no'], 0)
                            twiliodf = twiliodf.drop(twiliodf[twiliodf['ticket_no'] == ticket_no].index)
                            # end of case
                            return 
                        else:
                            print("never text before", datetime.now(timezone.utc) - message_timestamp, message_timestamp_str)
                localEscalation += 1
            else:
                with twiliodf_lock:
                    twiliodf.loc[twiliodf['ticket_no'] == ticket_no, 'status'] = 7
                serverFunct.updateReport(row, 3, message_timestamp, latest_response.date_sent.strftime("%Y-%m-%d %H:%M:%S"), row['ticket_no'], 0)
                twiliodf = twiliodf.drop(twiliodf[twiliodf['ticket_no'] == ticket_no].index)
                return
        
# twilio customize voice 
@app.route("/voice/<ticket_no>", methods=['GET', 'POST'])
def voice(ticket_no):
    resp = VoiceResponse()
    callMessage = request.args.get('callMessage')
    if 'Digits' in request.values:
        choice = request.values['Digits']
        if choice == '1':
            global responseArr
            responseArr[(int)(ticket_no.split("-")[1])] = 1
            resp.say('You have acknowledged the call. Good for you!')
            return str(resp)
        elif choice == '9':
            params = messageEditor.replace_numbers_with_spoken(callMessage)
            encoded_params = quote(params)
            resp.redirect(f'/voice/{ticket_no}?callMessage={encoded_params}')
            return str(resp)
    gather = Gather(num_digits=1, finishOnKey="", timeout=20)
    gather.say(f'{callMessage} To acknowledge, please press 1. Press 9 to repeat.')
    resp.append(gather)
    return str(resp)


    
if __name__ == "__main__":   
    # serverFunct.unUpdateStaging()
    # ticketno sample 	
    # ticket_no = "240218-0020"
    # serverFunct.updateProc(ticket_no, 1)
    threading.Thread(target=serverFunct.getTwillioStaging, daemon=True).start()
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    app.run(port=8000, host='0.0.0.0', threaded=True)
