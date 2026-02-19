import openai

def should_transfer_to_human(conversation):
    """Determine if call should be transferred to a human"""
    urgent_keywords = ['emergency', 'urgent', 'speak to human', 'real person']
    conversation_text = " ".join([msg['message'] for msg in conversation])
    
    if any(keyword in conversation_text.lower() for keyword in urgent_keywords):
        return True
    
    # Use AI to analyze sentiment/urgency
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Determine if this conversation requires human intervention. Respond with only 'YES' or 'NO'."},
                {"role": "user", "content": f"Conversation: {conversation_text}"}
            ]
        )
        return response.choices[0].message.content.strip().upper() == "YES"
    except Exception as e:
        print(f"Error checking transfer: {e}")
        return False
