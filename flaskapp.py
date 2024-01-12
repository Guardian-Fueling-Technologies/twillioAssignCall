from flask import Flask
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
import os

app = Flask(__name__)
            
@app.route("/voice", methods=['GET', 'POST'])
def voice():
    try:
        resp = VoiceResponse()

        gather = Gather(num_digits=1)
        gather.say('To accept the call, press 1. To decline the call, press 2.')
        resp.append(gather)

        resp.redirect('/voice')

        return str(resp)
    except Exception as e:
        return f"An error occurred: {str(e)}"

if __name__ == "__main__":
    app.run(port=8000, host='0.0.0.0', threaded=True)
