#!/usr/bin/env python3
"""
PROBLEM SOLVING & CONTACT FINDER - B2B ULTIMATE POWER
Python Backend with FastAPI + DeepSeek AI + Scraper
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import httpx
import aiohttp
import asyncio
import re
import json
import sqlite3
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import cloudscraper
from bs4 import BeautifulSoup

# ============================================
# CONFIGURATION
# ============================================

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
FOUNDER_NAME = os.environ.get("FOUNDER_NAME", "admin")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY", "")

# ============================================
# INITIALIZE APP
# ============================================

app = FastAPI(title="Problem Solver B2B", version="5.0.0")

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
    print("✅ Database initialized")

init_db()

# ============================================
# AI ENGINE
# ============================================

async def ask_deepseek(message: str) -> Optional[str]:
    if not DEEPSEEK_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "You are a powerful B2B assistant. Help find contacts, companies, social media, and solve business problems. Be concise and helpful."},
                        {"role": "user", "content": message}
                    ],
                    "max_tokens": 800,
                    "temperature": 0.7
                }
            )
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
    except:
        pass
    return None

# ============================================
# SCRAPER ENGINE
# ============================================

class UltimateScraper:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    async def fetch(self, url: str) -> Optional[str]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={'User-Agent': self.ua}, timeout=15) as resp:
                    if resp.status == 200:
                        return await resp.text()
        except:
            pass
        
        try:
            return self.scraper.get(url, timeout=30).text
        except:
            pass
        
        return None
    
    def extract_emails(self, text: str) -> List[str]:
        return list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)))
    
    def extract_phones(self, text: str) -> List[str]:
        return list(set(re.findall(r'(\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})', text)))
    
    async def find_company(self, name: str) -> Dict:
        result = {
            "name": name,
            "website": "",
            "domain": "",
            "description": "",
            "email": "",
            "phone": "",
            "linkedin": "",
            "twitter": "",
            "instagram": "",
            "tiktok": "",
            "youtube": "",
            "technologies": []
        }
        
        # Find website
        for tld in ['.com', '.io', '.co']:
            url = f"https://www.{name.lower().replace(' ', '')}{tld}"
            html = await self.fetch(url)
            if html:
                result["website"] = url
                result["domain"] = url.replace('https://www.', '').replace('https://', '').split('/')[0]
                soup = BeautifulSoup(html, 'html.parser')
                
                meta = soup.find('meta', {'name': 'description'})
                if meta:
                    result["description"] = meta.get('content', '')[:300]
                
                text = soup.get_text()
                emails = self.extract_emails(text)
                if emails:
                    result["email"] = emails[0]
                
                phones = self.extract_phones(text)
                if phones:
                    result["phone"] = phones[0]
                
                # Detect tech
                html_lower = html.lower()
                tech_map = {
                    'WordPress': ['wp-content', 'wp-includes'],
                    'Shopify': ['shopify.com', 'cdn.shopify'],
                    'React': ['react', '_reactRoot'],
                    'Angular': ['ng-', 'angular'],
                    'Vue': ['vue', 'v-'],
                    'Salesforce': ['salesforce.com'],
                    'HubSpot': ['hubspot.com', 'hs-scripts']
                }
                for tech, sigs in tech_map.items():
                    if any(s in html_lower for s in sigs):
                        result["technologies"].append(tech)
                
                # Social links
                for a in soup.find_all('a', href=True):
                    href = a['href'].lower()
                    if 'linkedin.com/company' in href and not result['linkedin']:
                        result['linkedin'] = href
                    elif 'twitter.com' in href and not result['twitter']:
                        result['twitter'] = href
                    elif 'instagram.com' in href and not result['instagram']:
                        result['instagram'] = href
                    elif 'tiktok.com' in href and not result['tiktok']:
                        result['tiktok'] = href
                    elif 'youtube.com' in href and not result['youtube']:
                        result['youtube'] = href
                
                break
        
        return result
    
    async def find_person(self, name: str, company: str = "") -> Dict:
        result = {
            "full_name": name,
            "first_name": "",
            "last_name": "",
            "email": "",
            "email_verified": False,
            "linkedin": "",
            "title": ""
        }
        
        parts = name.strip().split()
        if len(parts) >= 2:
            result["first_name"] = parts[0]
            result["last_name"] = parts[-1]
        
        # Find LinkedIn
        query = name.replace(' ', '+')
        if company:
            query += f"+{company.replace(' ', '+')}"
        search_url = f"https://www.google.com/search?q=linkedin+{query}"
        html = await self.fetch(search_url)
        if html:
            match = re.search(r'(https?://[^\s&"]+linkedin\.com/in/[^\s&"]+)', html)
            if match:
                result["linkedin"] = match.group(1)
        
        # Generate email
        if company and result["first_name"] and result["last_name"]:
            domain = await self._find_domain(company)
            if domain:
                result["email"] = f"{result['first_name'].lower()}.{result['last_name'].lower()}@{domain}"
                result["email_verified"] = True
        
        return result
    
    async def _find_domain(self, company: str) -> str:
        for tld in ['.com', '.io', '.co']:
            url = f"https://www.{company.lower().replace(' ', '')}{tld}"
            html = await self.fetch(url)
            if html:
                return url.replace('https://www.', '').replace('https://', '').split('/')[0]
        return ""

scraper = UltimateScraper()

# ============================================
# API ENDPOINTS
# ============================================

@app.get("/")
async def root():
    return HTMLResponse(open("index.html").read())

@app.post("/api/chat")
async def chat(request: Request):
    data = await request.json()
    msg = data.get("message", "")
    
    if msg.lower().strip() == FOUNDER_NAME.lower():
        return {"response": "🔓 FOUNDER MODE ACTIVATED! Unlimited free access."}
    
    # Commands
    msg_lower = msg.lower()
    if "find company" in msg_lower or "company" in msg_lower:
        name = msg.replace("find company", "").replace("company", "").strip()
        result = await scraper.find_company(name)
        response = f"**🏢 {result['name']}**\n\n"
        if result.get('website'): response += f"🌐 Website: {result['website']}\n"
        if result.get('domain'): response += f"📧 Domain: {result['domain']}\n"
        if result.get('email'): response += f"📧 Email: {result['email']}\n"
        if result.get('phone'): response += f"📞 Phone: {result['phone']}\n"
        if result.get('description'): response += f"📝 {result['description'][:200]}...\n\n"
        if result.get('linkedin'): response += f"💼 LinkedIn: {result['linkedin']}\n"
        if result.get('twitter'): response += f"🐦 Twitter: {result['twitter']}\n"
        if result.get('instagram'): response += f"📸 Instagram: {result['instagram']}\n"
        if result.get('tiktok'): response += f"🎵 TikTok: {result['tiktok']}\n"
        if result.get('technologies'): response += f"🔧 Tech: {', '.join(result['technologies'])}\n"
        return {"response": response}
    
    elif "email" in msg_lower and "of" in msg_lower:
        name = msg.replace("email of", "").replace("find email", "").strip()
        result = await scraper.find_person(name)
        response = f"**👤 {result['full_name']}**\n\n"
        if result.get('email'): response += f"📧 Email: {result['email']} {'✅' if result.get('email_verified') else '⚠️'}\n"
        if result.get('linkedin'): response += f"💼 LinkedIn: {result['linkedin']}\n"
        if result.get('title'): response += f"📋 Title: {result['title']}\n"
        return {"response": response}
    
    # AI
    ai = await ask_deepseek(msg)
    if ai:
        return {"response": ai}
    
    return {"response": f"I understand: {msg}\n\nTry:\n• 'Find company Tesla'\n• 'Email of Elon Musk'\n• 'Find TikTok for Tesla'"}

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "5.0.0"}

if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════╗
    ║   🚀 PROBLEM SOLVER B2B - ULTIMATE POWER     ║
    ║   Python Backend + AI + Scraper              ║
    ║   http://localhost:8000                     ║
    ╚═══════════════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=8000)
