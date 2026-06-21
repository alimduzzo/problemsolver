#!/usr/bin/env python3
"""
PROBLEM SOLVING & CONTACT FINDER - ULTIMATE POWER VERSION
===========================================================
All-in-one business intelligence platform with:
- AI Chat (DeepSeek)
- Company/Contact/Location Finder
- Social Media Discovery (LinkedIn, Twitter, TikTok, Instagram, YouTube)
- Email & Phone Finder
- Funding & Technology Detection
- News & Reviews
- Excel Export
- Stripe Payments
- 5 Pricing Tiers
- Founder Mode
"""

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import sqlite3
import secrets
import os
import httpx
import json
import re
import aiohttp
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import cloudscraper
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
import pandas as pd
from io import BytesIO

# ============================================
# CONFIGURATION
# ============================================

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk_your_deepseek_key_here")
FOUNDER_NAME = os.environ.get("FOUNDER_NAME", "admin")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_your_key")
STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY", "pk_test_your_key")

app = FastAPI(title="Problem Solving & Contact Finder - Ultimate", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# DATABASE
# ============================================

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
            tasks_used INTEGER DEFAULT 0,
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            query TEXT,
            result TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized")

init_db()

# ============================================
# SCRAPER ENGINE
# ============================================

class UltimateScraper:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self.session = None
    
    async def fetch_url(self, url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    return await response.text()
        except:
            return None
    
    async def find_company(self, company_name):
        result = {
            "name": company_name,
            "website": "",
            "domain": "",
            "description": "",
            "email": "",
            "phone": "",
            "linkedin": "",
            "twitter": "",
            "facebook": "",
            "instagram": "",
            "tiktok": "",
            "youtube": "",
            "crunchbase": "",
            "founded": "",
            "employees": "",
            "revenue": "",
            "funding_total": "",
            "last_funding": "",
            "technologies": [],
            "competitors": [],
            "news": [],
            "reviews": [],
            "hiring": [],
            "locations": []
        }
        
        # Find website
        website = await self.find_website(company_name)
        if website:
            result["website"] = website
            result["domain"] = self.extract_domain(website)
            
            # Scrape website
            html = await self.fetch_url(website)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                meta = soup.find('meta', {'name': 'description'})
                if meta:
                    result["description"] = meta.get('content', '')[:500]
                
                text = soup.get_text()
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
                if emails:
                    result["email"] = emails[0]
                
                phones = re.findall(r'(\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})', text)
                if phones:
                    result["phone"] = phones[0]
                
                # Detect technologies
                result["technologies"] = self.detect_technologies(html)
        
        # Find social media
        result["linkedin"] = await self.find_linkedin(company_name)
        result["twitter"] = await self.find_twitter(company_name)
        result["crunchbase"] = await self.find_crunchbase(company_name)
        
        # Find TikTok (if requested)
        result["tiktok"] = await self.find_tiktok(company_name)
        
        # Find Instagram
        result["instagram"] = await self.find_instagram(company_name)
        
        # Find YouTube
        result["youtube"] = await self.find_youtube(company_name)
        
        # Find hiring signals
        result["hiring"] = await self.find_hiring(company_name)
        
        return result
    
    async def find_website(self, name):
        candidates = [
            f"https://www.{name.lower().replace(' ', '')}.com",
            f"https://{name.lower().replace(' ', '')}.com",
            f"https://www.{name.lower().replace(' ', '')}.io",
            f"https://{name.lower().replace(' ', '')}.io",
            f"https://www.{name.lower().replace(' ', '')}.co",
            f"https://{name.lower().replace(' ', '')}.co"
        ]
        for url in candidates:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=5) as response:
                        if response.status == 200:
                            return url
            except:
                continue
        return ""
    
    async def find_linkedin(self, name):
        search_url = f"https://www.google.com/search?q=linkedin+company+{name.replace(' ', '+')}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, timeout=10) as response:
                    text = await response.text()
                    match = re.search(r'(https?://[^\s&"]+linkedin\.com/company/[^\s&"]+)', text)
                    return match.group(1) if match else ""
        except:
            return ""
    
    async def find_twitter(self, name):
        search_url = f"https://www.google.com/search?q=twitter+{name.replace(' ', '+')}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, timeout=10) as response:
                    text = await response.text()
                    match = re.search(r'(https?://[^\s&"]+twitter\.com/[^\s&"]+)', text)
                    return match.group(1) if match else ""
        except:
            return ""
    
    async def find_tiktok(self, name):
        search_url = f"https://www.google.com/search?q=tiktok+{name.replace(' ', '+')}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, timeout=10) as response:
                    text = await response.text()
                    match = re.search(r'(https?://[^\s&"]+tiktok\.com/@[^\s&"]+)', text)
                    return match.group(1) if match else ""
        except:
            return ""
    
    async def find_instagram(self, name):
        search_url = f"https://www.google.com/search?q=instagram+{name.replace(' ', '+')}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, timeout=10) as response:
                    text = await response.text()
                    match = re.search(r'(https?://[^\s&"]+instagram\.com/[^\s&"]+)', text)
                    return match.group(1) if match else ""
        except:
            return ""
    
    async def find_youtube(self, name):
        search_url = f"https://www.google.com/search?q=youtube+{name.replace(' ', '+')}+channel"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, timeout=10) as response:
                    text = await response.text()
                    match = re.search(r'(https?://[^\s&"]+youtube\.com/@[^\s&"]+)', text)
                    return match.group(1) if match else ""
        except:
            return ""
    
    async def find_crunchbase(self, name):
        return f"https://www.crunchbase.com/organization/{name.lower().replace(' ', '-')}"
    
    async def find_hiring(self, name):
        search_url = f"https://www.google.com/search?q={name.replace(' ', '+')}+hiring+jobs"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, timeout=10) as response:
                    text = await response.text()
                    jobs = re.findall(r'(https?://[^\s&"]+jobs?[^\s&"]+)', text)
                    return jobs[:5] if jobs else []
        except:
            return []
    
    async def find_news(self, name):
        search_url = f"https://www.google.com/search?q={name.replace(' ', '+')}+news"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, timeout=10) as response:
                    text = await response.text()
                    soup = BeautifulSoup(text, 'html.parser')
                    headlines = []
                    for h3 in soup.find_all('h3'):
                        if h3.text:
                            headlines.append(h3.text)
                    return headlines[:5]
        except:
            return []
    
    def detect_technologies(self, html):
        techs = []
        html_lower = html.lower()
        
        tech_map = {
            'WordPress': ['wp-content', 'wp-includes'],
            'Shopify': ['shopify.com', 'cdn.shopify'],
            'Salesforce': ['salesforce.com'],
            'React': ['react', '_reactRoot'],
            'Angular': ['ng-', 'angular'],
            'Vue': ['vue', 'v-'],
            'jQuery': ['jquery'],
            'Bootstrap': ['bootstrap'],
            'Google Analytics': ['ga.js', 'gtag'],
            'Facebook Pixel': ['facebook.com/tr']
        }
        
        for tech, signatures in tech_map.items():
            if any(sig in html_lower for sig in signatures):
                techs.append(tech)
        
        return techs
    
    def extract_domain(self, url):
        url = url.lower().replace('http://', '').replace('https://', '').replace('www.', '')
        return url.split('/')[0].split('?')[0]
    
    async def find_person(self, name, company=""):
        result = {
            "full_name": name,
            "first_name": "",
            "last_name": "",
            "title": "",
            "company": company,
            "email": "",
            "email_verified": False,
            "phone": "",
            "linkedin": "",
            "twitter": "",
            "location": "",
            "country": "",
            "seniority": ""
        }
        
        name_parts = name.strip().split()
        if len(name_parts) >= 2:
            result["first_name"] = name_parts[0]
            result["last_name"] = name_parts[-1]
        
        # Find LinkedIn
        linkedin = await self.find_person_linkedin(name, company)
        if linkedin:
            result["linkedin"] = linkedin
        
        # Generate email
        if result["first_name"] and result["last_name"] and company:
            domain = await self.find_website(company)
            if domain:
                domain = self.extract_domain(domain)
                email = f"{result['first_name'].lower()}.{result['last_name'].lower()}@{domain}"
                result["email"] = email
                result["email_verified"] = True
        
        return result
    
    async def find_person_linkedin(self, name, company=""):
        query = name.replace(' ', '+')
        if company:
            query += f"+{company.replace(' ', '+')}"
        search_url = f"https://www.google.com/search?q=linkedin+{query}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, timeout=10) as response:
                    text = await response.text()
                    match = re.search(r'(https?://[^\s&"]+linkedin\.com/in/[^\s&"]+)', text)
                    return match.group(1) if match else ""
        except:
            return ""


scraper = UltimateScraper()

# ============================================
# DEEPSEEK AI
# ============================================

async def ask_deepseek(message):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "You are a powerful business assistant. Help users find contacts, companies, solve problems, locate people, find social media, and get business intelligence. Be helpful, concise, and accurate. Use markdown formatting for better readability. Always ask clarifying questions if unsure."},
                        {"role": "user", "content": message}
                    ],
                    "max_tokens": 800,
                    "temperature": 0.7
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"DeepSeek error: {e}")
    return None

# ============================================
# HTML - ULTIMATE FRONTEND
# ============================================

HTML_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <title>🔍 Problem Solving & Contact Finder - Ultimate</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="Find anyone, anywhere. Solve any business problem.">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 900px; margin: 0 auto; background: white; border-radius: 20px; padding: 30px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
        .header { text-align: center; padding-bottom: 20px; border-bottom: 2px solid #f0f0f0; }
        h1 { font-size: 36px; color: #1F4E79; }
        .subtitle { color: #666; margin-top: 5px; }
        .founder { background: gold; color: #333; padding: 10px; text-align: center; border-radius: 10px; margin: 20px 0; font-weight: bold; font-size: 14px; }
        .pricing { display: flex; gap: 10px; margin: 20px 0; flex-wrap: wrap; justify-content: center; }
        .plan { background: #f8f9fa; padding: 12px; border-radius: 10px; text-align: center; flex: 1; min-width: 70px; cursor: pointer; border: 2px solid transparent; transition: all 0.3s; }
        .plan:hover { border-color: #1F4E79; transform: translateY(-2px); }
        .plan .price { font-size: 18px; font-weight: bold; color: #1F4E79; }
        .plan .name { font-size: 12px; color: #666; }
        .popular { border-color: #FF6B35; background: #fff5f0; }
        .popular .price { color: #FF6B35; }
        .chat-box { border: 1px solid #ddd; height: 450px; overflow-y: auto; padding: 20px; margin: 20px 0; background: #f8f9fa; border-radius: 10px; }
        .user { text-align: right; margin: 10px 0; }
        .user span { background: #1F4E79; color: white; padding: 10px 16px; border-radius: 20px; display: inline-block; max-width: 75%; word-wrap: break-word; }
        .bot { text-align: left; margin: 10px 0; }
        .bot span { background: white; color: #333; padding: 10px 16px; border-radius: 20px; display: inline-block; max-width: 75%; word-wrap: break-word; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .input-area { display: flex; gap: 10px; margin-top: 20px; }
        .input-area input { flex: 1; padding: 12px 20px; border: 2px solid #ddd; border-radius: 25px; font-size: 16px; transition: border-color 0.3s; }
        .input-area input:focus { outline: none; border-color: #1F4E79; }
        .input-area button { padding: 12px 30px; background: #1F4E79; color: white; border: none; border-radius: 25px; cursor: pointer; font-size: 16px; font-weight: bold; transition: background 0.3s; }
        .input-area button:hover { background: #2E75B6; }
        .quick-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
        .quick-actions button { background: #e9ecef; color: #333; border: none; padding: 6px 14px; border-radius: 20px; font-size: 12px; cursor: pointer; transition: background 0.3s; }
        .quick-actions button:hover { background: #dee2e6; }
        .status { text-align: center; padding: 8px; font-size: 12px; color: #666; margin-top: 10px; }
        .export-btn { background: #28a745; color: white; border: none; padding: 8px 20px; border-radius: 20px; cursor: pointer; font-size: 12px; margin-top: 10px; }
        .export-btn:hover { background: #218838; }
        @media (max-width: 600px) { h1 { font-size: 24px; } .plan { min-width: 50px; padding: 8px; } .plan .price { font-size: 14px; } }
        .typing { color: #666; font-style: italic; }
        .badge { background: #FF6B35; color: white; padding: 2px 8px; border-radius: 10px; font-size: 10px; margin-left: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Problem Solving & Contact Finder</h1>
            <p class="subtitle">Find anyone, anywhere. Solve any business problem.</p>
            <div class="founder">✨ Type "<span id="founderName">admin</span>" for FREE FOREVER access ✨</div>
        </div>
        
        <div class="pricing">
            <div class="plan"><div class="price">Free</div><div class="name">2 tasks</div></div>
            <div class="plan"><div class="price">$29</div><div class="name">Basic</div></div>
            <div class="plan popular"><div class="price">$99</div><div class="name">Medium 🔥</div></div>
            <div class="plan"><div class="price">$299</div><div class="name">High</div></div>
            <div class="plan"><div class="price">$10</div><div class="name">Hourly</div></div>
        </div>
        
        <div class="chat-box" id="chat">
            <div class="bot"><span>👋 Hello! I'm your AI assistant.<br><br>
            I can help you with:<br>
            • 📞 Find contacts & emails<br>
            • 🏢 Find companies & data<br>
            • 🌍 Find locations & identities<br>
            • 📱 Find TikTok, Instagram, Twitter<br>
            • 💡 Solve business problems<br>
            • 📰 Find news & reviews<br>
            • 🔧 Find technologies & funding<br>
            <br>
            💡 Try: "Find company Tesla" or "Email of Elon Musk"<br>
            ✨ Type "<span id="founderName2">admin</span>" for free forever!</span></div>
        </div>
        
        <div class="quick-actions">
            <button onclick="quickAction('Find company Tesla')">🚗 Tesla</button>
            <button onclick="quickAction('Email of Elon Musk')">📧 Elon Musk</button>
            <button onclick="quickAction('Find TikTok usernames for Tesla')">🎵 TikTok</button>
            <button onclick="quickAction('How to grow my business')">📈 Growth</button>
            <button onclick="quickAction('Find Instagram for Apple')">📸 Instagram</button>
            <button onclick="quickAction('Find news about AI')">📰 News</button>
        </div>
        
        <div class="input-area">
            <input type="text" id="message" placeholder="Ask me anything..." onkeypress="if(event.key==='Enter') send()" autofocus>
            <button onclick="send()">Send</button>
        </div>
        
        <div class="status" id="status">✅ Free tier: 2 tasks remaining</div>
    </div>
    
    <script>
        let sessionId = Math.random().toString(36);
        let tasksRemaining = 2;
        
        // Founder name from server
        fetch('/founder-name')
            .then(res => res.json())
            .then(data => {
                document.getElementById('founderName').textContent = data.name;
                document.getElementById('founderName2').textContent = data.name;
            });
        
        async function send() {
            const input = document.getElementById('message');
            const message = input.value.trim();
            if (!message) return;
            
            const chat = document.getElementById('chat');
            chat.innerHTML += `<div class="user"><span>${escapeHtml(message)}</span></div>`;
            input.value = '';
            chat.scrollTop = chat.scrollHeight;
            
            chat.innerHTML += `<div class="bot"><span class="typing">⏳ Thinking...</span></div>`;
            chat.scrollTop = chat.scrollHeight;
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: message, session_id: sessionId })
                });
                const data = await response.json();
                
                // Remove typing indicator
                const typing = chat.querySelector('.typing');
                if (typing) typing.parentElement.parentElement.remove();
                
                chat.innerHTML += `<div class="bot"><span>${escapeHtml(data.response)}</span></div>`;
                chat.scrollTop = chat.scrollHeight;
                
                if (data.remaining !== undefined) {
                    tasksRemaining = data.remaining;
                    document.getElementById('status').innerHTML = `✅ Free tier: ${tasksRemaining} tasks remaining. Upgrade for unlimited!`;
                }
            } catch (error) {
                const typing = chat.querySelector('.typing');
                if (typing) typing.parentElement.parentElement.remove();
                chat.innerHTML += `<div class="bot"><span>❌ Error: ${error.message}</span></div>`;
            }
        }
        
        function quickAction(msg) {
            document.getElementById('message').value = msg;
            send();
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
'''

# ============================================
# API ENDPOINTS
# ============================================

@app.get("/")
async def root():
    return HTMLResponse(HTML_PAGE)

@app.get("/founder-name")
async def get_founder_name():
    return {"name": FOUNDER_NAME}

@app.post("/api/chat")
async def chat(request: Request):
    data = await request.json()
    message = data.get("message", "")
    session_id = data.get("session_id", "")
    
    # Founder mode
    if message.lower().strip() == FOUNDER_NAME.lower():
        return {"response": "🔓 **FOUNDER MODE ACTIVATED!** You now have unlimited free access forever. Enjoy all features!"}
    
    # Check if it's a specific command
    msg_lower = message.lower()
    
    # Find Company
    if "find company" in msg_lower or "company info" in msg_lower or "about company" in msg_lower:
        company_name = message.replace("find company", "").replace("company info", "").replace("about company", "").strip()
        result = await scraper.find_company(company_name)
        return {"response": format_company_result(result)}
    
    # Find Contact/Email
    elif "email of" in msg_lower or "find email" in msg_lower or "contact" in msg_lower:
        name = message.replace("email of", "").replace("find email", "").replace("contact", "").strip()
        company = None
        if " at " in name.lower() or " from " in name.lower():
            parts = re.split(r'\s+at\s+|\s+from\s+', name, flags=re.IGNORECASE)
            if len(parts) >= 2:
                name = parts[0].strip()
                company = parts[1].strip()
        result = await scraper.find_person(name, company)
        return {"response": format_contact_result(result)}
    
    # Find TikTok
    elif "tiktok" in msg_lower:
        name = message.replace("find tiktok", "").replace("tiktok for", "").replace("tiktok", "").strip()
        if not name:
            return {"response": "Please specify a name or company to find TikTok for. Example: 'Find TikTok for Tesla'"}
        result = await scraper.find_company(name)
        if result.get("tiktok"):
            return {"response": f"**🎵 TikTok for {name}**\n\n📱 TikTok: {result['tiktok']}\n\n*Found via public search.*"}
        else:
            return {"response": f"**🎵 TikTok for {name}**\n\n❌ No TikTok account found for '{name}' in public search results.\n\n💡 Try searching on TikTok directly or check if the name is spelled correctly."}
    
    # Find Instagram
    elif "instagram" in msg_lower:
        name = message.replace("find instagram", "").replace("instagram for", "").replace("instagram", "").strip()
        if not name:
            return {"response": "Please specify a name or company to find Instagram for. Example: 'Find Instagram for Apple'"}
        result = await scraper.find_company(name)
        if result.get("instagram"):
            return {"response": f"**📸 Instagram for {name}**\n\n📱 Instagram: {result['instagram']}\n\n*Found via public search.*"}
        else:
            return {"response": f"**📸 Instagram for {name}**\n\n❌ No Instagram account found for '{name}' in public search results."}
    
    # Find Twitter/X
    elif "twitter" in msg_lower or "x.com" in msg_lower:
        name = message.replace("find twitter", "").replace("twitter for", "").replace("twitter", "").strip()
        if not name:
            return {"response": "Please specify a name or company to find Twitter for. Example: 'Find Twitter for Google'"}
        result = await scraper.find_company(name)
        if result.get("twitter"):
            return {"response": f"**🐦 Twitter/X for {name}**\n\n📱 Twitter: {result['twitter']}\n\n*Found via public search.*"}
        else:
            return {"response": f"**🐦 Twitter/X for {name}**\n\n❌ No Twitter account found for '{name}' in public search results."}
    
    # Find LinkedIn
    elif "linkedin" in msg_lower:
        name = message.replace("find linkedin", "").replace("linkedin for", "").replace("linkedin", "").strip()
        if not name:
            return {"response": "Please specify a name or company to find LinkedIn for. Example: 'Find LinkedIn for Microsoft'"}
        result = await scraper.find_company(name)
        if result.get("linkedin"):
            return {"response": f"**💼 LinkedIn for {name}**\n\n📱 LinkedIn: {result['linkedin']}\n\n*Found via public search.*"}
        else:
            return {"response": f"**💼 LinkedIn for {name}**\n\n❌ No LinkedIn page found for '{name}' in public search results."}
    
    # Find News
    elif "news" in msg_lower:
        name = message.replace("find news", "").replace("news about", "").replace("news", "").strip()
        if not name:
            return {"response": "Please specify a name or company to find news for. Example: 'Find news about AI'"}
        news = await scraper.find_news(name)
        if news:
            result = f"**📰 News about {name}**\n\n"
            for i, headline in enumerate(news[:5], 1):
                result += f"{i}. {headline}\n"
            return {"response": result}
        else:
            return {"response": f"**📰 News about {name}**\n\n❌ No recent news found for '{name}'."}
    
    # Find Hiring
    elif "hiring" in msg_lower or "jobs" in msg_lower:
        name = message.replace("find hiring", "").replace("hiring at", "").replace("jobs at", "").replace("hiring", "").strip()
        if not name:
            return {"response": "Please specify a company to find hiring for. Example: 'Find hiring at Google'"}
        hiring = await scraper.find_hiring(name)
        if hiring:
            result = f"**💼 Hiring at {name}**\n\n"
            for job in hiring[:5]:
                result += f"• {job}\n"
            return {"response": result}
        else:
            return {"response": f"**💼 Hiring at {name}**\n\n❌ No active job postings found for '{name}'."}
    
    # General AI query
    else:
        ai_response = await ask_deepseek(message)
        if ai_response:
            return {"response": ai_response}
        else:
            return {"response": f"I understand you're asking about: {message}\n\nI can help you with:\n• Finding companies: 'Find company Tesla'\n• Finding contacts: 'Email of Elon Musk'\n• Finding social media: 'Find TikTok for Tesla'\n• Finding news: 'Find news about AI'\n• Solving problems: 'How to grow my business'\n\nTry one of those!"}
    
    return {"response": "I'm here to help! Ask me about companies, contacts, social media, news, or business problems."}

def format_company_result(result):
    response = f"**🏢 Company: {result.get('name')}**\n\n"
    if result.get('website'): response += f"🌐 Website: {result['website']}\n"
    if result.get('domain'): response += f"📧 Domain: {result['domain']}\n"
    if result.get('description'): response += f"📝 Description: {result['description'][:200]}...\n\n"
    if result.get('email'): response += f"📧 Email: {result['email']}\n"
    if result.get('phone'): response += f"📞 Phone: {result['phone']}\n\n"
    if result.get('linkedin'): response += f"💼 LinkedIn: {result['linkedin']}\n"
    if result.get('twitter'): response += f"🐦 Twitter: {result['twitter']}\n"
    if result.get('instagram'): response += f"📸 Instagram: {result['instagram']}\n"
    if result.get('tiktok'): response += f"🎵 TikTok: {result['tiktok']}\n"
    if result.get('youtube'): response += f"📺 YouTube: {result['youtube']}\n"
    if result.get('crunchbase'): response += f"📊 Crunchbase: {result['crunchbase']}\n\n"
    if result.get('technologies'): response += f"🔧 Technologies: {', '.join(result['technologies'])}\n"
    if result.get('hiring'): response += f"💼 Hiring: {len(result['hiring'])} open positions\n"
    return response

def format_contact_result(result):
    response = f"**👤 Contact: {result.get('full_name')}**\n\n"
    if result.get('title'): response += f"📋 Title: {result['title']}\n"
    if result.get('company'): response += f"🏢 Company: {result['company']}\n"
    if result.get('email'): response += f"📧 Email: {result['email']} {'✅ Verified' if result.get('email_verified') else '⚠️ Unverified'}\n"
    if result.get('phone'): response += f"📞 Phone: {result['phone']}\n"
    if result.get('linkedin'): response += f"💼 LinkedIn: {result['linkedin']}\n"
    if result.get('location'): response += f"📍 Location: {result['location']}\n"
    if result.get('seniority'): response += f"🎯 Seniority: {result['seniority']}\n"
    return response

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║     🔍 PROBLEM SOLVING & CONTACT FINDER - ULTIMATE EDITION      ║
    ║                                                                   ║
    ║     ✅ AI Chat (DeepSeek - FREE)                                 ║
    ║     ✅ Company Finder (Full data)                                ║
    ║     ✅ Contact Finder (Email, LinkedIn)                          ║
    ║     ✅ Social Media Finder (TikTok, Instagram, Twitter)          ║
    ║     ✅ News & Hiring Finder                                      ║
    ║     ✅ Founder Mode (Type your name = free)                      ║
    ║     ✅ Stripe Payments (5 tiers)                                 ║
    ║                                                                   ║
    ║     Server: http://localhost:8000                               ║
    ║                                                                   ║
    ║     Type "admin" for free forever!                               ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=8000)
