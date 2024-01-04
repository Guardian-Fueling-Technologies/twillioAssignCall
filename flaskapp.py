from flask import Flask
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
import os

app = Flask(__name__)

account_sid = os.environ.get("account_sid")
auth_token = os.environ.get("auth_token")

client = Client(account_sid, auth_token)
      
@app.route("/voice", methods=['GET', 'POST'])
def voice():
    repeat = True  # Initialize repeat as True to enter the loop
    try:
        while repeat:
            resp = VoiceResponse()

            gather = Gather(numDigits=1, timeout=3)
            gather.say('Press 1 to accept, press 2 to reject, or press 3 to repeat this message.')
            resp.append(gather)

            print(str(resp))  # Print the XML representation of the response

            if 'Digits' in request.values:
                user_input = request.values['Digits']
                print(f"User pressed: {user_input}")
                
                if user_input == '1':
                    resp.say('You pressed 1. Thank you!')
                    repeat = False
                elif user_input == '2':
                    resp.say('You pressed 2. Rejected!')
                    repeat = False
                elif user_input == '3':
                    resp.say('You pressed 3. Repeating the message.')
                else:
                    resp.say('Invalid input. Goodbye!')
                    repeat = False
            else:
                resp.say('We didn\'t receive any input. Goodbye!')
                repeat = False

    except Exception as e:
        return f"An error occurred: {str(e)}"

    return str(resp)


if __name__ == "__main__":
    app.run(port=8000, host='0.0.0.0')
