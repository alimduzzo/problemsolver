#!/usr/bin/env python3
"""
PROBLEM SOLVING & CONTACT FINDER - SQLITE VERSION
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn
import openai
import sqlite3
import secrets
from datetime import datetime, timedelta
import os

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "sk_your_key_here")
FOUNDER_NAME = os.environ.get("FOUNDER_NAME", "admin")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_your_key")
STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY", "pk_test_your_key")

openai.api_key = OPENAI_API_KEY

app = FastAPI()

# Database
def init_db():
    conn = sqlite3.connect('problemsolver.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE,
            name TEXT,
            tier TEXT DEFAULT 'free',
            founder_mode BOOLEAN DEFAULT FALSE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hourly_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            session_key TEXT UNIQUE,
            expires_at TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized")

init_db()

# HTML
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Problem Solving & Contact Finder</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: white; border-radius: 20px; padding: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); }
        h1 { color: #1F4E79; text-align: center; margin-bottom: 10px; }
        .founder { background: gold; color: black; padding: 10px; text-align: center; border-radius: 10px; margin: 20px 0; font-weight: bold; }
        .chat-box { border: 1px solid #ddd; height: 400px; overflow-y: auto; padding: 20px; margin: 20px 0; background: #f9f9f9; border-radius: 10px; }
        .user { text-align: right; margin: 10px; }
        .user span { background: #1F4E79; color: white; padding: 10px 15px; border-radius: 20px; display: inline-block; max-width: 70%; }
        .bot { text-align: left; margin: 10px; }
        .bot span { background: #e0e0e0; color: #333; padding: 10px 15px; border-radius: 20px; display: inline-block; max-width: 70%; }
        .input-area { display: flex; gap: 10px; margin-top: 20px; }
        input { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 25px; font-size: 16px; }
        button { padding: 12px 24px; background: #1F4E79; color: white; border: none; border-radius: 25px; cursor: pointer; font-size: 16px; }
        button:hover { background: #2E75B6; }
        .pricing { display: flex; gap: 10px; margin: 20px 0; flex-wrap: wrap; justify-content: center; }
        .plan { background: #f0f0f0; padding: 10px; border-radius: 10px; text-align: center; flex: 1; min-width: 80px; cursor: pointer; }
        .plan:hover { background: #e0e0e0; }
        .price { font-size: 18px; font-weight: bold; color: #1F4E79; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Problem Solving & Contact Finder</h1>
        <div class="founder">✨ Type "admin" for FREE FOREVER access ✨</div>
        
        <div class="pricing">
            <div class="plan" onclick="alert('Free: 2 tasks')"><div class="price">Free</div>2 tasks</div>
            <div class="plan" onclick="alert('Basic $29/mo: 500 lookups')"><div class="price">$29</div>Basic</div>
            <div class="plan" onclick="alert('Medium $99/mo: 2000 lookups')"><div class="price">$99</div>Medium</div>
            <div class="plan" onclick="alert('High $299/mo: Unlimited')"><div class="price">$299</div>High</div>
            <div class="plan" onclick="alert('Hourly $10: 1 hour')"><div class="price">$10</div>Hourly</div>
        </div>
        
        <div class="chat-box" id="chat">
            <div class="bot"><span>👋 Hello! I can find contacts, companies, and solve problems.<br>💡 Try: "Find company Tesla" or "Email of Elon Musk"<br>✨ Type "admin" for free forever!</span></div>
        </div>
        
        <div class="input-area">
            <input type="text" id="message" placeholder="Type your question here..." onkeypress="if(event.key==='Enter') send()">
            <button onclick="send()">Send</button>
        </div>
    </div>
    
    <script>
        let sessionId = Math.random().toString(36);
        
        async function send() {
            const input = document.getElementById('message');
            const message = input.value.trim();
            if (!message) return;
            
            const chat = document.getElementById('chat');
            chat.innerHTML += `<div class="user"><span>${escapeHtml(message)}</span></div>`;
            input.value = '';
            chat.scrollTop = chat.scrollHeight;
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: message, session_id: sessionId })
                });
                const data = await response.json();
                chat.innerHTML += `<div class="bot"><span>${escapeHtml(data.response)}</span></div>`;
                chat.scrollTop = chat.scrollHeight;
            } catch (error) {
                chat.innerHTML += `<div class="bot"><span>❌ Error: ${error.message}</span></div>`;
            }
        }
        
        function escapeHtml(text) {
            return text.replace(/[&<>]/g, function(m) {
                if (m === '&') return '&amp;';
                if (m === '<') return '&lt;';
                if (m === '>') return '&gt;';
                return m;
            });
        }
    </script>
</body>
</html>
"""

@app.get("/")
async def root():
    return HTMLResponse(HTML_PAGE)

@app.post("/api/chat")
async def chat(request: Request):
    data = await request.json()
    message = data.get("message", "")
    
    if message.lower().strip() == FOUNDER_NAME.lower():
        return {"response": "🔓 FOUNDER MODE ACTIVATED! You now have unlimited free access forever."}
    
    msg_lower = message.lower()
    
    if "find company" in msg_lower or "company" in msg_lower:
        company = message.replace("find company", "").replace("company", "").strip()
        return {"response": f"**🏢 Company: {company}**\n\nI'm searching for {company}...\n\n📧 Email: contact@{company.lower().replace(' ', '')}.com\n🌐 Website: www.{company.lower().replace(' ', '')}.com\n💼 LinkedIn: linkedin.com/company/{company.lower().replace(' ', '-')}\n\n*Upgrade to Pro for complete company data including funding, technologies, and decision makers.*"}
    
    elif "email of" in msg_lower or "find email" in msg_lower or "contact" in msg_lower:
        name = message.replace("email of", "").replace("find email", "").replace("contact", "").strip()
        return {"response": f"**👤 Contact: {name}**\n\n📧 Email: {name.lower().replace(' ', '.')}@example.com\n🔗 LinkedIn: linkedin.com/in/{name.lower().replace(' ', '-')}\n\n*Upgrade to Pro for verified emails and phone numbers.*"}
    
    elif "how to" in msg_lower or "solve" in msg_lower or "problem" in msg_lower:
        return {"response": f"**📝 Problem Solving Advice:**\n\n1. Break down the problem into smaller parts\n2. Identify the root cause\n3. Research existing solutions\n4. Test small before scaling\n5. Measure results and iterate\n\n*Need specific help? Tell me more details and I'll assist further.*"}
    
    else:
        if OPENAI_API_KEY and OPENAI_API_KEY != "sk_your_key_here":
            try:
                import openai
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": message}],
                    max_tokens=300
                )
                return {"response": response.choices[0].message.content}
            except:
                pass
        
        return {"response": f"I understand you're asking about: {message}\n\nI can help you with:\n• Finding company information\n• Finding contact emails\n• Solving business problems\n\nTry: 'Find company Tesla' or 'Email of John Smith' or 'How to grow my business'"}
    
    return {"response": "I'm here to help! Ask me about companies, contacts, or business problems."}

if __name__ == "__main__":
    print("Server running at http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
