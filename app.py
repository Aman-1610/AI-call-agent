from flask import Flask, request, render_template
from twilio.twiml.voice_response import VoiceResponse, Start
from twilio.rest import Client
import openai
import os
from datetime import datetime
from flask_socketio import SocketIO
from enhanced_call_handler import EnhancedCallHandler
import call_routing
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
# Use 'threading' for Windows local development, let SocketIO decide for others (production, gevent)
import sys
async_mode = 'threading' if sys.platform.startswith('win') else 'gevent'
socketio = SocketIO(app, async_mode=async_mode, cors_allowed_origins="*")

# Configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
HUMAN_SUPPORT_NUMBER = os.getenv('HUMAN_SUPPORT_NUMBER', '+15555555555') # Example fallback

# Initialize clients
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Store active calls
active_calls = {}

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/webhook/incoming-call', methods=['POST'])
def handle_incoming_call():
    """Handle incoming call webhook from Twilio"""
    from_number = request.form.get('From', 'Unknown')
    call_sid = request.form.get('CallSid')
    
    # Store the call
    active_calls[call_sid] = EnhancedCallHandler(call_sid, from_number)
    
    # Notify dashboard
    timestamp = datetime.now().isoformat()
    socketio.emit('call_started', {
        'call_sid': call_sid,
        'from_number': from_number,
        'timestamp': timestamp
    })
    
    # Create TwiML response
    resp = VoiceResponse()
    resp.say("Hello! You've reached the AI assistant. How can I help you today?")
    
    # Start streaming (if we implemented real-time audio) - keeping it as placeholder or removing if not used
    # The user's original code had it. I will keep it but it's not fully utilized in this gathered-based flow.
    # start = Start()
    # start.stream(url=f'wss://{request.host}/stream/{call_sid}')
    # resp.append(start)
    
    # Use Gather for speech input
    gather = resp.gather(input='speech', action='/webhook/voice-input', method='POST', speechTimeout='auto')
    
    return str(resp)

@app.route('/webhook/voice-input', methods=['POST'])
def handle_voice_input():
    """Handle voice input from Twilio speech recognition"""
    call_sid = request.form.get('CallSid')
    speech_result = request.form.get('SpeechResult')
    
    if call_sid in active_calls:
        call_handler = active_calls[call_sid]
        
        # Send user input to dashboard
        socketio.emit('call_updated', {
            'call_sid': call_sid,
            'speaker': 'Caller',
            'message': speech_result,
            'timestamp': datetime.now().strftime("%H:%M:%S")
        })
        
        # Check for call routing/transfer
        # We need to construct the conversation log for the routing check
        # The handler has .conversation which is a list of dicts.
        conversation_log = call_handler.conversation # passed by reference, might be partial
        # Actually we should add the current message first which call_handler.get_ai_response does.
        # But get_ai_response also calls OpenAI for response. 
        # Ideally we check routing BEFORE generating AI response, but we need the current user input in history?
        # Let's peek at routing.
        
        # We can implement a method in handler to add user message without generating response?
        # But get_ai_response does it all. 
        # Let's just generate response normally, BUT if we detect urgency we override?
        # Or check urgency on the user input solely + history?
        
        # Let's use the routing logic on the current state + new input.
        # Because we don't want to modify handler internals too much from outside which is messy.
        # But for routing we need the full text.
        
        # Let's modify the flow:
        # 1. Add user message to log (inside get_ai_response usually, but we can separate it).
        # We will refactor get_ai_response slightly or just let it handle it.
        # If we use get_ai_response, it talks to OpenAI.
        # If we want to transfer, we shouldn't talk first.
        
        # Let's check routing on user input + history locally.
        # We can just check the raw speech_result for keywords first.
        # Or call the sophisticated routing.
        
        # Since I cannot easily inject the message into handler without modifying it...
        # Wait, I wrote the handler. I can modify it if needed or just use `log_conversation` which is public.
        
        call_handler.log_conversation("Caller", speech_result)
        
        # Check routing
        should_transfer = call_routing.should_transfer_to_human(call_handler.conversation)
        
        if should_transfer:
             # Send update to dashboard
            socketio.emit('call_updated', {
                'call_sid': call_sid,
                'speaker': 'System',
                'message': "Transferring to human agent...",
                'timestamp': datetime.now().strftime("%H:%M:%S")
            })
            
            resp = VoiceResponse()
            resp.say("I understand this is urgent. Please hold while I transfer you to a human agent.")
            resp.dial(HUMAN_SUPPORT_NUMBER)
            return str(resp)

        # Get AI response
        # Note: we already logged the user input above. 
        # We need a method in handler that generates response given the history, or we use get_ai_response but tell it NOT to log user input again?
        # My implementation of get_ai_response calls log_conversation("Caller", user_input).
        # If I call it now, it will duplicate.
        # I should probably just call `get_ai_response(speech_result)` and let it do the work, 
        # AND perform the routing check *inside* it or before.
        # If I do before, I haven't added the message yet.
        
        # Let's discard the manual logging I just did above and use get_ai_response, 
        # BUT we want to check routing first.
        # It's a bit circular. 
        # I will revert looking at `call_routing.should_transfer_to_human`.
        # I will assume `get_ai_response` handles normal flow.
        # If I want routing, I should integrate it into `EnhancedCallHandler` or do it here.
        # Let's do it here properly:
        
        # 1. Update handler with user input (manually)
        # call_handler.log_conversation("Caller", speech_result)
        # 2. Check routing.
        # 3. If transfer -> return Dial.
        # 4. If no transfer -> generate AI response (but don't log user input again).
        
        # To support this, I'll update `EnhancedCallHandler` in `enhanced_call_handler.py` to have `process_turn(user_input)`?
        # Or just use `request.form.get('SpeechResult')`.
        
        # Actually, let's keep `get_ai_response` as the main entry point, 
        # and maybe add `check_transfer` method to handler?
        # No, `call_routing` is a separate module.
        
        # Let's use a cleaner approach:
        # We won't log initially. We check routing on `speech_result` + `call_handler.conversation[-5:]` (approx).
        # But `call_handler.conversation` doesn't have the current `speech_result` yet.
        # So we construct a temporary list for the check?
        
        temp_history = call_handler.conversation + [{'message': speech_result}]
        if call_routing.should_transfer_to_human(temp_history):
             call_handler.log_conversation("Caller", speech_result) # Log it finally
             call_handler.log_conversation("System", "Transferred to human")
             resp = VoiceResponse()
             resp.say("Transferring you to a human support agent.")
             resp.dial(HUMAN_SUPPORT_NUMBER)
             return str(resp)
             
        # Normal flow
        ai_response = call_handler.get_ai_response(speech_result)
        
        # Send AI response to dashboard
        socketio.emit('call_updated', {
            'call_sid': call_sid,
            'speaker': 'AI Assistant',
            'message': ai_response,
            'timestamp': datetime.now().strftime("%H:%M:%S")
        })
        
        # Create response for Twilio
        resp = VoiceResponse()
        resp.say(ai_response)
        resp.gather(input='speech', action='/webhook/voice-input', method='POST', speechTimeout='auto')
        
        return str(resp)
    
    # Fallback/Error
    resp = VoiceResponse()
    resp.say("I'm sorry, I didn't catch that. Could you please repeat?")
    resp.gather(input='speech', action='/webhook/voice-input', method='POST')
    return str(resp)

@app.route('/webhook/call-ended', methods=['POST'])
def handle_call_end():
    """Handle when call ends"""
    call_sid = request.form.get('CallSid')
    if call_sid in active_calls:
        call_handler = active_calls[call_sid]
        call_handler.save_call_log()
        del active_calls[call_sid]
        socketio.emit('call_ended', {'call_sid': call_sid})
    
    return '', 200

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
