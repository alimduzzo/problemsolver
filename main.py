#!/usr/bin/env python3
"""
PROBLEM SOLVING & CONTACT FINDER - COMPLETE PLATFORM
All-in-one AI-powered tool for contact finding, problem solving, location lookup
PAYMENT TIERS: Free (2 tasks), Basic ($29/mo), Medium ($99/mo), High ($299/mo), Hourly ($10)
DEPLOYMENT: Ready for Render.com with PostgreSQL
"""

import asyncio
import aiohttp
import pandas as pd
from bs4 import BeautifulSoup
import cloudscraper
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
import secrets
import re
import json
import logging
from pathlib import Path
from fake_useragent import UserAgent
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import openai
import stripe
from fastapi import FastAPI, Depends, HTTPException, Header, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, EmailStr, Field
import uvicorn
from contextlib import asynccontextmanager
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import bcrypt
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
import dns.resolver
from email_validator import validate_email

# ============================================
# CONFIGURATION
# ============================================

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/problemsolver")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_your_key")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_your_key")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "sk_your_key")
FOUNDER_NAME = os.environ.get("FOUNDER_NAME", "admin")

openai.api_key = OPENAI_API_KEY
stripe.api_key = STRIPE_SECRET_KEY

# ============================================
# PRICING TIERS
# ============================================

PRICING = {
    "free": {"price": 0, "price_id": None, "tasks_limit": 2, "lookups_limit": 2, "ai_chat": False, "location_finder": False, "api_access": False},
    "basic": {"price": 29, "price_id": "price_basic_monthly", "tasks_limit": 500, "lookups_limit": 500, "ai_chat": True, "location_finder": False, "api_access": False},
    "medium": {"price": 99, "price_id": "price_medium_monthly", "tasks_limit": 2000, "lookups_limit": 2000, "ai_chat": True, "location_finder": True, "api_access": False},
    "high": {"price": 299, "price_id": "price_high_monthly", "tasks_limit": 999999, "lookups_limit": 999999, "ai_chat": True, "location_finder": True, "api_access": True, "api_limit": 10000}
}

# ============================================
# LOGGING & RATE LIMITING
# ============================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

# ============================================
# DATABASE
# ============================================

class Database:
    def __init__(self):
        self.conn = None
    
    def get_connection(self):
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(DATABASE_URL)
        return self.conn
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                password_hash TEXT NOT NULL,
                phone TEXT,
                tier TEXT DEFAULT 'free',
                subscription_status TEXT DEFAULT 'active',
                stripe_customer_id TEXT,
                subscription_end_date TIMESTAMP,
                founder_mode BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                api_key TEXT UNIQUE NOT NULL,
                tier TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                date DATE NOT NULL,
                count INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hourly_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_key TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_id TEXT,
                question TEXT,
                answer TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        cursor.close()
        logger.info("Database initialized")
    
    def get_user(self, user_id=None, email=None, api_key=None):
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        if user_id:
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        elif email:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        elif api_key:
            cursor.execute("SELECT u.* FROM users u JOIN api_keys ak ON u.id = ak.user_id WHERE ak.api_key = %s", (api_key,))
        else:
            return None
        
        row = cursor.fetchone()
        cursor.close()
        return dict(row) if row else None
    
    def create_user(self, user_id, email, password_hash, name=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (id, email, name, password_hash) VALUES (%s, %s, %s, %s)", (user_id, email, name, password_hash))
            conn.commit()
            return True
        except:
            conn.rollback()
            return False
        finally:
            cursor.close()
    
    def update_user_tier(self, user_id, tier, subscription_end_date=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET tier = %s, subscription_end_date = %s WHERE id = %s", (tier, subscription_end_date, user_id))
        conn.commit()
        cursor.close()
    
    def set_founder_mode(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET founder_mode = TRUE, tier = 'high' WHERE id = %s", (user_id,))
        conn.commit()
        cursor.close()
    
    def create_api_key(self, user_id, tier):
        api_key = f"ps_{secrets.token_urlsafe(32)}"
        api_key_id = secrets.token_urlsafe(16)
        expires_at = datetime.now() + timedelta(days=365)
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO api_keys (id, user_id, api_key, tier, expires_at) VALUES (%s, %s, %s, %s, %s)", (api_key_id, user_id, api_key, tier, expires_at))
        conn.commit()
        cursor.close()
        return api_key
    
    def create_hourly_session(self, user_id):
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=1)
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO hourly_sessions (id, user_id, session_key, expires_at) VALUES (%s, %s, %s, %s)", (secrets.token_urlsafe(16), user_id, session_id, expires_at))
        conn.commit()
        cursor.close()
        return session_id, expires_at
    
    def check_hourly_session(self, session_key):
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM hourly_sessions WHERE session_key = %s AND expires_at > NOW()", (session_key,))
        row = cursor.fetchone()
        cursor.close()
        return dict(row) if row else None
    
    def check_usage(self, user_id, action_type, date=None):
        if date is None:
            date = datetime.now().date()
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(count) FROM usage WHERE user_id = %s AND action_type = %s AND date = %s", (user_id, action_type, date))
        result = cursor.fetchone()[0]
        cursor.close()
        return result or 0
    
    def increment_usage(self, user_id, action_type):
        date = datetime.now().date()
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO usage (user_id, action_type, date, count) VALUES (%s, %s, %s, 1) ON CONFLICT (user_id, action_type, date) DO UPDATE SET count = usage.count + 1", (user_id, action_type, date))
        conn.commit()
        cursor.close()
    
    def save_chat(self, user_id, question, answer, session_id=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_history (user_id, session_id, question, answer) VALUES (%s, %s, %s, %s)", (user_id, session_id, question, answer))
        conn.commit()
        cursor.close()

db = Database()

# ============================================
# SECURITY HELPERS
# ============================================

def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# ============================================
# DATA MODELS
# ============================================

@dataclass
class CompanyData:
    company_name: str = ""
    website: str = ""
    domain: str = ""
    industry: str = ""
    description: str = ""
    phone: str = ""
    email: str = ""
    technologies: List[str] = field(default_factory=list)
    linkedin_url: str = ""
    data_quality_score: int = 0

@dataclass
class ContactData:
    full_name: str = ""
    first_name: str = ""
    last_name: str = ""
    title: str = ""
    company: str = ""
    company_domain: str = ""
    email: str = ""
    email_verified: bool = False
    linkedin_url: str = ""
    confidence_score: int = 0

# ============================================
# PYDANTIC MODELS
# ============================================

class UserRegister(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    hourly_key: Optional[str] = None

class CompanyRequest(BaseModel):
    company_name: str

class ContactRequest(BaseModel):
    name: str
    company: Optional[str] = None

# ============================================
# WEB SCRAPER ENGINE
# ============================================

class WebScraper:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self.ua = UserAgent()
        self.phone_pattern = re.compile(r'(\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})')
    
    async def find_company(self, company_name):
        company = CompanyData(company_name=company_name)
        company.website = await self._find_website(company_name)
        if company.website:
            company.domain = self._extract_domain(company.website)
            website_data = await self._scrape_website(company.website)
            company.description = website_data.get('description', '')
            company.phone = website_data.get('phone', '')
            company.email = website_data.get('email', '')
            company.technologies = await self._detect_technologies(company.website)
        company.linkedin_url = await self._find_linkedin(company_name)
        company.data_quality_score = self._calculate_score(company)
        return company
    
    async def find_person(self, name, company=None):
        contact = ContactData(full_name=name)
        name_parts = name.strip().split()
        if len(name_parts) >= 2:
            contact.first_name = name_parts[0]
            contact.last_name = name_parts[-1]
        if company:
            contact.company = company
            contact.company_domain = await self._get_domain_from_company(company)
            if contact.first_name and contact.last_name and contact.company_domain:
                contact.email = await self._generate_email(contact.first_name, contact.last_name, contact.company_domain)
                if contact.email:
                    contact.email_verified = await self._verify_email(contact.email)
        contact.linkedin_url = await self._find_person_linkedin(name, company)
        contact.confidence_score = 70
        return contact
    
    async def find_location(self, name, company=None):
        location_data = {"name": name, "country": "", "source": ""}
        linkedin_url = await self._find_person_linkedin(name, company)
        if linkedin_url:
            location_data["source"] = "LinkedIn"
        return location_data
    
    async def _find_website(self, company_name):
        candidates = [f"https://www.{company_name.lower().replace(' ', '')}.com", f"https://{company_name.lower().replace(' ', '')}.com"]
        for url in candidates:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=5) as response:
                        if response.status == 200:
                            return url
            except:
                continue
        return ""
    
    async def _scrape_website(self, url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    data = {'description': '', 'phone': '', 'email': ''}
                    meta = soup.find('meta', {'name': 'description'})
                    if meta:
                        data['description'] = meta.get('content', '')[:500]
                    text = soup.get_text()
                    phones = self.phone_pattern.findall(text)
                    if phones:
                        data['phone'] = phones[0]
                    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
                    if emails:
                        data['email'] = emails[0]
                    return data
        except:
            return {}
    
    async def _detect_technologies(self, url):
        technologies = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    html = (await response.text()).lower()
                    tech_map = {'WordPress': ['wp-content'], 'Shopify': ['shopify.com'], 'React': ['react'], 'Angular': ['ng-']}
                    for tech, sigs in tech_map.items():
                        if any(sig in html for sig in sigs):
                            technologies.append(tech)
        except:
            pass
        return technologies
    
    async def _find_linkedin(self, company_name):
        search_url = f"https://www.google.com/search?q=linkedin+company+{company_name.replace(' ', '+')}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url) as response:
                    text = await response.text()
                    for line in text.split('\n'):
                        if 'linkedin.com/company/' in line:
                            match = re.search(r'(https?://[^\s&"]+linkedin\.com/company/[^\s&"]+)', line)
                            if match:
                                return match.group(1)
        except:
            pass
        return ""
    
    async def _find_person_linkedin(self, name, company=None):
        query = name.replace(' ', '+')
        if company:
            query += f"+{company.replace(' ', '+')}"
        search_url = f"https://www.google.com/search?q=linkedin+{query}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url) as response:
                    text = await response.text()
                    for line in text.split('\n'):
                        if 'linkedin.com/in/' in line:
                            match = re.search(r'(https?://[^\s&"]+linkedin\.com/in/[^\s&"]+)', line)
                            if match:
                                return match.group(1)
        except:
            pass
        return ""
    
    async def _get_domain_from_company(self, company):
        domain = await self._find_website(company)
        if domain:
            return self._extract_domain(domain)
        return f"{company.lower().replace(' ', '')}.com"
    
    async def _generate_email(self, first, last, domain):
        patterns = [f"{first.lower()}.{last.lower()}@{domain}", f"{first.lower()}{last.lower()}@{domain}", f"{first.lower()}@{domain}"]
        for email in patterns:
            if await self._verify_email(email):
                return email
        return patterns[0]
    
    async def _verify_email(self, email):
        try:
            validate_email(email, check_deliverability=False)
            domain = email.split('@')[1]
            try:
                dns.resolver.resolve(domain, 'MX')
                return True
            except:
                return False
        except:
            return False
    
    def _extract_domain(self, url):
        url = url.lower().replace('http://', '').replace('https://', '').replace('www.', '')
        return url.split('/')[0].split('?')[0]
    
    def _calculate_score(self, company):
        score = 0
        if company.company_name: score += 15
        if company.website: score += 15
        if company.domain: score += 10
        if company.phone: score += 10
        if company.email: score += 10
        if company.technologies: score += 10
        if company.linkedin_url: score += 10
        if company.description: score += 10
        return min(score, 100)

# ============================================
# AI CHAT ENGINE
# ============================================

class AIChatEngine:
    def __init__(self, scraper):
        self.scraper = scraper
    
    async def chat(self, user_id, message, session_id=None):
        if message.lower().strip() == FOUNDER_NAME.lower():
            return "🔓 FOUNDER MODE ACTIVATED! Unlimited free access forever."
        
        intent = await self._detect_intent(message)
        
        if intent["type"] == "find_company":
            result = await self.scraper.find_company(intent["target"])
            return self._format_company_result(result)
        elif intent["type"] == "find_contact":
            result = await self.scraper.find_person(intent["target"], intent.get("company"))
            return self._format_contact_result(result)
        elif intent["type"] == "solve_problem":
            return await self._solve_problem(message)
        else:
            return await self._general_chat(message)
    
    async def _detect_intent(self, message):
        msg_lower = message.lower()
        if any(w in msg_lower for w in ['find company', 'company info']):
            return {"type": "find_company", "target": message}
        if any(w in msg_lower for w in ['find email', 'contact', 'email of']):
            name = message.replace('find email of', '').replace('contact', '').strip()
            return {"type": "find_contact", "target": name}
        if any(w in msg_lower for w in ['how to', 'solve', 'problem', 'advice']):
            return {"type": "solve_problem", "target": message}
        return {"type": "general", "target": message}
    
    async def _solve_problem(self, problem):
        try:
            response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[{"role": "system", "content": "You are a business problem solver."}, {"role": "user", "content": problem}], max_tokens=500)
            return response.choices[0].message.content
        except:
            return f"**Problem Solving Advice for:** {problem}\n\n1. Break down the problem\n2. Identify root cause\n3. Research solutions\n4. Test and iterate"
    
    async def _general_chat(self, message):
        try:
            response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[{"role": "system", "content": "You are a helpful AI assistant for Problem Solving & Contact Finder."}, {"role": "user", "content": message}], max_tokens=300)
            return response.choices[0].message.content
        except:
            return f"I can help you find contacts, companies, or solve problems. Try: 'Find company Tesla' or 'Email of John Smith'"
    
    def _format_company_result(self, company):
        return f"""**🏢 Company: {company.company_name}**
Website: {company.website or 'Not found'}
Email: {company.email or 'N/A'}
Phone: {company.phone or 'N/A'}
LinkedIn: {company.linkedin_url or 'N/A'}
Quality Score: {company.data_quality_score}/100"""
    
    def _format_contact_result(self, contact):
        verified = "✅" if contact.email_verified else "⚠️"
        return f"""**👤 Contact: {contact.full_name}**
Company: {contact.company or 'N/A'}
Email: {contact.email or 'Not found'} {verified}
LinkedIn: {contact.linkedin_url or 'N/A'}
Confidence: {contact.confidence_score}/100"""

# ============================================
# MAIN SCRAPER CLASS
# ============================================

class ProblemSolverFinder:
    def __init__(self, user_id=None, tier="free", is_founder=False):
        self.db = db
        self.scraper = WebScraper()
        self.ai_chat = AIChatEngine(self.scraper)
        self._current_user_id = user_id
        self._current_user_tier = tier
        self._is_founder = is_founder
    
    async def find_company(self, company_name):
        return await self.scraper.find_company(company_name)
    
    async def find_contact(self, name, company=None):
        return await self.scraper.find_person(name, company)
    
    async def chat(self, message, session_id=None):
        return await self.ai_chat.chat(self._current_user_id, message, session_id)

# ============================================
# FASTAPI SERVER
# ============================================

db.init_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API starting...")
    yield
    logger.info("Shutting down...")

app = FastAPI(title="Problem Solving & Contact Finder", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(status_code=429, content={"error": "Rate limit exceeded"})
# ============================================
# HTML FRONTEND
# ============================================

HTML_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Problem Solving & Contact Finder</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; padding: 40px; background: white; border-radius: 20px; margin-bottom: 30px; }
        h1 { font-size: 48px; color: #1F4E79; }
        .pricing { display: flex; gap: 20px; margin: 40px 0; flex-wrap: wrap; justify-content: center; }
        .plan { background: white; padding: 30px; border-radius: 15px; width: 200px; text-align: center; }
        .price { font-size: 32px; color: #764ba2; font-weight: bold; }
        button { background: #1F4E79; color: white; padding: 12px 24px; border: none; border-radius: 8px; cursor: pointer; width: 100%; }
        .chat-container { background: white; border-radius: 20px; overflow: hidden; }
        .chat-header { background: #1F4E79; color: white; padding: 20px; font-size: 18px; }
        .chat-messages { height: 400px; overflow-y: auto; padding: 20px; background: #f8f9fa; }
        .message { margin-bottom: 15px; display: flex; }
        .user-message { justify-content: flex-end; }
        .bot-message { justify-content: flex-start; }
        .message-bubble { max-width: 70%; padding: 12px 16px; border-radius: 18px; }
        .user-message .message-bubble { background: #1F4E79; color: white; }
        .bot-message .message-bubble { background: white; color: #333; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
        .chat-input { display: flex; padding: 20px; background: white; }
        .chat-input input { flex: 1; padding: 12px; border: 1px solid #ddd; border-radius: 25px; margin-right: 10px; }
        .founder-badge { background: gold; color: #333; padding: 5px 15px; border-radius: 20px; display: inline-block; font-size: 12px; margin-top: 10px; }
        @media (max-width: 768px) { .plan { width: calc(33% - 10px); padding: 15px; } .price { font-size: 24px; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Problem Solving & Contact Finder</h1>
            <p>Find anyone, anywhere. Solve any business problem.</p>
            <div class="founder-badge">✨ Type "admin" for FREE FOREVER access ✨</div>
        </div>
        
        <div class="pricing">
            <div class="plan"><h3>Free</h3><div class="price">$0</div><p>2 tasks</p><button onclick="alert('Free: 2 tasks')">Start</button></div>
            <div class="plan"><h3>Basic</h3><div class="price">$29</div><p>/month</p><button onclick="checkout('basic')">Subscribe</button></div>
            <div class="plan"><h3>Medium</h3><div class="price">$99</div><p>/month</p><button onclick="checkout('medium')">Subscribe</button></div>
            <div class="plan"><h3>High</h3><div class="price">$299</div><p>/month</p><button onclick="checkout('high')">Subscribe</button></div>
            <div class="plan"><h3>Hourly</h3><div class="price">$10</div><p>1 hour</p><button onclick="hourlyCheckout()">Buy</button></div>
        </div>
        
        <div class="chat-container">
            <div class="chat-header">💬 AI Assistant - Ask me anything</div>
            <div class="chat-messages" id="chatMessages">
                <div class="message bot-message"><div class="message-bubble">👋 Hello! I can find contacts, companies, and solve problems.<br>💡 Try: "Find company Tesla" or "Email of Elon Musk"<br>✨ Type "admin" for free forever!</div></div>
            </div>
            <div class="chat-input">
                <input type="text" id="messageInput" placeholder="Type your question..." onkeypress="if(event.key==='Enter') sendMessage()">
                <button onclick="sendMessage()">Send</button>
            </div>
        </div>
    </div>
    
    <script>
        let sessionId = Math.random().toString(36);
        
        async function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            if (!message) return;
            
            const messagesDiv = document.getElementById('chatMessages');
            messagesDiv.innerHTML += `<div class="message user-message"><div class="message-bubble">${escapeHtml(message)}</div></div>`;
            input.value = '';
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: message, session_id: sessionId })
                });
                const data = await response.json();
                messagesDiv.innerHTML += `<div class="message bot-message"><div class="message-bubble">${escapeHtml(data.response)}</div></div>`;
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            } catch (error) {
                messagesDiv.innerHTML += `<div class="message bot-message"><div class="message-bubble">Error: ${error.message}</div></div>`;
            }
        }
        
        async function checkout(tier) {
            const response = await fetch('/create-checkout-session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tier: tier })
            });
            const data = await response.json();
            window.location.href = data.checkout_url;
        }
        
        async function hourlyCheckout() {
            const response = await fetch('/create-hourly-session', { method: 'POST' });
            const data = await response.json();
            window.location.href = data.checkout_url;
        }
        
        function escapeHtml(text) { return text.replace(/[&<>]/g, function(m){if(m==='&') return '&amp;'; if(m==='<') return '&lt;'; if(m==='>') return '&gt;'; return m;}); }
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

@app.post("/api/chat")
@limiter.limit("30 per minute")
async def chat_endpoint(request: Request, chat_req: ChatRequest):
    if chat_req.message.lower().strip() == FOUNDER_NAME.lower():
        return {"response": "🔓 FOUNDER MODE ACTIVATED! Unlimited free access forever."}
    
    if chat_req.hourly_key:
        session = db.check_hourly_session(chat_req.hourly_key)
        if session:
            solver = ProblemSolverFinder(session['user_id'], "high", False)
            response_text = await solver.chat(chat_req.message, chat_req.session_id)
            return {"response": response_text}
    
    solver = ProblemSolverFinder(None, "free", False)
    response_text = await solver.chat(chat_req.message, chat_req.session_id)
    return {"response": response_text}

@app.post("/api/find-company")
@limiter.limit("20 per minute")
async def find_company_endpoint(company_req: CompanyRequest):
    solver = ProblemSolverFinder(None, "free", False)
    result = await solver.find_company(company_req.company_name)
    return {"success": True, "data": asdict(result)}

@app.post("/api/find-contact")
@limiter.limit("20 per minute")
async def find_contact_endpoint(contact_req: ContactRequest):
    solver = ProblemSolverFinder(None, "free", False)
    result = await solver.find_contact(contact_req.name, contact_req.company)
    return {"success": True, "data": asdict(result)}

@app.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    body = await request.json()
    tier = body.get("tier", "basic")
    if tier not in PRICING or PRICING[tier]["price"] == 0:
        raise HTTPException(status_code=400, detail="Invalid tier")
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{"price": PRICING[tier]["price_id"], "quantity": 1}],
        mode="subscription",
        success_url="https://yourdomain.com/success",
        cancel_url="https://yourdomain.com/",
        metadata={"tier": tier}
    )
    return {"checkout_url": session.url}

@app.post("/create-hourly-session")
async def create_hourly_session():
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{"price_data": {"currency": "usd", "product_data": {"name": "1 Hour Unlimited Chat"}, "unit_amount": 1000}, "quantity": 1}],
        mode="payment",
        success_url="https://yourdomain.com/success",
        cancel_url="https://yourdomain.com/",
    )
    return {"checkout_url": session.url}

@app.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except:
        raise HTTPException(status_code=400, detail="Invalid webhook")
    
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email")
        tier = session.get("metadata", {}).get("tier")
        if tier:
            user = db.get_user(email=customer_email)
            if user:
                db.update_user_tier(user['id'], tier, datetime.now() + timedelta(days=30))
            else:
                user_id = secrets.token_urlsafe(16)
                password_hash = hash_password(secrets.token_urlsafe(16))
                db.create_user(user_id, customer_email, password_hash)
                db.update_user_tier(user_id, tier, datetime.now() + timedelta(days=30))
    return {"status": "success"}

@app.get("/pricing")
async def pricing():
    return PRICING

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# ============================================
# MAIN ENTRY POINT
# ============================================

def main():
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║     PROBLEM SOLVING & CONTACT FINDER - READY FOR RENDER    ║
    ╚════════════════════════════════════════════════════════════╝
    
    Server running on http://0.0.0.0:8000
    """)
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()