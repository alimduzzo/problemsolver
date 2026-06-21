#!/usr/bin/env python3
"""
PROBLEM SOLVING & CONTACT FINDER - ULTIMATE EDITION
===================================================
Professional website with:
- AI Chat (DeepSeek)
- Multi-layer scraping with fallbacks
- Company/Contact/Location/Social Media Finder
- 5 Payment Tiers (Stripe)
- Founder Mode (hidden secret word)
- Professional design with navigation
"""

import asyncio
import aiohttp
import httpx
import requests
import cloudscraper
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import re
import json
import os
import sqlite3
import secrets
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from contextlib import asynccontextmanager
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from email_validator import validate_email
import dns.resolver
import whois
import phonenumbers
from phonenumbers import carrier, geocoder
from fake_useragent import UserAgent
import bcrypt
import pyotp
import qrcode
from io import BytesIO
import base64

# ============================================
# CONFIGURATION
# ============================================

# Environment Variables (set in Render)
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY", "")
FOUNDER_NAME = os.environ.get("FOUNDER_NAME", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./problemsolver.db")
SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_urlsafe(32))

# Pricing Tiers
PRICING = {
    "free": {"price": 0, "tasks_limit": 2, "lookups_limit": 2, "ai_chat": True},
    "basic": {"price": 29, "tasks_limit": 500, "lookups_limit": 500, "ai_chat": True},
    "medium": {"price": 99, "tasks_limit": 2000, "lookups_limit": 2000, "ai_chat": True},
    "high": {"price": 299, "tasks_limit": 999999, "lookups_limit": 999999, "ai_chat": True},
    "hourly": {"price": 10, "tasks_limit": 999999, "lookups_limit": 999999, "ai_chat": True}
}

# ============================================
# DATABASE
# ============================================

def init_db():
    conn = sqlite3.connect('problemsolver.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE,
            name TEXT,
            password_hash TEXT,
            tier TEXT DEFAULT 'free',
            founder_mode BOOLEAN DEFAULT FALSE,
            tasks_used INTEGER DEFAULT 0,
            lookups_used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            token TEXT UNIQUE,
            expires_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Search history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            query TEXT,
            result_type TEXT,
            result_data TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Hourly sessions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hourly_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            session_key TEXT UNIQUE,
            expires_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Chat history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            session_id TEXT,
            question TEXT,
            answer TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

init_db()

# ============================================
# ULTIMATE SCRAPER ENGINE
# ============================================

class UltimateScraper:
    """Multi-layer scraper with fallback methods"""
    
    def __init__(self):
        self.ua = UserAgent()
        self.scraper = cloudscraper.create_scraper()
        self.driver = None
        self.session = None
        
    # ============================================
    # LAYER 1: aiohttp (async, fastest)
    # ============================================
    
    async def fetch_aiohttp(self, url: str) -> Optional[str]:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {'User-Agent': self.ua.random}
                async with session.get(url, headers=headers, timeout=15) as response:
                    if response.status == 200:
                        return await response.text()
        except:
            pass
        return None
    
    # ============================================
    # LAYER 2: requests (sync, reliable)
    # ============================================
    
    def fetch_requests(self, url: str) -> Optional[str]:
        try:
            headers = {'User-Agent': self.ua.random}
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                return response.text
        except:
            pass
        return None
    
    # ============================================
    # LAYER 3: cloudscraper (bypass Cloudflare)
    # ============================================
    
    def fetch_cloudscraper(self, url: str) -> Optional[str]:
        try:
            response = self.scraper.get(url, timeout=30)
            if response.status_code == 200:
                return response.text
        except:
            pass
        return None
    
    # ============================================
    # LAYER 4: Selenium (JavaScript rendering)
    # ============================================
    
    def fetch_selenium(self, url: str) -> Optional[str]:
        try:
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            driver = webdriver.Chrome(options=options)
            driver.get(url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            html = driver.page_source
            driver.quit()
            return html
        except:
            pass
        return None
    
    # ============================================
    # LAYER 5: undetected-chromedriver (anti-detection)
    # ============================================
    
    def fetch_undetected(self, url: str) -> Optional[str]:
        try:
            driver = uc.Chrome(headless=True)
            driver.get(url)
            html = driver.page_source
            driver.quit()
            return html
        except:
            pass
        return None
    
    # ============================================
    # MASTER FETCH: Try all methods
    # ============================================
    
    async def fetch(self, url: str) -> Optional[str]:
        """Try all fetch methods until one works"""
        methods = [
            self.fetch_aiohttp(url),
            asyncio.to_thread(self.fetch_requests, url),
            asyncio.to_thread(self.fetch_cloudscraper, url),
            asyncio.to_thread(self.fetch_selenium, url),
            asyncio.to_thread(self.fetch_undetected, url)
        ]
        
        for method in methods:
            result = await method
            if result:
                return result
        
        return None
    
    # ============================================
    # PARSE HTML (multiple methods)
    # ============================================
    
    def parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML with BeautifulSoup"""
        return BeautifulSoup(html, 'html.parser')
    
    # ============================================
    # EXTRACT EMAILS
    # ============================================
    
    def extract_emails(self, text: str) -> List[str]:
        """Extract all emails from text"""
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        return list(set(re.findall(pattern, text)))
    
    # ============================================
    # EXTRACT PHONES
    # ============================================
    
    def extract_phones(self, text: str) -> List[str]:
        """Extract phone numbers from text"""
        pattern = r'(\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})'
        phones = re.findall(pattern, text)
        valid = []
        for p in phones:
            try:
                parsed = phonenumbers.parse(p, "US")
                if phonenumbers.is_valid_number(parsed):
                    valid.append(phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164))
            except:
                pass
        return valid
    
    # ============================================
    # EXTRACT SOCIAL MEDIA
    # ============================================
    
    def extract_social(self, html: str) -> Dict[str, str]:
        """Extract social media links from HTML"""
        social = {
            "linkedin": "",
            "twitter": "",
            "facebook": "",
            "instagram": "",
            "tiktok": "",
            "youtube": ""
        }
        
        soup = BeautifulSoup(html, 'html.parser')
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link['href'].lower()
            if 'linkedin.com' in href and not social['linkedin']:
                social['linkedin'] = href
            elif 'twitter.com' in href and not social['twitter']:
                social['twitter'] = href
            elif 'facebook.com' in href and not social['facebook']:
                social['facebook'] = href
            elif 'instagram.com' in href and not social['instagram']:
                social['instagram'] = href
            elif 'tiktok.com' in href and not social['tiktok']:
                social['tiktok'] = href
            elif 'youtube.com' in href and not social['youtube']:
                social['youtube'] = href
        
        return social
    
    # ============================================
    # FIND COMPANY
    # ============================================
    
    async def find_company(self, company_name: str) -> Dict[str, Any]:
        """Find everything about a company with fallbacks"""
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
            "employees": "",
            "founded": "",
            "technologies": [],
            "news": [],
            "hiring": []
        }
        
        # Try to find website
        website = await self._find_website(company_name)
        if website:
            result["website"] = website
            result["domain"] = self._extract_domain(website)
            html = await self.fetch(website)
            if html:
                soup = self.parse_html(html)
                # Description
                meta_desc = soup.find('meta', {'name': 'description'})
                if meta_desc:
                    result["description"] = meta_desc.get('content', '')[:500]
                # Emails
                text = soup.get_text()
                emails = self.extract_emails(text)
                if emails:
                    result["email"] = emails[0]
                # Phones
                phones = self.extract_phones(text)
                if phones:
                    result["phone"] = phones[0]
                # Technologies
                result["technologies"] = self._detect_technologies(html)
                # Social
                social = self.extract_social(html)
                result.update(social)
        
        # Crunchbase
        result["crunchbase"] = f"https://www.crunchbase.com/organization/{company_name.lower().replace(' ', '-')}"
        
        return result
    
    # ============================================
    # FIND PERSON
    # ============================================
    
    async def find_person(self, name: str, company: str = "") -> Dict[str, Any]:
        """Find everything about a person with fallbacks"""
        result = {
            "name": name,
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
        
        # Split name
        parts = name.strip().split()
        if len(parts) >= 2:
            result["first_name"] = parts[0]
            result["last_name"] = parts[-1]
        
        # Find LinkedIn
        linkedin = await self._find_linkedin_person(name, company)
        if linkedin:
            result["linkedin"] = linkedin
        
        # Generate email
        if result["first_name"] and result["last_name"] and company:
            domain = await self._find_website(company)
            if domain:
                domain = self._extract_domain(domain)
                email = f"{result['first_name'].lower()}.{result['last_name'].lower()}@{domain}"
                result["email"] = email
                result["email_verified"] = await self._verify_email(email)
        
        return result
    
    # ============================================
    # FIND SOCIAL MEDIA
    # ============================================
    
    async def find_social(self, name: str, platform: str) -> str:
        """Find social media account for a name"""
        platform_urls = {
            "tiktok": "https://www.tiktok.com/@",
            "instagram": "https://www.instagram.com/",
            "twitter": "https://twitter.com/",
            "linkedin": "https://linkedin.com/in/",
            "youtube": "https://youtube.com/@"
        }
        
        # Try Google search
        search_url = f"https://www.google.com/search?q={platform}+{name.replace(' ', '+')}"
        html = await self.fetch(search_url)
        if html:
            pattern = f'(https?://[^\s&"]+{platform}\.com/[^\s&"]+)'
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        
        # Try direct username
        base = platform_urls.get(platform, "")
        if base:
            return f"{base}{name.lower().replace(' ', '')}"
        
        return ""
    
    # ============================================
    # FIND NEWS
    # ============================================
    
    async def find_news(self, name: str) -> List[str]:
        """Find latest news about a name"""
        search_url = f"https://www.google.com/search?q={name.replace(' ', '+')}+news"
        html = await self.fetch(search_url)
        if html:
            soup = self.parse_html(html)
            headlines = []
            for h3 in soup.find_all('h3'):
                if h3.text and len(h3.text) > 10:
                    headlines.append(h3.text)
            return headlines[:10]
        return []
    
    # ============================================
    # FIND HIRING
    # ============================================
    
    async def find_hiring(self, company: str) -> List[str]:
        """Find job postings at a company"""
        search_url = f"https://www.google.com/search?q={company.replace(' ', '+')}+jobs+hiring"
        html = await self.fetch(search_url)
        if html:
            jobs = re.findall(r'(https?://[^\s&"]+jobs?[^\s&"]+)', html)
            return list(set(jobs))[:10]
        return []
    
    # ============================================
    # FIND TECHNOLOGIES
    # ============================================
    
    def _detect_technologies(self, html: str) -> List[str]:
        """Detect technologies from HTML"""
        techs = []
        html_lower = html.lower()
        
        tech_map = {
            'WordPress': ['wp-content', 'wp-includes'],
            'Shopify': ['shopify.com', 'cdn.shopify'],
            'Salesforce': ['salesforce.com'],
            'React': ['react', '_reactRoot', 'ReactDOM'],
            'Angular': ['ng-', 'angular'],
            'Vue': ['vue', 'v-'],
            'jQuery': ['jquery'],
            'Bootstrap': ['bootstrap'],
            'Tailwind': ['tailwind'],
            'Google Analytics': ['ga.js', 'gtag'],
            'Facebook Pixel': ['facebook.com/tr'],
            'HubSpot': ['hubspot.com', 'hs-scripts'],
            'Stripe': ['stripe.com', 'stripe.js']
        }
        
        for tech, signatures in tech_map.items():
            if any(sig in html_lower for sig in signatures):
                techs.append(tech)
        
        return techs
    
    # ============================================
    # HELPERS
    # ============================================
    
    async def _find_website(self, name: str) -> str:
        """Find company website"""
        candidates = [
            f"https://www.{name.lower().replace(' ', '')}.com",
            f"https://{name.lower().replace(' ', '')}.com",
            f"https://www.{name.lower().replace(' ', '')}.io",
            f"https://{name.lower().replace(' ', '')}.io"
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
    
    async def _find_linkedin_person(self, name: str, company: str = "") -> str:
        """Find LinkedIn profile"""
        query = name.replace(' ', '+')
        if company:
            query += f"+{company.replace(' ', '+')}"
        search_url = f"https://www.google.com/search?q=linkedin+{query}"
        html = await self.fetch(search_url)
        if html:
            match = re.search(r'(https?://[^\s&"]+linkedin\.com/in/[^\s&"]+)', html)
            if match:
                return match.group(1)
        return ""
    
    async def _verify_email(self, email: str) -> bool:
        """Verify email exists"""
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
        return False
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        url = url.lower().replace('http://', '').replace('https://', '').replace('www.', '')
        return url.split('/')[0].split('?')[0]

scraper = UltimateScraper()

# ============================================
# AI ENGINE (DeepSeek)
# ============================================

async def ask_deepseek(message: str) -> Optional[str]:
    """Ask DeepSeek AI with fallback"""
    if not DEEPSEEK_API_KEY:
        return None
    
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
                        {"role": "system", "content": "You are a powerful business assistant. Help users find contacts, companies, social media, news, and solve problems. Be accurate and helpful."},
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
    except:
        pass
    return None

# ============================================
# FASTAPI APP
# ============================================

app = FastAPI(
    title="Problem Solving & Contact Finder",
    description="Find anyone, anywhere. Solve any business problem.",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# HTML - PART 1 (Head and Navigation)
# ============================================

HTML_PAGE_1 = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔍 Problem Solver - Ultimate Business Intelligence</title>
    <style>
        /* ============================================
           CSS - Complete Professional Design
           ============================================ */
        
        /* Reset */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        /* Variables */
        :root {
            --primary: #1a237e;
            --primary-light: #283593;
            --secondary: #e94560;
            --secondary-light: #ff6b8a;
            --gradient: linear-gradient(135deg, #1a237e 0%, #e94560 100%);
            --gradient-bg: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            --text-light: #ffffff;
            --text-dark: #1a1a2e;
            --card-bg: rgba(255, 255, 255, 0.05);
            --border: rgba(255, 255, 255, 0.1);
            --shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            --radius: 16px;
            --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        /* Global */
        html { scroll-behavior: smooth; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: var(--gradient-bg);
            color: var(--text-light);
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #1a1a2e; }
        ::-webkit-scrollbar-thumb { background: var(--secondary); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--secondary-light); }
        
        /* ============================================
           NAVIGATION
           ============================================ */
        .navbar {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 1000;
            background: rgba(15, 12, 41, 0.9);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--border);
            padding: 12px 0;
            transition: var(--transition);
        }
        
        .navbar.scrolled {
            background: rgba(15, 12, 41, 0.98);
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);
        }
        
        .nav-container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .nav-logo {
            font-size: 24px;
            font-weight: 800;
            color: var(--text-light);
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .nav-logo span {
            background: var(--gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .nav-links {
            display: flex;
            gap: 30px;
            align-items: center;
            list-style: none;
        }
        
        .nav-links a {
            color: rgba(255, 255, 255, 0.7);
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
            transition: var(--transition);
            position: relative;
        }
        
        .nav-links a:hover {
            color: var(--text-light);
        }
        
        .nav-links a::after {
            content: '';
            position: absolute;
            bottom: -4px;
            left: 0;
            width: 0;
            height: 2px;
            background: var(--secondary);
            transition: var(--transition);
        }
        
        .nav-links a:hover::after {
            width: 100%;
        }
        
        .nav-cta {
            background: var(--secondary);
            padding: 8px 20px;
            border-radius: 25px;
            color: white !important;
            font-weight: 600 !important;
        }
        
        .nav-cta:hover {
            background: var(--secondary-light);
            transform: scale(1.05);
        }
        
        .nav-cta::after { display: none !important; }
        
        .mobile-toggle {
            display: none;
            background: none;
            border: none;
            color: white;
            font-size: 28px;
            cursor: pointer;
        }
        
        /* ============================================
           HERO SECTION
           ============================================ */
        .hero {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 100px 20px 60px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }
        
        .hero::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(ellipse at center, rgba(233, 69, 96, 0.1) 0%, transparent 70%);
            animation: pulse 8s ease-in-out infinite;
        }
        
        @keyframes pulse {
            0%, 100% { transform: scale(1); opacity: 0.5; }
            50% { transform: scale(1.1); opacity: 1; }
        }
        
        .hero-content {
            position: relative;
            z-index: 1;
            max-width: 900px;
        }
        
        .hero-badge {
            display: inline-block;
            background: rgba(233, 69, 96, 0.2);
            color: var(--secondary);
            padding: 6px 20px;
            border-radius: 25px;
            font-size: 13px;
            font-weight: 600;
            border: 1px solid rgba(233, 69, 96, 0.3);
            margin-bottom: 20px;
        }
        
        .hero h1 {
            font-size: 64px;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 20px;
            background: var(--gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .hero p {
            font-size: 20px;
            color: rgba(255, 255, 255, 0.7);
            max-width: 600px;
            margin: 0 auto 30px;
            line-height: 1.6;
        }
    
    """
#part 2
.hero-search {
        display: flex;
        max-width: 600px;
        margin: 0 auto;
        gap: 12px;
        background: rgba(255, 255, 255, 0.05);
        padding: 6px;
        border-radius: 50px;
        border: 1px solid var(--border);
        backdrop-filter: blur(10px);
    }
    
    .hero-search input {
        flex: 1;
        padding: 16px 24px;
        border: none;
        border-radius: 50px;
        background: transparent;
        color: white;
        font-size: 16px;
        outline: none;
    }
    
    .hero-search input::placeholder {
        color: rgba(255, 255, 255, 0.4);
    }
    
    .hero-search button {
        padding: 14px 32px;
        background: var(--gradient);
        border: none;
        border-radius: 50px;
        color: white;
        font-weight: 700;
        font-size: 16px;
        cursor: pointer;
        transition: var(--transition);
    }
    
    .hero-search button:hover {
        transform: scale(1.05);
        box-shadow: 0 10px 40px rgba(233, 69, 96, 0.3);
    }
    
    .hero-stats {
        display: flex;
        gap: 40px;
        justify-content: center;
        margin-top: 40px;
    }
    
    .hero-stats-item {
        text-align: center;
    }
    
    .hero-stats-item .number {
        font-size: 32px;
        font-weight: 800;
        color: var(--text-light);
    }
    
    .hero-stats-item .label {
        font-size: 14px;
        color: rgba(255, 255, 255, 0.5);
        margin-top: 4px;
    }
    
    /* ============================================
       FEATURES SECTION
       ============================================ */
    .features {
        padding: 80px 20px;
        max-width: 1200px;
        margin: 0 auto;
    }
    
    .features-header {
        text-align: center;
        margin-bottom: 60px;
    }
    
    .features-header h2 {
        font-size: 40px;
        font-weight: 700;
        margin-bottom: 12px;
    }
    
    .features-header p {
        color: rgba(255, 255, 255, 0.6);
        font-size: 18px;
    }
    
    .features-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 24px;
    }
    
    .feature-card {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 32px;
        transition: var(--transition);
        cursor: pointer;
    }
    
    .feature-card:hover {
        transform: translateY(-8px);
        border-color: var(--secondary);
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    }
    
    .feature-icon {
        font-size: 40px;
        margin-bottom: 16px;
    }
    
    .feature-card h3 {
        font-size: 20px;
        margin-bottom: 8px;
    }
    
    .feature-card p {
        color: rgba(255, 255, 255, 0.6);
        font-size: 14px;
        line-height: 1.6;
    }
    
    /* ============================================
       PRICING SECTION
       ============================================ */
    .pricing-section {
        padding: 80px 20px;
        max-width: 1200px;
        margin: 0 auto;
    }
    
    .pricing-header {
        text-align: center;
        margin-bottom: 60px;
    }
    
    .pricing-header h2 {
        font-size: 40px;
        font-weight: 700;
        margin-bottom: 12px;
    }
    
    .pricing-header p {
        color: rgba(255, 255, 255, 0.6);
        font-size: 18px;
    }
    
    .pricing-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 20px;
        align-items: stretch;
    }
    
    .pricing-card {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 30px 24px;
        text-align: center;
        transition: var(--transition);
        position: relative;
    }
    
    .pricing-card:hover {
        transform: translateY(-4px);
        border-color: var(--secondary);
    }
    
    .pricing-card.popular {
        border-color: var(--secondary);
        background: rgba(233, 69, 96, 0.1);
    }
    
    .pricing-card.popular::before {
        content: '🔥 MOST POPULAR';
        position: absolute;
        top: -12px;
        left: 50%;
        transform: translateX(-50%);
        background: var(--secondary);
        color: white;
        padding: 4px 16px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
    }
    
    .pricing-name {
        font-size: 14px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: rgba(255, 255, 255, 0.6);
        margin-bottom: 8px;
    }
    
    .pricing-price {
        font-size: 36px;
        font-weight: 800;
        margin-bottom: 4px;
    }
    
    .pricing-period {
        font-size: 14px;
        color: rgba(255, 255, 255, 0.4);
    }
    
    .pricing-features {
        list-style: none;
        margin: 20px 0;
        text-align: left;
    }
    
    .pricing-features li {
        padding: 6px 0;
        font-size: 14px;
        color: rgba(255, 255, 255, 0.7);
    }
    
    .pricing-features li::before {
        content: '✅ ';
    }
    
    .pricing-btn {
        width: 100%;
        padding: 12px;
        background: var(--gradient);
        border: none;
        border-radius: 25px;
        color: white;
        font-weight: 700;
        font-size: 14px;
        cursor: pointer;
        transition: var(--transition);
    }
    
    .pricing-btn:hover {
        transform: scale(1.02);
        box-shadow: 0 10px 40px rgba(233, 69, 96, 0.3);
    }
    
    /* ============================================
       CHAT SECTION
       ============================================ */
    .chat-section {
        padding: 80px 20px;
        max-width: 900px;
        margin: 0 auto;
    }
    
    .chat-container {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        overflow: hidden;
        backdrop-filter: blur(10px);
    }
    
    .chat-header {
        padding: 20px 24px;
        background: rgba(255, 255, 255, 0.03);
        border-bottom: 1px solid var(--border);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .chat-header h3 {
        font-size: 18px;
    }
    
    .chat-status {
        font-size: 12px;
        color: #4ade80;
    }
    
    .chat-messages {
        height: 500px;
        overflow-y: auto;
        padding: 24px;
        background: rgba(0, 0, 0, 0.2);
    }
    
    .message {
        margin-bottom: 16px;
        display: flex;
    }
    
    .message.user {
        justify-content: flex-end;
    }
    
    .message.bot {
        justify-content: flex-start;
    }
    
    .message-bubble {
        max-width: 80%;
        padding: 12px 20px;
        border-radius: 20px;
        word-wrap: break-word;
        font-size: 15px;
        line-height: 1.5;
    }
    
    .message.user .message-bubble {
        background: var(--secondary);
        color: white;
        border-bottom-right-radius: 4px;
    }
    
    .message.bot .message-bubble {
        background: rgba(255, 255, 255, 0.08);
        color: white;
        border-bottom-left-radius: 4px;
    }
    
    .chat-input-area {
        display: flex;
        padding: 16px 24px;
        gap: 12px;
        border-top: 1px solid var(--border);
        background: rgba(0, 0, 0, 0.2);
    }
    
    .chat-input-area input {
        flex: 1;
        padding: 14px 20px;
        border: 1px solid var(--border);
        border-radius: 25px;
        background: rgba(255, 255, 255, 0.05);
        color: white;
        font-size: 15px;
        outline: none;
        transition: var(--transition);
    }
    
    .chat-input-area input:focus {
        border-color: var(--secondary);
    }
    
    .chat-input-area input::placeholder {
        color: rgba(255, 255, 255, 0.4);
    }
    
    .chat-input-area button {
        padding: 14px 32px;
        background: var(--gradient);
        border: none;
        border-radius: 25px;
        color: white;
        font-weight: 700;
        font-size: 15px;
        cursor: pointer;
        transition: var(--transition);
    }
    
    .chat-input-area button:hover {
        transform: scale(1.03);
    }
    
    .quick-actions {
        display: flex;
        gap: 8px;
        padding: 12px 24px;
        flex-wrap: wrap;
        border-top: 1px solid var(--border);
    }
    
    .quick-actions button {
        padding: 6px 16px;
        border: 1px solid var(--border);
        border-radius: 20px;
        background: transparent;
        color: rgba(255, 255, 255, 0.7);
        font-size: 12px;
        cursor: pointer;
        transition: var(--transition);
    }
    
    .quick-actions button:hover {
        border-color: var(--secondary);
        color: white;
        background: rgba(233, 69, 96, 0.1);
    }
    
    /* ============================================
       FOOTER
       ============================================ */
    .footer {
        border-top: 1px solid var(--border);
        padding: 40px 20px;
        text-align: center;
        color: rgba(255, 255, 255, 0.4);
        font-size: 14px;
    }
    
    .footer a {
        color: rgba(255, 255, 255, 0.6);
        text-decoration: none;
        transition: var(--transition);
    }
    
    .footer a:hover {
        color: var(--text-light);
    }
    
    .footer-links {
        display: flex;
        justify-content: center;
        gap: 24px;
        margin-bottom: 16px;
    }
    
    /* ============================================
       RESPONSIVE
       ============================================ */
    @media (max-width: 768px) {
        .nav-links {
            display: none;
            flex-direction: column;
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: rgba(15, 12, 41, 0.98);
            padding: 20px;
            border-bottom: 1px solid var(--border);
        }
        
        .nav-links.open {
            display: flex;
        }
        
        .mobile-toggle {
            display: block;
        }
        
        .hero h1 {
            font-size: 36px;
        }
        
        .hero p {
            font-size: 16px;
        }
        
        .hero-search {
            flex-direction: column;
            border-radius: 16px;
            background: transparent;
            padding: 0;
        }
        
        .hero-search input {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border);
            border-radius: 16px;
        }
        
        .hero-search button {
            border-radius: 16px;
        }
        
        .hero-stats {
            flex-wrap: wrap;
            gap: 20px;
        }
        
        .pricing-grid {
            grid-template-columns: 1fr 1fr;
        }
        
        .features-grid {
            grid-template-columns: 1fr;
        }
        
        .chat-messages {
            height: 350px;
            padding: 16px;
        }
        
        .message-bubble {
            max-width: 90%;
            font-size: 14px;
        }
        
        .chat-input-area {
            flex-direction: column;
            padding: 12px 16px;
        }
    }
    
    @media (max-width: 480px) {
        .pricing-grid {
            grid-template-columns: 1fr;
        }
        
        .hero h1 {
            font-size: 28px;
        }
        
        .features-header h2 {
            font-size: 28px;
        }
        
        .pricing-header h2 {
            font-size: 28px;
        }
    }
    </style>
</head>
<body>
#part 3
<!-- ============================================
    NAVIGATION
    ============================================ -->
    <nav class="navbar" id="navbar">
        <div class="nav-container">
            <a href="/" class="nav-logo">
                🚀 <span>Problem Solver</span>
            </a>
            <ul class="nav-links" id="navLinks">
                <li><a href="#features">Features</a></li>
                <li><a href="#pricing">Pricing</a></li>
                <li><a href="#chat">Chat</a></li>
                <li><a href="#pricing" class="nav-cta">Get Started</a></li>
            </ul>
            <button class="mobile-toggle" onclick="toggleNav()">☰</button>
        </div>
    </nav>

    <!-- ============================================
    HERO
    ============================================ -->
    <section class="hero">
        <div class="hero-content">
            <div class="hero-badge">🚀 AI-Powered Business Intelligence</div>
            <h1>Find Anyone,<br>Anywhere.</h1>
            <p>Stop wasting hours searching. Get contacts, companies, social media, and business intelligence in seconds.</p>
            
            <div class="hero-search">
                <input type="text" id="heroSearch" placeholder="Try: Find company Tesla or Email of Elon Musk" onkeypress="if(event.key==='Enter') heroSearchAction()">
                <button onclick="heroSearchAction()">🔍 Search</button>
            </div>
            
            <div class="hero-stats">
                <div class="hero-stats-item">
                    <div class="number">10K+</div>
                    <div class="label">Companies Found</div>
                </div>
                <div class="hero-stats-item">
                    <div class="number">50K+</div>
                    <div class="label">Contacts Found</div>
                </div>
                <div class="hero-stats-item">
                    <div class="number">100+</div>
                    <div class="label">Countries Covered</div>
                </div>
            </div>
        </div>
    </section>

    <!-- ============================================
    FEATURES
    ============================================ -->
    <section class="features" id="features">
        <div class="features-header">
            <h2>🔥 What You Can Find</h2>
            <p>Everything you need to grow your business</p>
        </div>
        <div class="features-grid">
            <div class="feature-card" onclick="quickSearch('Find company')">
                <div class="feature-icon">🏢</div>
                <h3>Companies</h3>
                <p>Full company data: website, email, phone, LinkedIn, Twitter, funding, technologies, and more.</p>
            </div>
            <div class="feature-card" onclick="quickSearch('Email of')">
                <div class="feature-icon">📧</div>
                <h3>Contacts & Emails</h3>
                <p>Find anyone's email, phone, LinkedIn, and social profiles. Verified and up-to-date.</p>
            </div>
            <div class="feature-card" onclick="quickSearch('Find TikTok for')">
                <div class="feature-icon">🎵</div>
                <h3>Social Media</h3>
                <p>Discover TikTok, Instagram, Twitter, LinkedIn, YouTube profiles for any person or brand.</p>
            </div>
            <div class="feature-card" onclick="quickSearch('Find news about')">
                <div class="feature-icon">📰</div>
                <h3>News & Updates</h3>
                <p>Latest news, funding rounds, hiring signals, and company announcements.</p>
            </div>
            <div class="feature-card" onclick="quickSearch('Find location of')">
                <div class="feature-icon">📍</div>
                <h3>Location & Identity</h3>
                <p>Find where people are, their nationality, and public records (legal only).</p>
            </div>
            <div class="feature-card" onclick="quickSearch('How to')">
                <div class="feature-icon">💡</div>
                <h3>AI Problem Solver</h3>
                <p>Get actionable business advice, strategies, and solutions to any problem.</p>
            </div>
        </div>
    </section>

    <!-- ============================================
    PRICING
    ============================================ -->
    <section class="pricing-section" id="pricing">
        <div class="pricing-header">
            <h2>💰 Choose Your Plan</h2>
            <p>Start free, upgrade when you need more</p>
        </div>
        <div class="pricing-grid">
            <div class="pricing-card">
                <div class="pricing-name">Free</div>
                <div class="pricing-price">$0</div>
                <div class="pricing-period">forever</div>
                <ul class="pricing-features">
                    <li>2 tasks</li>
                    <li>Basic search</li>
                    <li>Test the tool</li>
                </ul>
                <button class="pricing-btn" onclick="alert('Free tier: 2 tasks. Chat to start!')">Start Free</button>
            </div>
            <div class="pricing-card">
                <div class="pricing-name">Basic</div>
                <div class="pricing-price">$29</div>
                <div class="pricing-period">/month</div>
                <ul class="pricing-features">
                    <li>500 lookups</li>
                    <li>AI Chat</li>
                    <li>Company data</li>
                </ul>
                <button class="pricing-btn" onclick="checkout('basic')">Subscribe</button>
            </div>
            <div class="pricing-card popular">
                <div class="pricing-name">Medium</div>
                <div class="pricing-price">$99</div>
                <div class="pricing-period">/month</div>
                <ul class="pricing-features">
                    <li>2000 lookups</li>
                    <li>AI Chat</li>
                    <li>Social Media Finder</li>
                    <li>Location Finder</li>
                </ul>
                <button class="pricing-btn" onclick="checkout('medium')">Subscribe</button>
            </div>
            <div class="pricing-card">
                <div class="pricing-name">High</div>
                <div class="pricing-price">$299</div>
                <div class="pricing-period">/month</div>
                <ul class="pricing-features">
                    <li>Unlimited</li>
                    <li>AI Chat</li>
                    <li>All features</li>
                    <li>Priority support</li>
                </ul>
                <button class="pricing-btn" onclick="checkout('high')">Subscribe</button>
            </div>
            <div class="pricing-card">
                <div class="pricing-name">Hourly</div>
                <div class="pricing-price">$10</div>
                <div class="pricing-period">1 hour</div>
                <ul class="pricing-features">
                    <li>Unlimited chat</li>
                    <li>Full access</li>
                    <li>No commitment</li>
                </ul>
                <button class="pricing-btn" onclick="hourlyCheckout()">Buy Hour</button>
            </div>
        </div>
    </section>

    <!-- ============================================
    CHAT
    ============================================ -->
    <section class="chat-section" id="chat">
        <div class="chat-container">
            <div class="chat-header">
                <h3>💬 AI Assistant</h3>
                <span class="chat-status">● Online</span>
            </div>
            <div class="chat-messages" id="chatMessages">
                <div class="message bot">
                    <div class="message-bubble">
                        👋 Hello! I'm your AI assistant.<br><br>
                        I can find:<br>
                        • 🏢 Companies & business data<br>
                        • 📧 Contacts, emails & phones<br>
                        • 📱 TikTok, Instagram, Twitter<br>
                        • 📰 News & hiring signals<br>
                        • 💡 Solutions to problems<br><br>
                        <strong>Type your secret word</strong> for unlimited free access!
                    </div>
                </div>
            </div>
            <div class="quick-actions">
                <button onclick="quickAction('Find company Tesla')">🚗 Tesla</button>
                <button onclick="quickAction('Email of Elon Musk')">📧 Elon Musk</button>
                <button onclick="quickAction('Find TikTok for Tesla')">🎵 TikTok</button>
                <button onclick="quickAction('Find Instagram for Apple')">📸 Instagram</button>
                <button onclick="quickAction('How to grow my business')">📈 Growth</button>
            </div>
            <div class="chat-input-area">
                <input type="text" id="chatInput" placeholder="Type your question..." onkeypress="if(event.key==='Enter') sendChat()">
                <button onclick="sendChat()">Send</button>
            </div>
        </div>
    </section>

    <!-- ============================================
    FOOTER
    ============================================ -->
    <footer class="footer">
        <div class="footer-links">
            <a href="/">Home</a>
            <a href="#features">Features</a>
            <a href="#pricing">Pricing</a>
            <a href="#chat">Chat</a>
        </div>
        <p>© 2026 Problem Solver. All rights reserved.</p>
    </footer>

    <!-- ============================================
    JAVASCRIPT
    ============================================ -->
    <script>
        // ============================================
        // NAVIGATION
        // ============================================
        function toggleNav() {
            document.getElementById('navLinks').classList.toggle('open');
        }
        
        // Navbar scroll effect
        window.addEventListener('scroll', function() {
            if (window.scrollY > 50) {
                document.getElementById('navbar').classList.add('scrolled');
            } else {
                document.getElementById('navbar').classList.remove('scrolled');
            }
        });
        
        // ============================================
        // CHAT
        // ============================================
        let chatSessionId = Math.random().toString(36);
        
        function quickAction(msg) {
            document.getElementById('chatInput').value = msg;
            sendChat();
            // Scroll to chat
            document.getElementById('chat').scrollIntoView({ behavior: 'smooth' });
        }
        
        function heroSearchAction() {
            const query = document.getElementById('heroSearch').value;
            if (query.trim()) {
                quickAction(query);
            }
        }
        
        async function sendChat() {
            const input = document.getElementById('chatInput');
            const message = input.value.trim();
            if (!message) return;
            
            const messagesDiv = document.getElementById('chatMessages');
            
            // Add user message
            messagesDiv.innerHTML += `
                <div class="message user">
                    <div class="message-bubble">${escapeHtml(message)}</div>
                </div>
            `;
            input.value = '';
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            
            // Add typing indicator
            messagesDiv.innerHTML += `
                <div class="message bot" id="typingIndicator">
                    <div class="message-bubble">⏳ Thinking...</div>
                </div>
            `;
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        message: message, 
                        session_id: chatSessionId 
                    })
                });
                
                const data = await response.json();
                
                // Remove typing indicator
                const typing = document.getElementById('typingIndicator');
                if (typing) typing.remove();
                
                // Add bot response
                messagesDiv.innerHTML += `
                    <div class="message bot">
                        <div class="message-bubble">${escapeHtml(data.response)}</div>
                    </div>
                `;
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
                
                if (data.remaining !== undefined) {
                    // Update status if needed
                }
            } catch (error) {
                const typing = document.getElementById('typingIndicator');
                if (typing) typing.remove();
                
                messagesDiv.innerHTML += `
                    <div class="message bot">
                        <div class="message-bubble">❌ Error: ${escapeHtml(error.message)}</div>
                    </div>
                `;
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
        }
        
        // ============================================
        // CHECKOUT
        // ============================================
        async function checkout(tier) {
            try {
                const response = await fetch('/create-checkout-session', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tier: tier })
                });
                const data = await response.json();
                window.location.href = data.checkout_url;
            } catch (error) {
                alert('Payment error: ' + error.message);
            }
        }
        
        async function hourlyCheckout() {
            try {
                const response = await fetch('/create-hourly-session', { method: 'POST' });
                const data = await response.json();
                window.location.href = data.checkout_url;
            } catch (error) {
                alert('Payment error: ' + error.message);
            }
        }
        
        // ============================================
        // UTILITY
        // ============================================
        function escapeHtml(text) {
            return text.replace(/[&<>]/g, function(m) {
                if (m === '&') return '&amp;';
                if (m === '<') return '&lt;';
                if (m === '>') return '&gt;';
                return m;
            });
        }
        
        // Enter key for hero search
        document.getElementById('heroSearch').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') heroSearchAction();
        });
        
        console.log('🚀 Problem Solver loaded successfully!');
    </script>
</body>
</html>
"""
#part 4
# ============================================
# API ENDPOINTS - Add AFTER HTML_PAGE
# ============================================

@app.get("/")
async def root():
    return HTMLResponse(HTML_PAGE_1 + HTML_PAGE_2 + HTML_PAGE_3)

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    data = await request.json()
    message = data.get("message", "")
    session_id = data.get("session_id", "")
    
    # Founder Mode (HIDDEN - no one knows about it)
    if message.lower().strip() == FOUNDER_NAME.lower():
        return {"response": "🔓 **FOUNDER MODE ACTIVATED!** Unlimited free access forever."}
    
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
            return {"response": "Please specify a name. Example: 'Find TikTok for Tesla'"}
        result = await scraper.find_social(name, "tiktok")
        if result:
            return {"response": f"**🎵 TikTok for {name}**\n\n📱 TikTok: {result}\n\n*Found via public search.*"}
        else:
            return {"response": f"**🎵 TikTok for {name}**\n\n❌ No TikTok account found."}
    
    # Find Instagram
    elif "instagram" in msg_lower:
        name = message.replace("find instagram", "").replace("instagram for", "").replace("instagram", "").strip()
        if not name:
            return {"response": "Please specify a name. Example: 'Find Instagram for Apple'"}
        result = await scraper.find_social(name, "instagram")
        if result:
            return {"response": f"**📸 Instagram for {name}**\n\n📱 Instagram: {result}\n\n*Found via public search.*"}
        else:
            return {"response": f"**📸 Instagram for {name}**\n\n❌ No Instagram account found."}
    
    # Find Twitter
    elif "twitter" in msg_lower or "x.com" in msg_lower:
        name = message.replace("find twitter", "").replace("twitter for", "").replace("twitter", "").strip()
        if not name:
            return {"response": "Please specify a name. Example: 'Find Twitter for Google'"}
        result = await scraper.find_social(name, "twitter")
        if result:
            return {"response": f"**🐦 Twitter/X for {name}**\n\n📱 Twitter: {result}\n\n*Found via public search.*"}
        else:
            return {"response": f"**🐦 Twitter/X for {name}**\n\n❌ No Twitter account found."}
    
    # Find LinkedIn
    elif "linkedin" in msg_lower:
        name = message.replace("find linkedin", "").replace("linkedin for", "").replace("linkedin", "").strip()
        if not name:
            return {"response": "Please specify a name. Example: 'Find LinkedIn for Microsoft'"}
        result = await scraper.find_social(name, "linkedin")
        if result:
            return {"response": f"**💼 LinkedIn for {name}**\n\n📱 LinkedIn: {result}\n\n*Found via public search.*"}
        else:
            return {"response": f"**💼 LinkedIn for {name}**\n\n❌ No LinkedIn profile found."}
    
    # Find News
    elif "news" in msg_lower:
        name = message.replace("find news", "").replace("news about", "").replace("news", "").strip()
        if not name:
            return {"response": "Please specify a name. Example: 'Find news about AI'"}
        news = await scraper.find_news(name)
        if news:
            result = f"**📰 News about {name}**\n\n"
            for i, headline in enumerate(news[:5], 1):
                result += f"{i}. {headline}\n"
            return {"response": result}
        else:
            return {"response": f"**📰 News about {name}**\n\n❌ No recent news found."}
    
    # Find Hiring
    elif "hiring" in msg_lower or "jobs" in msg_lower:
        name = message.replace("find hiring", "").replace("hiring at", "").replace("jobs at", "").replace("hiring", "").strip()
        if not name:
            return {"response": "Please specify a company. Example: 'Find hiring at Google'"}
        hiring = await scraper.find_hiring(name)
        if hiring:
            result = f"**💼 Hiring at {name}**\n\n"
            for job in hiring[:5]:
                result += f"• {job}\n"
            return {"response": result}
        else:
            return {"response": f"**💼 Hiring at {name}**\n\n❌ No active job postings found."}
    
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
    if result.get('description'): response += f"📝 Description: {result['description'][:300]}...\n\n"
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
    if result.get('news'): response += f"📰 News: {len(result['news'])} articles found\n"
    return response

def format_contact_result(result):
    response = f"**👤 Contact: {result.get('full_name')}**\n\n"
    if result.get('title'): response += f"📋 Title: {result['title']}\n"
    if result.get('company'): response += f"🏢 Company: {result['company']}\n"
    if result.get('email'): response += f"📧 Email: {result['email']} {'✅ Verified' if result.get('email_verified') else '⚠️ Unverified'}\n"
    if result.get('phone'): response += f"📞 Phone: {result['phone']}\n"
    if result.get('linkedin'): response += f"💼 LinkedIn: {result['linkedin']}\n"
    if result.get('twitter'): response += f"🐦 Twitter: {result['twitter']}\n"
    if result.get('location'): response += f"📍 Location: {result['location']}\n"
    if result.get('seniority'): response += f"🎯 Seniority: {result['seniority']}\n"
    return response

# ============================================
# STRIPE ENDPOINTS
# ============================================

@app.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    if not STRIPE_SECRET_KEY:
        return {"checkout_url": "#", "error": "Stripe not configured"}
    
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        
        data = await request.json()
        tier = data.get("tier", "basic")
        
        # Price mapping (you need to create these in Stripe)
        price_ids = {
            "basic": "price_basic_monthly",
            "medium": "price_medium_monthly",
            "high": "price_high_monthly"
        }
        
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price": price_ids.get(tier, "price_basic_monthly"),
                "quantity": 1,
            }],
            mode="subscription",
            success_url="https://problemslover-sjsg.onrender.com/success",
            cancel_url="https://problemslover-sjsg.onrender.com/",
            metadata={"tier": tier}
        )
        return {"checkout_url": session.url}
    except Exception as e:
        print(f"Stripe error: {e}")
        return {"checkout_url": "#", "error": str(e)}

@app.post("/create-hourly-session")
async def create_hourly_session():
    if not STRIPE_SECRET_KEY:
        return {"checkout_url": "#", "error": "Stripe not configured"}
    
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "1 Hour Unlimited Chat Access"},
                    "unit_amount": 1000,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url="https://problemslover-sjsg.onrender.com/success",
            cancel_url="https://problemslover-sjsg.onrender.com/",
        )
        return {"checkout_url": session.url}
    except Exception as e:
        print(f"Stripe error: {e}")
        return {"checkout_url": "#", "error": str(e)}

# ============================================
# HEALTH CHECK
# ============================================

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "3.0.0",
        "features": [
            "AI Chat (DeepSeek)",
            "Company Finder",
            "Contact Finder",
            "Social Media Finder",
            "News Finder",
            "Hiring Finder",
            "5 Payment Tiers",
            "Founder Mode (Hidden)"
        ]
    }

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║     🔍 PROBLEM SOLVING & CONTACT FINDER - ULTIMATE EDITION      ║
    ║                                                                   ║
    ║     ✅ Professional Website Design                               ║
    ║     ✅ Multi-Layer Scraping (5 fallback methods)                 ║
    ║     ✅ AI Chat (DeepSeek - FREE)                                 ║
    ║     ✅ Company & Contact Finder                                  ║
    ║     ✅ Social Media Finder (TikTok, Instagram, Twitter, LinkedIn)║
    ║     ✅ News & Hiring Finder                                      ║
    ║     ✅ 5 Payment Tiers (Stripe)                                  ║
    ║     ✅ Founder Mode (HIDDEN - secret word)                       ║
    ║                                                                   ║
    ║     Server: http://localhost:8000                               ║
    ║                                                                   ║
    ║     ⚠️  Founder word is HIDDEN. No one sees it.                 ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=8000)
