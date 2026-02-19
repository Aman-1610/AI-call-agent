from datetime import datetime
import json
import sqlite3
import openai

class EnhancedCallHandler:
    def __init__(self, call_sid, from_number):
        self.call_sid = call_sid
        self.from_number = from_number
        self.start_time = datetime.now()
        # self.conversation stores the log with timestamps
        self.conversation = [] 
        self.system_prompt = """You are a helpful AI assistant answering phone calls on behalf of your owner. 
            Be polite, professional, and try to handle the caller's request. If you need to take a message, 
            ask for their name, contact information, and the purpose of the call. Keep responses concise for phone conversation."""
        self.call_status = "active"
        self.setup_database()
    
    def setup_database(self):
        """Initialize SQLite database for call logs"""
        # check_same_thread=False is needed if multiple threads access the same connection, 
        # but here each handler instance might be in a thread. 
        # It is safer to create a fresh connection per request or use a pool, 
        # but for this class, we can just open one.
        # However, SQLite in Flask with threads can be tricky. 
        # We'll use check_same_thread=False as suggested by user.
        self.conn = sqlite3.connect('call_logs.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS call_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_sid TEXT UNIQUE,
                from_number TEXT,
                start_time TEXT,
                end_time TEXT,
                conversation TEXT,
                summary TEXT
            )
        ''')
        self.conn.commit()
    
    def log_conversation(self, speaker, message):
        """Log each conversation turn"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.conversation.append({
            'timestamp': timestamp,
            'speaker': speaker,
            'message': message
        })
    
    def get_openai_messages(self):
        """Convert conversation log to OpenAI message format"""
        messages = [{"role": "system", "content": self.system_prompt}]
        for msg in self.conversation:
            role = "user" if msg['speaker'] == "Caller" else "assistant"
            messages.append({"role": role, "content": msg['message']})
        # Keep only last 10 messages context + system prompt
        if len(messages) > 11:
            messages = [messages[0]] + messages[-10:]
        return messages

    def get_ai_response(self, user_input):
        """Get AI response for the conversation"""
        # Log user input
        self.log_conversation("Caller", user_input)
        
        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=self.get_openai_messages(),
                max_tokens=150,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content
            # Log AI response
            self.log_conversation("AI Assistant", ai_response)
            
            return ai_response
            
        except Exception as e:
            print(f"Error calling OpenAI: {e}")
            return "I apologize, but I'm having trouble processing your request right now. Please try again later."

    def save_call_log(self):
        """Save the complete call log to database"""
        conversation_json = json.dumps(self.conversation)
        
        # Generate AI summary of the call
        summary = self.generate_call_summary()
        
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO call_logs 
                (call_sid, from_number, start_time, end_time, conversation, summary)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (self.call_sid, self.from_number, self.start_time.isoformat(),
                datetime.now().isoformat(), conversation_json, summary))
            self.conn.commit()
        except Exception as e:
            print(f"Error saving log: {e}")
    
    def generate_call_summary(self):
        """Generate AI summary of the call"""
        if not self.conversation:
            return "No conversation recorded"
        
        conversation_text = "\n".join([
            f"{msg['speaker']} ({msg['timestamp']}): {msg['message']}"
            for msg in self.conversation
        ])
        
        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Summarize this phone conversation concisely. Include key points, caller's purpose, and any action items."},
                    {"role": "user", "content": conversation_text}
                ],
                max_tokens=200
            )
            return response.choices[0].message.content
        except:
            return "Summary unavailable"
