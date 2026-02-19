import os
import sys
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_number = os.getenv('TWILIO_PHONE_NUMBER')

if not account_sid or not auth_token:
    print("Error: TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN not set.")
    sys.exit(1)

client = Client(account_sid, auth_token)

# Normalize phone number (remove spaces)
if twilio_number:
    twilio_number = twilio_number.replace(' ', '')

try:
    incoming_phone_numbers = client.incoming_phone_numbers.list(phone_number=twilio_number)
except Exception as e:
    print(f"Error listing numbers: {e}")
    sys.exit(1)

if not incoming_phone_numbers:
    print(f"Error: Phone number {twilio_number} not found in account.")
    # Fallback: List all and print
    print("Available numbers:")
    all_numbers = client.incoming_phone_numbers.list(limit=5)
    for num in all_numbers:
        print(f"- {num.phone_number} ({num.sid})")
    sys.exit(1)

number_sid = incoming_phone_numbers[0].sid
print(f"Found SID: {number_sid} for number {twilio_number}")

if len(sys.argv) < 2:
    print("Usage: python setup_webhook.py <ngrok_url>")
    sys.exit(1)

ngrok_url = sys.argv[1]
if not ngrok_url.startswith("http"):
    ngrok_url = "https://" + ngrok_url

voice_url = f"{ngrok_url}/webhook/incoming-call"

print(f"Updating Voice URL to: {voice_url}")

try:
    client.incoming_phone_numbers(number_sid).update(
        voice_url=voice_url,
        voice_method='POST'
    )
    print("Successfully updated Twilio webhook!")
except Exception as e:
    print(f"Error updating webhook: {e}")
    sys.exit(1)
