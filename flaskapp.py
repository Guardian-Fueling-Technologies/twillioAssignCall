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
    repeat = False
    try:
        while(repeat):
            resp = VoiceResponse()

            gather = Gather(num_digits=1, timeout=3)
            gather.say('Press 1 to accept, press 2 to reject or press 3 to repeat this message.')
            resp.append(gather)

            resp.redirect('/voice')
            print(resp)
            if resp:
                print(f"User pressed: {resp}")
                resp.say(f'You pressed {resp}. Thank you!')
            elif(resp == 3):
                repeat = True
            else:
                resp.say('We didn\'t receive any input. Goodbye!')

    except Exception as e:
        return f"An error occurred: {str(e)}"


if __name__ == "__main__":
    app.run(port=8000, host='0.0.0.0')
