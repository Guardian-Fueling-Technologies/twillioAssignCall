from flask import Flask
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
import os

app = Flask(__name__)

account_sid = os.environ.get("account_sid")
auth_token = os.environ.get("auth_token")

client = Client(account_sid, auth_token)
import streamlit as st
            
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
    
@app.route('/streamlit')
def streamlit():
    st.set_page_config(page_title="My Streamlit App")
    st.write("Hello, world!")

if __name__ == "__main__":
    app.run(debug=True)
