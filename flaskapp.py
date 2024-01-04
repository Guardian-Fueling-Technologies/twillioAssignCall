from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather

app = Flask(__name__)

@app.route("/voice", methods=['GET', 'POST'])
def voice():
    """Respond to incoming phone calls with a menu of options"""
    # Start our TwiML response
    resp = VoiceResponse()

    if 'Digits' in request.values:
        choice = request.values['Digits']

        if choice == '1':
            resp.say('You selected sales. Good for you!')
            return str(resp)
        elif choice == '2':
            resp.say('You need support. We will help!')
            return str(resp)
        else:
            resp.say("Sorry, I don't understand that choice.")

    gather = Gather(num_digits=1)
    gather.say('For sales, press 1. For support, press 2.')
    resp.append(gather)

    resp.redirect('/voice')

    return str(resp)


if __name__ == "__main__":
    app.run(port=8000, host='0.0.0.0')
