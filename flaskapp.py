from twilio.twiml.voice_response import Gather, VoiceResponse
from flask import Flask, request

app = Flask(__name__)

@app.route("/voice", methods=['GET', 'POST'])
def voice():
    try:
        user_input = request.values.get('Digits', None)

        resp = VoiceResponse()

        if user_input == '1':
            resp.say("You pressed 1. Call accepted.")
        elif user_input == '2':
            resp.say("You pressed 2. Call rejected.")
        elif user_input == '3':
            resp.say('Press 1 to accept, press 2 to reject, or press 3 to repeat this message.')
            resp.redirect('/voice')
        else:
            resp.say("Invalid input. Goodbye.")

        return str(resp)

    except Exception as e:
        return f"An error occurred: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
