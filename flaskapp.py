from twilio.twiml.voice_response import Gather, VoiceResponse
from flask import Flask, request

app = Flask(__name__)

@app.route("/voice", methods=['GET', 'POST'])
def voice():
    try:
        resp = VoiceResponse()
        gather = Gather(num_digits=1, timeout=3)
        gather.say('Press 1 to accept, press 2 to reject, or press 3 to repeat this message.')
        resp.append(gather)
        return str(resp)

    except Exception as e:
        return f"An error occurred: {str(e)}"

@app.route('/gather', methods=['GET', 'POST'])
def gather():
    try:
        resp = VoiceResponse()

        if 'Digits' in request.values:
            choice = request.values['Digits']
            
            if choice == '1':
                resp.say('You pressed 1. Call accepted.')
                return str(resp)
            elif choice == '2':
                resp.say('You pressed 2. Call rejected.')
                return str(resp)
            elif choice == '3':
                resp.redirect('/voice')
            else:
                resp.say("Invalid input. Goodbye.")
        else:
            # Handle the case where no input is received
            resp.say("Sorry, I don't understand that choice. Goodbye.")

        return str(resp)

    except Exception as e:
        return f"An error occurred: {str(e)}"



if __name__ == "__main__":
    app.run(port=8000, host='0.0.0.0', threaded=True)
