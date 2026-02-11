from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import base64
import httpx
import json
import asyncio
import resend

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Viva Wallet Configuration
VIVA_CLIENT_ID = os.environ.get('VIVA_CLIENT_ID', '')
VIVA_CLIENT_SECRET = os.environ.get('VIVA_CLIENT_SECRET', '')
VIVA_SOURCE_CODE = os.environ.get('VIVA_SOURCE_CODE', '9570')
VIVA_ENVIRONMENT = os.environ.get('VIVA_ENVIRONMENT', 'demo')

VIVA_API_BASE = "https://demo-api.vivapayments.com" if VIVA_ENVIRONMENT == "demo" else "https://api.vivapayments.com"
VIVA_ACCOUNTS_BASE = "https://demo-accounts.vivapayments.com" if VIVA_ENVIRONMENT == "demo" else "https://accounts.vivapayments.com"
VIVA_CHECKOUT_BASE = "https://demo.vivapayments.com" if VIVA_ENVIRONMENT == "demo" else "https://www.vivapayments.com"

# Resend Email Configuration
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
resend.api_key = RESEND_API_KEY

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="X67 Digital Media Groupe API")
api_router = APIRouter(prefix="/api")

# ===================== MODELS =====================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    user_id: str
    email: str
    name: str
    phone: Optional[str] = None
    picture: Optional[str] = None
    role: str = "user"
    created_at: datetime

class AdCreate(BaseModel):
    title: str
    description: str
    category_id: str
    subcategory_id: Optional[str] = None
    city_id: str
    price: Optional[float] = None
    price_type: str = "fixed"  # fixed, negotiable, free
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    details: Optional[Dict[str, Any]] = {}

class AdUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    price_type: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class PaymentCreate(BaseModel):
    ad_id: str
    payment_type: str  # post_ad, boost, promote
    customer_email: str
    customer_name: str

class BannerCreate(BaseModel):
    title: str
    image_url: str
    link_url: Optional[str] = None
    position: str = "homepage"  # homepage, sidebar, category
    is_active: bool = True
    order: int = 0

# ===================== HELPER FUNCTIONS =====================

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token() -> str:
    return str(uuid.uuid4())

# ===================== EMAIL TEMPLATES & FUNCTIONS =====================

def get_email_template(template_type: str, data: dict) -> tuple:
    """Returns (subject, html_content) for email template"""
    
    base_style = """
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; background-color: #050505; color: #F8FAFC; margin: 0; padding: 0; }
        .container { max-width: 600px; margin: 0 auto; padding: 40px 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .logo { font-size: 32px; font-weight: bold; color: #3B82F6; }
        .content { background-color: #0A0A0A; border-radius: 16px; padding: 30px; border: 1px solid rgba(255,255,255,0.1); }
        .title { font-size: 24px; font-weight: bold; color: #fff; margin-bottom: 20px; }
        .text { color: #94A3B8; font-size: 16px; line-height: 1.6; margin-bottom: 20px; }
        .button { display: inline-block; background-color: #3B82F6; color: #fff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; margin-top: 10px; }
        .footer { text-align: center; margin-top: 30px; color: #64748B; font-size: 12px; }
        .highlight { color: #3B82F6; font-weight: 600; }
        .success { color: #10B981; }
        .warning { color: #F59E0B; }
        .badge { display: inline-block; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
        .badge-approved { background-color: rgba(16, 185, 129, 0.2); color: #10B981; }
        .badge-rejected { background-color: rgba(239, 68, 68, 0.2); color: #EF4444; }
        .badge-promoted { background-color: rgba(59, 130, 246, 0.2); color: #3B82F6; }
    </style>
    """
    
    if template_type == "welcome":
        subject = "Bine ai venit pe X67 Digital Media!"
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>{base_style}</head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">X67</div>
                    <p style="color: #64748B; margin: 0;">Digital Media Groupe</p>
                </div>
                <div class="content">
                    <h1 class="title">Bine ai venit, {data.get('name', 'User')}! 🎉</h1>
                    <p class="text">
                        Contul tău a fost creat cu succes pe <span class="highlight">X67 Digital Media</span>.
                    </p>
                    <p class="text">
                        Acum poți:
                    </p>
                    <ul class="text">
                        <li>Publica anunțuri în toate categoriile</li>
                        <li>Promova anunțurile pentru vizibilitate maximă</li>
                        <li>Contacta vânzătorii direct</li>
                    </ul>
                    <p class="text">
                        Publicarea unui anunț costă doar <span class="highlight">2€</span>!
                    </p>
                    <a href="{data.get('site_url', 'https://x67digital.com')}/create-ad" class="button">
                        Publică primul anunț
                    </a>
                </div>
                <div class="footer">
                    <p>© 2026 X67 Digital Media Groupe. Toate drepturile rezervate.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
    elif template_type == "ad_approved":
        subject = f"✅ Anunțul tău a fost aprobat - {data.get('ad_title', 'Anunț')}"
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>{base_style}</head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">X67</div>
                    <p style="color: #64748B; margin: 0;">Digital Media Groupe</p>
                </div>
                <div class="content">
                    <h1 class="title">Anunțul tău a fost aprobat! ✅</h1>
                    <p class="text">
                        Bună, <span class="highlight">{data.get('user_name', 'User')}</span>!
                    </p>
                    <p class="text">
                        Anunțul tău <strong>"{data.get('ad_title', 'Anunț')}"</strong> a fost aprobat și este acum <span class="success">activ</span> pe platformă.
                    </p>
                    <div style="background-color: #121212; border-radius: 8px; padding: 20px; margin: 20px 0;">
                        <p style="color: #64748B; font-size: 14px; margin: 0 0 10px 0;">Detalii anunț:</p>
                        <p style="color: #fff; font-size: 16px; margin: 0;"><strong>{data.get('ad_title', 'Anunț')}</strong></p>
                        <p style="color: #3B82F6; font-size: 18px; margin: 10px 0 0 0;">{data.get('ad_price', 'Preț la cerere')}</p>
                    </div>
                    <p class="text">
                        Vrei să ajungi la mai mulți cumpărători? <span class="highlight">Promovează anunțul</span> pentru doar 5€ și apare pe prima pagină!
                    </p>
                    <a href="{data.get('site_url', 'https://x67digital.com')}/ad/{data.get('ad_id', '')}" class="button">
                        Vezi anunțul
                    </a>
                </div>
                <div class="footer">
                    <p>© 2026 X67 Digital Media Groupe. Toate drepturile rezervate.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
    elif template_type == "ad_rejected":
        subject = f"❌ Anunțul tău a fost respins - {data.get('ad_title', 'Anunț')}"
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>{base_style}</head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">X67</div>
                    <p style="color: #64748B; margin: 0;">Digital Media Groupe</p>
                </div>
                <div class="content">
                    <h1 class="title">Anunțul tău a fost respins ❌</h1>
                    <p class="text">
                        Bună, <span class="highlight">{data.get('user_name', 'User')}</span>!
                    </p>
                    <p class="text">
                        Din păcate, anunțul tău <strong>"{data.get('ad_title', 'Anunț')}"</strong> nu a fost aprobat de echipa noastră.
                    </p>
                    <div style="background-color: rgba(239, 68, 68, 0.1); border-radius: 8px; padding: 20px; margin: 20px 0; border: 1px solid rgba(239, 68, 68, 0.3);">
                        <p style="color: #EF4444; font-size: 14px; margin: 0;">
                            Motivul respingerii poate fi: conținut necorespunzător, informații incomplete sau încălcarea regulamentului platformei.
                        </p>
                    </div>
                    <p class="text">
                        Te rugăm să verifici regulamentul și să încerci din nou cu un anunț actualizat.
                    </p>
                    <a href="{data.get('site_url', 'https://x67digital.com')}/create-ad" class="button">
                        Creează un anunț nou
                    </a>
                </div>
                <div class="footer">
                    <p>© 2026 X67 Digital Media Groupe. Toate drepturile rezervate.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
    elif template_type == "views_milestone":
        milestone = data.get('milestone', 0)
        subject = f"🎉 Anunțul tău a atins {milestone} vizualizări!"
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>{base_style}</head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">X67</div>
                    <p style="color: #64748B; margin: 0;">Digital Media Groupe</p>
                </div>
                <div class="content">
                    <h1 class="title">Felicitări! 🎉</h1>
                    <p class="text">
                        Bună, <span class="highlight">{data.get('user_name', 'User')}</span>!
                    </p>
                    <p class="text">
                        Anunțul tău <strong>"{data.get('ad_title', 'Anunț')}"</strong> tocmai a atins un milestone important!
                    </p>
                    <div style="background-color: #121212; border-radius: 16px; padding: 30px; margin: 20px 0; text-align: center;">
                        <p style="font-size: 64px; margin: 0; color: #3B82F6;">👁️</p>
                        <p style="font-size: 48px; font-weight: bold; color: #fff; margin: 10px 0;">{milestone}</p>
                        <p style="color: #64748B; font-size: 18px; margin: 0;">vizualizări</p>
                    </div>
                    <p class="text">
                        Anunțul tău atrage atenția! Vrei să ajungi la și mai mulți cumpărători?
                    </p>
                    <p class="text">
                        <span class="highlight">Promovează anunțul</span> pentru doar 5€ și apare pe prima pagină!
                    </p>
                    <a href="{data.get('site_url', 'https://x67digital.com')}/ad/{data.get('ad_id', '')}" class="button">
                        Vezi anunțul
                    </a>
                </div>
                <div class="footer">
                    <p>© 2026 X67 Digital Media Groupe. Toate drepturile rezervate.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
    elif template_type == "payment_success":
        payment_type_labels = {
            "post_ad": "Publicare anunț",
            "boost": "Ridicare anunț",
            "promote": "Promovare anunț"
        }
        subject = f"💳 Plată confirmată - {payment_type_labels.get(data.get('payment_type', ''), 'Plată')}"
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>{base_style}</head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">X67</div>
                    <p style="color: #64748B; margin: 0;">Digital Media Groupe</p>
                </div>
                <div class="content">
                    <h1 class="title">Plată confirmată! 💳</h1>
                    <p class="text">
                        Bună, <span class="highlight">{data.get('user_name', 'User')}</span>!
                    </p>
                    <p class="text">
                        Plata ta a fost procesată cu succes.
                    </p>
                    <div style="background-color: #121212; border-radius: 8px; padding: 20px; margin: 20px 0;">
                        <table style="width: 100%; color: #94A3B8;">
                            <tr>
                                <td style="padding: 8px 0;">Tip:</td>
                                <td style="text-align: right; color: #fff;">{payment_type_labels.get(data.get('payment_type', ''), 'Plată')}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0;">Sumă:</td>
                                <td style="text-align: right; color: #10B981; font-size: 18px; font-weight: bold;">{data.get('amount', '0')} €</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0;">Anunț:</td>
                                <td style="text-align: right; color: #fff;">{data.get('ad_title', '-')}</td>
                            </tr>
                        </table>
                    </div>
                    <a href="{data.get('site_url', 'https://x67digital.com')}/ad/{data.get('ad_id', '')}" class="button">
                        Vezi anunțul
                    </a>
                </div>
                <div class="footer">
                    <p>© 2026 X67 Digital Media Groupe. Toate drepturile rezervate.</p>
                </div>
            </div>
        </body>
        </html>
        """
    else:
        subject = "Notificare X67 Digital Media"
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>{base_style}</head>
        <body>
            <div class="container">
                <div class="content">
                    <p class="text">{data.get('message', 'Ai primit o notificare.')}</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    return subject, html

async def send_email_notification(to_email: str, template_type: str, data: dict):
    """Send email notification asynchronously"""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured, skipping email")
        return None
    
    try:
        subject, html_content = get_email_template(template_type, data)
        params = {
            "from": SENDER_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_content
        }
        
        # Run sync SDK in thread to keep FastAPI non-blocking
        email = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Email sent to {to_email}: {template_type}")
        return email.get("id")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return None

async def get_current_user(request: Request) -> Optional[dict]:
    # Check cookie first
    session_token = request.cookies.get("session_token")
    # Then check Authorization header
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.split(" ")[1]
    
    if not session_token:
        return None
    
    session = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
    if not session:
        return None
    
    # Check expiry
    expires_at = session.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None
    
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    return user

async def require_auth(request: Request) -> dict:
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

async def require_admin(request: Request) -> dict:
    user = await require_auth(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# ===================== VIVA WALLET =====================

async def get_viva_access_token() -> str:
    credentials = base64.b64encode(f"{VIVA_CLIENT_ID}:{VIVA_CLIENT_SECRET}".encode()).decode()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{VIVA_ACCOUNTS_BASE}/connect/token",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {credentials}"
            },
            data={"grant_type": "client_credentials"}
        )
        if response.status_code != 200:
            logger.error(f"Viva token error: {response.text}")
            raise HTTPException(status_code=502, detail="Payment service unavailable")
        return response.json()["access_token"]

# ===================== AUTH ENDPOINTS =====================

@api_router.post("/auth/register")
async def register(data: UserCreate):
    existing = await db.users.find_one({"email": data.email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    user_doc = {
        "user_id": user_id,
        "email": data.email,
        "password_hash": hash_password(data.password),
        "name": data.name,
        "phone": data.phone,
        "picture": None,
        "role": "user",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(user_doc)
    
    # Create session
    session_token = generate_token()
    session_doc = {
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_sessions.insert_one(session_doc)
    
    # Send welcome email (non-blocking)
    asyncio.create_task(send_email_notification(
        data.email,
        "welcome",
        {"name": data.name, "site_url": "https://x67digital.com"}
    ))
    
    response = JSONResponse(content={
        "user_id": user_id,
        "email": data.email,
        "name": data.name,
        "role": "user"
    })
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=7*24*60*60,
        path="/"
    )
    return response

@api_router.post("/auth/login")
async def login(data: UserLogin):
    user = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user or user.get("password_hash") != hash_password(data.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create session
    session_token = generate_token()
    session_doc = {
        "user_id": user["user_id"],
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_sessions.insert_one(session_doc)
    
    response = JSONResponse(content={
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "role": user.get("role", "user")
    })
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=7*24*60*60,
        path="/"
    )
    return response

@api_router.post("/auth/google-session")
async def google_session(request: Request):
    """Process Google OAuth session from Emergent Auth"""
    body = await request.json()
    session_id = body.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    
    # Get user data from Emergent Auth
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        auth_data = response.json()
    
    email = auth_data.get("email")
    name = auth_data.get("name")
    picture = auth_data.get("picture")
    emergent_session_token = auth_data.get("session_token")
    
    # Find or create user
    user = await db.users.find_one({"email": email}, {"_id": 0})
    is_new_user = False
    if not user:
        is_new_user = True
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user_doc = {
            "user_id": user_id,
            "email": email,
            "password_hash": None,
            "name": name,
            "phone": None,
            "picture": picture,
            "role": "user",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one(user_doc)
        user = user_doc
    else:
        user_id = user["user_id"]
        # Update picture if changed
        if picture and picture != user.get("picture"):
            await db.users.update_one({"user_id": user_id}, {"$set": {"picture": picture}})
    
    # Create session
    session_token = emergent_session_token or generate_token()
    session_doc = {
        "user_id": user["user_id"],
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_sessions.insert_one(session_doc)
    
    # Send welcome email for new users
    if is_new_user and email:
        asyncio.create_task(send_email_notification(
            email,
            "welcome",
            {"name": name or "User", "site_url": "https://x67digital.com"}
        ))
    
    response = JSONResponse(content={
        "user_id": user["user_id"],
        "email": email,
        "name": name or user.get("name"),
        "picture": picture or user.get("picture"),
        "role": user.get("role", "user")
    })
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=7*24*60*60,
        path="/"
    )
    return response

@api_router.get("/auth/me")
async def get_me(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "phone": user.get("phone"),
        "picture": user.get("picture"),
        "role": user.get("role", "user")
    }

@api_router.post("/auth/logout")
async def logout(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    
    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie(key="session_token", path="/")
    return response

# ===================== CATEGORIES =====================

CATEGORIES = [
    {"id": "escorts", "name": "Escorte", "icon": "heart", "color": "#D946EF", "subcategories": [
        {"id": "escorts_female", "name": "Dame"},
        {"id": "escorts_male", "name": "Domni"},
        {"id": "escorts_trans", "name": "Trans"},
        {"id": "escorts_massage", "name": "Masaj"}
    ]},
    {"id": "real_estate", "name": "Imobiliare", "icon": "home", "color": "#10B981", "subcategories": [
        {"id": "apartments_sale", "name": "Apartamente de vânzare"},
        {"id": "apartments_rent", "name": "Apartamente de închiriat"},
        {"id": "apt_1_room_sale", "name": "Garsoniere de vânzare"},
        {"id": "apt_1_room_rent", "name": "Garsoniere de închiriat"},
        {"id": "apt_2_rooms_sale", "name": "2 camere de vânzare"},
        {"id": "apt_2_rooms_rent", "name": "2 camere de închiriat"},
        {"id": "apt_3_rooms_sale", "name": "3 camere de vânzare"},
        {"id": "apt_3_rooms_rent", "name": "3 camere de închiriat"},
        {"id": "apt_4_rooms_sale", "name": "4+ camere de vânzare"},
        {"id": "apt_4_rooms_rent", "name": "4+ camere de închiriat"},
        {"id": "houses_sale", "name": "Case de vânzare"},
        {"id": "houses_rent", "name": "Case de închiriat"},
        {"id": "land", "name": "Terenuri"},
        {"id": "commercial", "name": "Spații comerciale"},
        {"id": "offices", "name": "Birouri"},
        {"id": "garages", "name": "Garaje / Parcări"}
    ]},
    {"id": "cars", "name": "Auto", "icon": "car", "color": "#3B82F6", "subcategories": [
        {"id": "cars_sale", "name": "Autoturisme"},
        {"id": "motorcycles", "name": "Motociclete"},
        {"id": "scooters", "name": "Scutere / ATV"},
        {"id": "trucks", "name": "Autoutilitare"},
        {"id": "buses", "name": "Autobuze / Microbuze"},
        {"id": "trailers", "name": "Rulote / Remorci"},
        {"id": "car_parts", "name": "Piese auto"},
        {"id": "wheels_tires", "name": "Jante / Anvelope"},
        {"id": "car_audio", "name": "Audio / Navigație"},
        {"id": "car_services", "name": "Service auto"}
    ]},
    {"id": "jobs", "name": "Locuri de muncă", "icon": "briefcase", "color": "#F59E0B", "subcategories": [
        {"id": "jobs_driver", "name": "Șofer / Curier / Livrator"},
        {"id": "jobs_it", "name": "IT / Programare / Web"},
        {"id": "jobs_sales", "name": "Vânzări / Marketing"},
        {"id": "jobs_finance", "name": "Contabilitate / Financiar"},
        {"id": "jobs_admin", "name": "Administrativ / Secretariat"},
        {"id": "jobs_hr", "name": "Resurse Umane"},
        {"id": "jobs_construction", "name": "Construcții / Instalații"},
        {"id": "jobs_production", "name": "Producție / Fabrică"},
        {"id": "jobs_horeca", "name": "HoReCa / Turism"},
        {"id": "jobs_medical", "name": "Medical / Farmacie"},
        {"id": "jobs_education", "name": "Educație / Training"},
        {"id": "jobs_beauty", "name": "Frumusețe / Fitness"},
        {"id": "jobs_security", "name": "Pază / Securitate"},
        {"id": "jobs_cleaning", "name": "Curățenie / Menaj"},
        {"id": "jobs_agriculture", "name": "Agricultură / Zootehnie"},
        {"id": "jobs_part_time", "name": "Part-time"},
        {"id": "jobs_remote", "name": "Remote / Work from home"},
        {"id": "jobs_freelance", "name": "Freelance"},
        {"id": "jobs_internship", "name": "Stagii / Internship"},
        {"id": "jobs_abroad", "name": "Muncă în străinătate"}
    ]},
    {"id": "electronics", "name": "Electronice", "icon": "smartphone", "color": "#8B5CF6", "subcategories": [
        {"id": "phones", "name": "Telefoane mobile"},
        {"id": "tablets", "name": "Tablete"},
        {"id": "laptops", "name": "Laptopuri"},
        {"id": "computers", "name": "Calculatoare / Desktop"},
        {"id": "monitors", "name": "Monitoare"},
        {"id": "printers", "name": "Imprimante / Scanere"},
        {"id": "gaming", "name": "Console / Gaming"},
        {"id": "tv", "name": "Televizoare"},
        {"id": "audio", "name": "Audio / Boxe / Căști"},
        {"id": "cameras", "name": "Camere foto / Video"},
        {"id": "smartwatch", "name": "Smartwatch / Wearables"},
        {"id": "accessories_elec", "name": "Accesorii electronice"}
    ]},
    {"id": "fashion", "name": "Modă", "icon": "shirt", "color": "#EC4899", "subcategories": [
        {"id": "women_clothing", "name": "Îmbrăcăminte femei"},
        {"id": "men_clothing", "name": "Îmbrăcăminte bărbați"},
        {"id": "kids_clothing", "name": "Îmbrăcăminte copii"},
        {"id": "shoes_women", "name": "Încălțăminte femei"},
        {"id": "shoes_men", "name": "Încălțăminte bărbați"},
        {"id": "shoes_kids", "name": "Încălțăminte copii"},
        {"id": "bags", "name": "Genți / Rucsacuri"},
        {"id": "watches", "name": "Ceasuri"},
        {"id": "jewelry", "name": "Bijuterii"},
        {"id": "accessories_fashion", "name": "Accesorii modă"}
    ]},
    {"id": "services", "name": "Servicii", "icon": "wrench", "color": "#06B6D4", "subcategories": [
        {"id": "construction", "name": "Construcții / Renovări"},
        {"id": "plumbing", "name": "Instalații sanitare"},
        {"id": "electrical", "name": "Electricieni"},
        {"id": "cleaning_service", "name": "Curățenie"},
        {"id": "moving", "name": "Mutări / Transport"},
        {"id": "auto_service", "name": "Service auto"},
        {"id": "it_services", "name": "IT / Web / Design"},
        {"id": "legal", "name": "Juridice / Consultanță"},
        {"id": "accounting", "name": "Contabilitate"},
        {"id": "events_service", "name": "Evenimente / Organizări"},
        {"id": "photo_video", "name": "Foto / Video"},
        {"id": "lessons", "name": "Meditații / Cursuri"},
        {"id": "beauty_service", "name": "Frumusețe / Coafură"},
        {"id": "health_service", "name": "Sănătate / Masaj"},
        {"id": "pet_service", "name": "Servicii animale"}
    ]},
    {"id": "animals", "name": "Animale", "icon": "dog", "color": "#84CC16", "subcategories": [
        {"id": "dogs", "name": "Câini"},
        {"id": "cats", "name": "Pisici"},
        {"id": "birds", "name": "Păsări"},
        {"id": "fish_aquarium", "name": "Pești / Acvarii"},
        {"id": "rodents", "name": "Rozătoare"},
        {"id": "reptiles", "name": "Reptile"},
        {"id": "horses", "name": "Cai"},
        {"id": "farm_animals", "name": "Animale de fermă"},
        {"id": "pet_food", "name": "Hrană animale"},
        {"id": "pet_accessories", "name": "Accesorii animale"}
    ]}
]

# Romanian cities
ROMANIAN_CITIES = [
    {"id": "bucuresti", "name": "București", "county": "București"},
    {"id": "cluj", "name": "Cluj-Napoca", "county": "Cluj"},
    {"id": "timisoara", "name": "Timișoara", "county": "Timiș"},
    {"id": "iasi", "name": "Iași", "county": "Iași"},
    {"id": "constanta", "name": "Constanța", "county": "Constanța"},
    {"id": "craiova", "name": "Craiova", "county": "Dolj"},
    {"id": "brasov", "name": "Brașov", "county": "Brașov"},
    {"id": "galati", "name": "Galați", "county": "Galați"},
    {"id": "ploiesti", "name": "Ploiești", "county": "Prahova"},
    {"id": "oradea", "name": "Oradea", "county": "Bihor"},
    {"id": "braila", "name": "Brăila", "county": "Brăila"},
    {"id": "arad", "name": "Arad", "county": "Arad"},
    {"id": "pitesti", "name": "Pitești", "county": "Argeș"},
    {"id": "sibiu", "name": "Sibiu", "county": "Sibiu"},
    {"id": "bacau", "name": "Bacău", "county": "Bacău"},
    {"id": "targu_mures", "name": "Târgu Mureș", "county": "Mureș"},
    {"id": "baia_mare", "name": "Baia Mare", "county": "Maramureș"},
    {"id": "buzau", "name": "Buzău", "county": "Buzău"},
    {"id": "botosani", "name": "Botoșani", "county": "Botoșani"},
    {"id": "satu_mare", "name": "Satu Mare", "county": "Satu Mare"},
    {"id": "ramnicu_valcea", "name": "Râmnicu Vâlcea", "county": "Vâlcea"},
    {"id": "drobeta", "name": "Drobeta-Turnu Severin", "county": "Mehedinți"},
    {"id": "suceava", "name": "Suceava", "county": "Suceava"},
    {"id": "piatra_neamt", "name": "Piatra Neamț", "county": "Neamț"},
    {"id": "targu_jiu", "name": "Târgu Jiu", "county": "Gorj"},
    {"id": "tulcea", "name": "Tulcea", "county": "Tulcea"},
    {"id": "resita", "name": "Reșița", "county": "Caraș-Severin"},
    {"id": "focsani", "name": "Focșani", "county": "Vrancea"},
    {"id": "bistrita", "name": "Bistrița", "county": "Bistrița-Năsăud"},
    {"id": "calarasi", "name": "Călărași", "county": "Călărași"},
    {"id": "giurgiu", "name": "Giurgiu", "county": "Giurgiu"},
    {"id": "alba_iulia", "name": "Alba Iulia", "county": "Alba"},
    {"id": "deva", "name": "Deva", "county": "Hunedoara"},
    {"id": "hunedoara", "name": "Hunedoara", "county": "Hunedoara"},
    {"id": "zalau", "name": "Zalău", "county": "Sălaj"},
    {"id": "sfantu_gheorghe", "name": "Sfântu Gheorghe", "county": "Covasna"},
    {"id": "vaslui", "name": "Vaslui", "county": "Vaslui"},
    {"id": "alexandria", "name": "Alexandria", "county": "Teleorman"},
    {"id": "targoviste", "name": "Târgoviște", "county": "Dâmbovița"},
    {"id": "slobozia", "name": "Slobozia", "county": "Ialomița"},
    {"id": "miercurea_ciuc", "name": "Miercurea Ciuc", "county": "Harghita"}
]

# Car brands and models
CAR_BRANDS = {
    "bmw": {"name": "BMW", "models": ["Seria 1", "Seria 2", "Seria 3", "Seria 4", "Seria 5", "Seria 7", "X1", "X3", "X5", "X6", "X7", "i3", "i4", "iX"]},
    "mercedes": {"name": "Mercedes-Benz", "models": ["Clasa A", "Clasa B", "Clasa C", "Clasa E", "Clasa S", "GLA", "GLB", "GLC", "GLE", "GLS", "EQC", "EQS"]},
    "audi": {"name": "Audi", "models": ["A1", "A3", "A4", "A5", "A6", "A7", "A8", "Q2", "Q3", "Q5", "Q7", "Q8", "e-tron"]},
    "volkswagen": {"name": "Volkswagen", "models": ["Polo", "Golf", "Passat", "Arteon", "T-Roc", "Tiguan", "Touareg", "ID.3", "ID.4"]},
    "toyota": {"name": "Toyota", "models": ["Yaris", "Corolla", "Camry", "RAV4", "Land Cruiser", "C-HR", "Prius", "Supra"]},
    "ford": {"name": "Ford", "models": ["Fiesta", "Focus", "Mondeo", "Puma", "Kuga", "Explorer", "Mustang", "Ranger"]},
    "opel": {"name": "Opel", "models": ["Corsa", "Astra", "Insignia", "Crossland", "Grandland", "Mokka"]},
    "renault": {"name": "Renault", "models": ["Clio", "Megane", "Talisman", "Captur", "Kadjar", "Koleos", "Zoe"]},
    "dacia": {"name": "Dacia", "models": ["Sandero", "Logan", "Duster", "Spring", "Jogger"]},
    "skoda": {"name": "Škoda", "models": ["Fabia", "Scala", "Octavia", "Superb", "Kamiq", "Karoq", "Kodiaq", "Enyaq"]},
    "hyundai": {"name": "Hyundai", "models": ["i10", "i20", "i30", "Tucson", "Santa Fe", "Kona", "Ioniq"]},
    "kia": {"name": "Kia", "models": ["Picanto", "Rio", "Ceed", "Stonic", "Sportage", "Sorento", "EV6"]},
    "peugeot": {"name": "Peugeot", "models": ["208", "308", "508", "2008", "3008", "5008", "e-208"]},
    "fiat": {"name": "Fiat", "models": ["500", "Panda", "Tipo", "500X", "500L"]},
    "honda": {"name": "Honda", "models": ["Jazz", "Civic", "Accord", "HR-V", "CR-V", "e"]},
    "nissan": {"name": "Nissan", "models": ["Micra", "Juke", "Qashqai", "X-Trail", "Leaf", "Ariya"]},
    "mazda": {"name": "Mazda", "models": ["Mazda2", "Mazda3", "Mazda6", "CX-3", "CX-30", "CX-5", "MX-5"]},
    "volvo": {"name": "Volvo", "models": ["S60", "S90", "V60", "V90", "XC40", "XC60", "XC90"]},
    "porsche": {"name": "Porsche", "models": ["718", "911", "Taycan", "Panamera", "Macan", "Cayenne"]},
    "tesla": {"name": "Tesla", "models": ["Model 3", "Model S", "Model X", "Model Y"]}
}

# Motorcycle brands and models
MOTO_BRANDS = {
    "honda_moto": {"name": "Honda", "models": ["CBR600RR", "CBR1000RR", "CB650R", "CB500F", "Africa Twin", "Gold Wing", "Rebel 500", "Forza 350", "PCX125", "SH150"]},
    "yamaha": {"name": "Yamaha", "models": ["YZF-R1", "YZF-R6", "MT-09", "MT-07", "Tracer 900", "Tenere 700", "XMAX 300", "NMAX 125", "XSR700"]},
    "kawasaki": {"name": "Kawasaki", "models": ["Ninja ZX-10R", "Ninja 650", "Z900", "Z650", "Versys 650", "Vulcan S", "Z400"]},
    "suzuki_moto": {"name": "Suzuki", "models": ["GSX-R1000", "GSX-R750", "GSX-S750", "V-Strom 650", "SV650", "Burgman 400", "Hayabusa"]},
    "bmw_moto": {"name": "BMW", "models": ["S1000RR", "R1250GS", "F900R", "F850GS", "R nineT", "K1600GT", "C400X", "CE 04"]},
    "ducati": {"name": "Ducati", "models": ["Panigale V4", "Streetfighter V4", "Monster", "Multistrada", "Scrambler", "Diavel", "Hypermotard"]},
    "ktm": {"name": "KTM", "models": ["Duke 390", "Duke 690", "Duke 890", "RC 390", "Adventure 390", "Adventure 890", "Super Duke 1290"]},
    "harley": {"name": "Harley-Davidson", "models": ["Street Glide", "Road King", "Sportster S", "Fat Boy", "Iron 883", "Street Bob", "Pan America"]},
    "triumph": {"name": "Triumph", "models": ["Street Triple", "Speed Triple", "Tiger 900", "Bonneville T120", "Trident 660", "Rocket 3"]},
    "aprilia": {"name": "Aprilia", "models": ["RSV4", "Tuono V4", "RS 660", "Tuono 660", "SR GT", "SXR 160"]},
    "mv_agusta": {"name": "MV Agusta", "models": ["F3", "Brutale", "Dragster", "Superveloce", "Turismo Veloce"]},
    "vespa": {"name": "Vespa", "models": ["Primavera 125", "GTS 300", "Sprint 150", "Elettrica"]},
    "piaggio": {"name": "Piaggio", "models": ["Beverly 300", "MP3 500", "Medley 150", "Liberty 125"]},
    "kymco": {"name": "Kymco", "models": ["AK 550", "Downtown 350", "Agility 125", "Like 150"]},
    "sym": {"name": "SYM", "models": ["Maxsym 400", "Joymax Z", "Symphony 125", "Fiddle III"]}
}

@api_router.get("/categories")
async def get_categories():
    return CATEGORIES

@api_router.get("/cities")
async def get_cities():
    return ROMANIAN_CITIES

@api_router.get("/car-brands")
async def get_car_brands():
    return CAR_BRANDS

@api_router.get("/moto-brands")
async def get_moto_brands():
    return MOTO_BRANDS

# ===================== ADS ENDPOINTS =====================

@api_router.post("/ads")
async def create_ad(request: Request):
    user = await require_auth(request)
    body = await request.json()
    
    ad_id = f"ad_{uuid.uuid4().hex[:12]}"
    ad_doc = {
        "ad_id": ad_id,
        "user_id": user["user_id"],
        "title": body.get("title"),
        "description": body.get("description"),
        "category_id": body.get("category_id"),
        "subcategory_id": body.get("subcategory_id"),
        "city_id": body.get("city_id"),
        "price": body.get("price"),
        "price_type": body.get("price_type", "fixed"),
        "contact_phone": body.get("contact_phone"),
        "contact_email": body.get("contact_email", user["email"]),
        "images": body.get("images", []),
        "details": body.get("details", {}),
        "status": "pending",  # pending, active, rejected, expired
        "is_boosted": False,
        "boost_expires_at": None,
        "is_promoted": False,
        "promote_expires_at": None,
        "views": 0,
        "is_paid": False,
        "auto_topup": True,  # Auto-topup enabled by default for all categories
        "topup_rank": 0,
        "last_topup": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.ads.insert_one(ad_doc)
    return {"ad_id": ad_id, "status": "pending", "message": "Ad created, pending payment and approval"}

@api_router.get("/ads")
async def get_ads(
    category_id: Optional[str] = None,
    subcategory_id: Optional[str] = None,
    city_id: Optional[str] = None,
    search: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort: str = "newest",
    page: int = 1,
    limit: int = 20
):
    query = {"status": "active"}
    
    if category_id:
        query["category_id"] = category_id
    if subcategory_id:
        query["subcategory_id"] = subcategory_id
    if city_id:
        query["city_id"] = city_id
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    if min_price is not None:
        query["price"] = query.get("price", {})
        query["price"]["$gte"] = min_price
    if max_price is not None:
        query["price"] = query.get("price", {})
        query["price"]["$lte"] = max_price
    
    # Sort options - topup_rank takes priority (most recent topup first)
    sort_options = {
        "newest": [("topup_rank", -1), ("created_at", -1)],
        "oldest": [("created_at", 1)],
        "price_low": [("topup_rank", -1), ("price", 1)],
        "price_high": [("topup_rank", -1), ("price", -1)],
        "boosted": [("topup_rank", -1), ("is_boosted", -1), ("boost_expires_at", -1), ("created_at", -1)]
    }
    
    sort_by = sort_options.get(sort, sort_options["newest"])
    
    # For escort category, show by topup_rank first
    if category_id == "escorts":
        sort_by = [("topup_rank", -1), ("is_boosted", -1)] + [s for s in sort_by if s[0] not in ["topup_rank", "is_boosted"]]
    
    skip = (page - 1) * limit
    
    ads = await db.ads.find(query, {"_id": 0}).sort(sort_by).skip(skip).limit(limit).to_list(limit)
    total = await db.ads.count_documents(query)
    
    # Enrich with category and city names
    for ad in ads:
        cat = next((c for c in CATEGORIES if c["id"] == ad.get("category_id")), None)
        if cat:
            ad["category_name"] = cat["name"]
            ad["category_color"] = cat["color"]
            if ad.get("subcategory_id"):
                subcat = next((s for s in cat.get("subcategories", []) if s["id"] == ad["subcategory_id"]), None)
                if subcat:
                    ad["subcategory_name"] = subcat["name"]
        
        city = next((c for c in ROMANIAN_CITIES if c["id"] == ad.get("city_id")), None)
        if city:
            ad["city_name"] = city["name"]
    
    return {
        "ads": ads,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }

@api_router.get("/ads/promoted")
async def get_promoted_ads(limit: int = 10):
    """Get promoted ads for homepage"""
    query = {"status": "active", "is_promoted": True}
    ads = await db.ads.find(query, {"_id": 0}).sort([("promote_expires_at", -1)]).limit(limit).to_list(limit)
    
    # Enrich with category info
    for ad in ads:
        cat = next((c for c in CATEGORIES if c["id"] == ad.get("category_id")), None)
        if cat:
            ad["category_name"] = cat["name"]
            ad["category_color"] = cat["color"]
        city = next((c for c in ROMANIAN_CITIES if c["id"] == ad.get("city_id")), None)
        if city:
            ad["city_name"] = city["name"]
    
    return ads

# View milestones for notifications
VIEW_MILESTONES = [100, 500, 1000, 5000, 10000]

@api_router.get("/ads/{ad_id}")
async def get_ad(ad_id: str):
    ad = await db.ads.find_one({"ad_id": ad_id}, {"_id": 0})
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    
    # Get current views before increment
    old_views = ad.get("views", 0)
    new_views = old_views + 1
    
    # Increment views
    await db.ads.update_one({"ad_id": ad_id}, {"$inc": {"views": 1}})
    
    # Check for milestone notifications
    for milestone in VIEW_MILESTONES:
        if old_views < milestone <= new_views:
            # Get ad owner for notification
            owner = await db.users.find_one({"user_id": ad.get("user_id")}, {"_id": 0, "password_hash": 0})
            if owner and owner.get("email"):
                asyncio.create_task(send_email_notification(
                    owner["email"],
                    "views_milestone",
                    {
                        "user_name": owner.get("name", "User"),
                        "ad_title": ad.get("title", "Anunț"),
                        "ad_id": ad_id,
                        "milestone": milestone,
                        "site_url": "https://x67digital.com"
                    }
                ))
                logger.info(f"Views milestone notification sent for ad {ad_id}: {milestone} views")
            break
    
    # Enrich with category and city
    cat = next((c for c in CATEGORIES if c["id"] == ad.get("category_id")), None)
    if cat:
        ad["category_name"] = cat["name"]
        ad["category_color"] = cat["color"]
        if ad.get("subcategory_id"):
            subcat = next((s for s in cat.get("subcategories", []) if s["id"] == ad["subcategory_id"]), None)
            if subcat:
                ad["subcategory_name"] = subcat["name"]
    
    city = next((c for c in ROMANIAN_CITIES if c["id"] == ad.get("city_id")), None)
    if city:
        ad["city_name"] = city["name"]
        ad["city_county"] = city["county"]
    
    # Get user info
    user = await db.users.find_one({"user_id": ad.get("user_id")}, {"_id": 0, "password_hash": 0})
    if user:
        ad["user_name"] = user.get("name")
        ad["user_picture"] = user.get("picture")
    
    return ad

@api_router.put("/ads/{ad_id}")
async def update_ad(ad_id: str, request: Request):
    user = await require_auth(request)
    body = await request.json()
    
    ad = await db.ads.find_one({"ad_id": ad_id}, {"_id": 0})
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    if ad["user_id"] != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    update_fields = {}
    for field in ["title", "description", "price", "price_type", "contact_phone", "contact_email", "details", "images"]:
        if field in body:
            update_fields[field] = body[field]
    
    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.ads.update_one({"ad_id": ad_id}, {"$set": update_fields})
    return {"message": "Ad updated"}

@api_router.delete("/ads/{ad_id}")
async def delete_ad(ad_id: str, request: Request):
    user = await require_auth(request)
    
    ad = await db.ads.find_one({"ad_id": ad_id}, {"_id": 0})
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    if ad["user_id"] != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    await db.ads.delete_one({"ad_id": ad_id})
    return {"message": "Ad deleted"}

@api_router.get("/my-ads")
async def get_my_ads(request: Request, page: int = 1, limit: int = 20):
    user = await require_auth(request)
    
    query = {"user_id": user["user_id"]}
    skip = (page - 1) * limit
    
    ads = await db.ads.find(query, {"_id": 0}).sort([("created_at", -1)]).skip(skip).limit(limit).to_list(limit)
    total = await db.ads.count_documents(query)
    
    return {
        "ads": ads,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }

# ===================== PAYMENTS =====================

PAYMENT_AMOUNTS = {
    "post_ad": 1140,   # 11.40 RON in bani (cents)
    "boost": 700,      # 7.00 RON for boost (ridicare anunț)
    "promote": 2999    # 29.99 RON for promote
}

@api_router.post("/payments/create-order")
async def create_payment_order(request: Request):
    user = await require_auth(request)
    body = await request.json()
    
    ad_id = body.get("ad_id")
    payment_type = body.get("payment_type")  # post_ad, boost, promote
    
    if payment_type not in PAYMENT_AMOUNTS:
        raise HTTPException(status_code=400, detail="Invalid payment type")
    
    amount = PAYMENT_AMOUNTS[payment_type]
    
    # Get Viva access token
    try:
        access_token = await get_viva_access_token()
    except Exception as e:
        logger.error(f"Viva token error: {e}")
        raise HTTPException(status_code=502, detail="Payment service unavailable")
    
    # Create payment order
    order_payload = {
        "amount": amount,
        "customerTrns": f"X67 - {payment_type} - {ad_id}",
        "customer": {
            "email": user["email"],
            "fullName": user["name"],
            "requestLang": "ro"
        },
        "sourceCode": VIVA_SOURCE_CODE,
        "merchantTrns": json.dumps({"ad_id": ad_id, "payment_type": payment_type, "user_id": user["user_id"]})
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{VIVA_API_BASE}/checkout/v2/orders",
            json=order_payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        )
        
        if response.status_code != 200:
            logger.error(f"Viva order error: {response.text}")
            raise HTTPException(status_code=502, detail="Failed to create payment order")
        
        data = response.json()
    
    order_code = data.get("orderCode")
    
    # Store payment record
    payment_doc = {
        "payment_id": f"pay_{uuid.uuid4().hex[:12]}",
        "order_code": order_code,
        "ad_id": ad_id,
        "user_id": user["user_id"],
        "payment_type": payment_type,
        "amount": amount,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.payments.insert_one(payment_doc)
    
    checkout_url = f"{VIVA_CHECKOUT_BASE}/web/checkout?ref={order_code}&lang=ro"
    
    return {
        "order_code": order_code,
        "checkout_url": checkout_url,
        "amount": amount / 100
    }

@api_router.post("/payments/webhook")
async def payment_webhook(request: Request):
    """Handle Viva payment webhooks"""
    body = await request.json()
    
    event_data = body.get("EventData", {})
    transaction_id = event_data.get("TransactionId")
    order_code = event_data.get("OrderCode")
    status_id = event_data.get("StatusId")
    merchant_trns = event_data.get("MerchantTrns", "{}")
    
    try:
        trns_data = json.loads(merchant_trns)
    except:
        trns_data = {}
    
    ad_id = trns_data.get("ad_id")
    payment_type = trns_data.get("payment_type")
    
    logger.info(f"Payment webhook: order={order_code}, status={status_id}, type={payment_type}")
    
    if status_id == "F":  # Finished/Successful
        # Update payment record
        payment = await db.payments.find_one({"order_code": order_code}, {"_id": 0})
        
        await db.payments.update_one(
            {"order_code": order_code},
            {"$set": {
                "status": "completed",
                "transaction_id": transaction_id,
                "completed_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Update ad based on payment type
        if payment_type == "post_ad":
            await db.ads.update_one(
                {"ad_id": ad_id},
                {"$set": {"is_paid": True, "status": "pending"}}  # pending for admin approval
            )
        elif payment_type == "boost":
            await db.ads.update_one(
                {"ad_id": ad_id},
                {"$set": {
                    "is_boosted": True,
                    "boost_expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
                }}
            )
        elif payment_type == "promote":
            await db.ads.update_one(
                {"ad_id": ad_id},
                {"$set": {
                    "is_promoted": True,
                    "promote_expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
                }}
            )
        
        # Send payment confirmation email
        if payment and ad_id:
            ad = await db.ads.find_one({"ad_id": ad_id}, {"_id": 0})
            user = await db.users.find_one({"user_id": payment.get("user_id")}, {"_id": 0})
            
            if user and user.get("email"):
                amount_eur = payment.get("amount", 0) / 100
                asyncio.create_task(send_email_notification(
                    user["email"],
                    "payment_success",
                    {
                        "user_name": user.get("name", "User"),
                        "payment_type": payment_type,
                        "amount": f"{amount_eur:.2f}",
                        "ad_title": ad.get("title", "Anunț") if ad else "Anunț",
                        "ad_id": ad_id,
                        "site_url": "https://x67digital.com"
                    }
                ))
    
    return {"status": "received"}

@api_router.get("/payments/verify/{order_code}")
async def verify_payment(order_code: int, request: Request):
    payment = await db.payments.find_one({"order_code": order_code}, {"_id": 0})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    return {
        "order_code": order_code,
        "status": payment.get("status"),
        "payment_type": payment.get("payment_type"),
        "ad_id": payment.get("ad_id")
    }

# ===================== IMAGE UPLOAD =====================

UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Allowed file types
ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"]
ALLOWED_VIDEO_TYPES = ["video/mp4", "video/webm"]
MAX_VIDEO_DURATION = 15  # seconds

@api_router.post("/upload")
async def upload_image(request: Request, file: UploadFile = File(...)):
    user = await require_auth(request)
    
    # Validate file type
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: JPG, PNG, WebP, GIF")
    
    # Generate unique filename
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = UPLOAD_DIR / filename
    
    # Save file
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
    
    # Return URL - using /api/uploads for proper routing
    return {"url": f"/api/uploads/{filename}", "filename": filename}

@api_router.post("/upload/banner")
async def upload_banner_media(request: Request, file: UploadFile = File(...)):
    """Upload image or video for banners (admin only)"""
    await require_admin(request)
    
    all_allowed = ALLOWED_IMAGE_TYPES + ALLOWED_VIDEO_TYPES
    if file.content_type not in all_allowed:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed: JPG, PNG, WebP, GIF, MP4, WebM")
    
    # Determine file type
    is_video = file.content_type in ALLOWED_VIDEO_TYPES
    ext = file.filename.split(".")[-1] if "." in file.filename else ("mp4" if is_video else "jpg")
    filename = f"banner_{uuid.uuid4().hex}.{ext}"
    filepath = UPLOAD_DIR / filename
    
    # Save file
    content = await file.read()
    
    # Check file size (max 50MB for videos, 10MB for images)
    max_size = 50 * 1024 * 1024 if is_video else 10 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail=f"File too large. Max: {max_size // (1024*1024)}MB")
    
    with open(filepath, "wb") as f:
        f.write(content)
    
    return {
        "url": f"/api/uploads/{filename}", 
        "filename": filename,
        "is_video": is_video,
        "content_type": file.content_type
    }

# ===================== TOPUP / BOOST SYSTEM =====================

# Referral tracking
@api_router.post("/referral/track")
async def track_referral(request: Request):
    """Track referral when someone visits with ref code"""
    body = await request.json()
    ref_code = body.get("ref_code")
    
    if not ref_code:
        return {"tracked": False}
    
    # Find user with this referral code
    referrer = await db.users.find_one({"referral_code": ref_code}, {"_id": 0})
    if referrer:
        # Increment referral count
        await db.users.update_one(
            {"referral_code": ref_code},
            {"$inc": {"referral_count": 1}}
        )
        return {"tracked": True, "referrer_id": referrer["user_id"]}
    
    return {"tracked": False}

@api_router.get("/user/referral-code")
async def get_user_referral_code(request: Request):
    """Get or generate user's referral code"""
    user = await require_auth(request)
    
    # Check if user has a referral code
    if not user.get("referral_code"):
        ref_code = f"ref_{user['user_id'][-8:]}"
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"referral_code": ref_code, "referral_count": 0}}
        )
        return {"referral_code": ref_code, "referral_count": 0}
    
    return {
        "referral_code": user.get("referral_code"),
        "referral_count": user.get("referral_count", 0)
    }

@api_router.post("/ads/{ad_id}/topup")
async def topup_ad(ad_id: str, request: Request):
    """TopUp an ad to appear at the top of its category"""
    user = await require_auth(request)
    
    ad = await db.ads.find_one({"ad_id": ad_id}, {"_id": 0})
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    if ad["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your ad")
    if ad["status"] != "active":
        raise HTTPException(status_code=400, detail="Ad must be active to topup")
    
    # Check cooldown
    last_topup = ad.get("last_topup")
    if last_topup:
        last_topup_time = datetime.fromisoformat(last_topup) if isinstance(last_topup, str) else last_topup
        if last_topup_time.tzinfo is None:
            last_topup_time = last_topup_time.replace(tzinfo=timezone.utc)
        
        # Check if user has referrals (40 min cooldown) or not (60 min cooldown)
        referral_count = user.get("referral_count", 0)
        cooldown_minutes = 40 if referral_count > 0 else 60
        
        time_since_topup = (datetime.now(timezone.utc) - last_topup_time).total_seconds() / 60
        if time_since_topup < cooldown_minutes:
            remaining = int(cooldown_minutes - time_since_topup)
            raise HTTPException(
                status_code=400, 
                detail=f"Poți face TopUp din nou în {remaining} minute"
            )
    
    # Perform topup
    now = datetime.now(timezone.utc)
    await db.ads.update_one(
        {"ad_id": ad_id},
        {"$set": {
            "last_topup": now.isoformat(),
            "topup_rank": now.timestamp()  # Higher = more recent = appears first
        }}
    )
    
    return {"message": "TopUp successful", "next_topup_available_in": 40 if user.get("referral_count", 0) > 0 else 60}

@api_router.post("/ads/{ad_id}/auto-topup")
async def toggle_auto_topup(ad_id: str, request: Request):
    """Enable/disable auto-topup for an ad"""
    user = await require_auth(request)
    body = await request.json()
    
    ad = await db.ads.find_one({"ad_id": ad_id}, {"_id": 0})
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    if ad["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your ad")
    
    enabled = body.get("enabled", True)
    
    await db.ads.update_one(
        {"ad_id": ad_id},
        {"$set": {"auto_topup": enabled}}
    )
    
    return {"message": f"Auto-topup {'enabled' if enabled else 'disabled'}", "auto_topup": enabled}

# ===================== BANNERS / ADS SYSTEM =====================

@api_router.get("/banners")
async def get_banners(position: str = "homepage"):
    query = {"is_active": True, "position": position}
    banners = await db.banners.find(query, {"_id": 0}).sort([("order", 1)]).to_list(100)
    return banners

@api_router.post("/admin/banners")
async def create_banner(request: Request):
    await require_admin(request)
    body = await request.json()
    
    banner_id = f"banner_{uuid.uuid4().hex[:12]}"
    banner_doc = {
        "banner_id": banner_id,
        "title": body.get("title"),
        "media_url": body.get("media_url"),  # Can be image or video
        "media_type": body.get("media_type", "image"),  # "image" or "video"
        "image_url": body.get("media_url"),  # Backwards compatibility
        "link_url": body.get("link_url"),
        "position": body.get("position", "homepage"),
        "is_active": body.get("is_active", True),
        "order": body.get("order", 0),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.banners.insert_one(banner_doc)
    return {"banner_id": banner_id}

@api_router.put("/admin/banners/{banner_id}")
async def update_banner(banner_id: str, request: Request):
    await require_admin(request)
    body = await request.json()
    
    update_fields = {}
    for field in ["title", "media_url", "media_type", "link_url", "position", "is_active", "order"]:
        if field in body:
            update_fields[field] = body[field]
    
    # Keep image_url in sync with media_url for backwards compatibility
    if "media_url" in update_fields:
        update_fields["image_url"] = update_fields["media_url"]
    
    await db.banners.update_one({"banner_id": banner_id}, {"$set": update_fields})
    return {"message": "Banner updated"}

@api_router.delete("/admin/banners/{banner_id}")
async def delete_banner(banner_id: str, request: Request):
    await require_admin(request)
    await db.banners.delete_one({"banner_id": banner_id})
    return {"message": "Banner deleted"}

# ===================== ADMIN ENDPOINTS =====================

@api_router.get("/admin/users")
async def admin_get_users(request: Request, page: int = 1, limit: int = 20):
    await require_admin(request)
    
    skip = (page - 1) * limit
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort([("created_at", -1)]).skip(skip).limit(limit).to_list(limit)
    total = await db.users.count_documents({})
    
    return {
        "users": users,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }

@api_router.put("/admin/users/{user_id}")
async def admin_update_user(user_id: str, request: Request):
    await require_admin(request)
    body = await request.json()
    
    update_fields = {}
    if "role" in body:
        update_fields["role"] = body["role"]
    if "name" in body:
        update_fields["name"] = body["name"]
    if "is_blocked" in body:
        update_fields["is_blocked"] = body["is_blocked"]
    
    await db.users.update_one({"user_id": user_id}, {"$set": update_fields})
    return {"message": "User updated"}

@api_router.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, request: Request):
    admin = await require_admin(request)
    
    # Prevent self-deletion
    if admin["user_id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    # Delete user's ads
    await db.ads.delete_many({"user_id": user_id})
    # Delete user's sessions
    await db.user_sessions.delete_many({"user_id": user_id})
    # Delete user
    await db.users.delete_one({"user_id": user_id})
    
    return {"message": "User and all associated data deleted"}

@api_router.get("/admin/ads")
async def admin_get_ads(request: Request, status: Optional[str] = None, page: int = 1, limit: int = 20):
    await require_admin(request)
    
    query = {}
    if status:
        query["status"] = status
    
    skip = (page - 1) * limit
    ads = await db.ads.find(query, {"_id": 0}).sort([("created_at", -1)]).skip(skip).limit(limit).to_list(limit)
    total = await db.ads.count_documents(query)
    
    return {
        "ads": ads,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }

@api_router.put("/admin/ads/{ad_id}/status")
async def admin_update_ad_status(ad_id: str, request: Request):
    await require_admin(request)
    body = await request.json()
    
    new_status = body.get("status")
    if new_status not in ["pending", "active", "rejected", "expired"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    # Get ad and user info for email
    ad = await db.ads.find_one({"ad_id": ad_id}, {"_id": 0})
    if ad:
        user = await db.users.find_one({"user_id": ad.get("user_id")}, {"_id": 0})
        
        # Send notification email based on status
        if user and user.get("email"):
            price_str = f"{ad.get('price')} €" if ad.get('price') else "Preț la cerere"
            email_data = {
                "user_name": user.get("name", "User"),
                "ad_title": ad.get("title", "Anunț"),
                "ad_price": price_str,
                "ad_id": ad_id,
                "site_url": "https://x67digital.com"
            }
            
            if new_status == "active":
                asyncio.create_task(send_email_notification(
                    user["email"],
                    "ad_approved",
                    email_data
                ))
            elif new_status == "rejected":
                asyncio.create_task(send_email_notification(
                    user["email"],
                    "ad_rejected",
                    email_data
                ))
    
    await db.ads.update_one(
        {"ad_id": ad_id},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": f"Ad status updated to {new_status}"}

@api_router.get("/admin/stats")
async def admin_stats(request: Request):
    await require_admin(request)
    
    total_users = await db.users.count_documents({})
    total_ads = await db.ads.count_documents({})
    pending_ads = await db.ads.count_documents({"status": "pending"})
    active_ads = await db.ads.count_documents({"status": "active"})
    total_payments = await db.payments.count_documents({"status": "completed"})
    
    # Revenue calculation
    pipeline = [
        {"$match": {"status": "completed"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    revenue_result = await db.payments.aggregate(pipeline).to_list(1)
    total_revenue = revenue_result[0]["total"] / 100 if revenue_result else 0
    
    return {
        "total_users": total_users,
        "total_ads": total_ads,
        "pending_ads": pending_ads,
        "active_ads": active_ads,
        "total_payments": total_payments,
        "total_revenue": total_revenue
    }

# ===================== FAVORITES SYSTEM =====================

@api_router.post("/favorites/{ad_id}")
async def add_favorite(ad_id: str, request: Request):
    """Add an ad to user's favorites"""
    user = await require_auth(request)
    
    # Check if ad exists
    ad = await db.ads.find_one({"ad_id": ad_id}, {"_id": 0})
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    
    # Check if already favorited
    existing = await db.favorites.find_one({"user_id": user["user_id"], "ad_id": ad_id})
    if existing:
        raise HTTPException(status_code=400, detail="Already in favorites")
    
    favorite_doc = {
        "favorite_id": f"fav_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "ad_id": ad_id,
        "ad_price": ad.get("price"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.favorites.insert_one(favorite_doc)
    
    # Increment ad's favorite count
    await db.ads.update_one({"ad_id": ad_id}, {"$inc": {"favorites_count": 1}})
    
    return {"message": "Added to favorites", "favorite_id": favorite_doc["favorite_id"]}

@api_router.delete("/favorites/{ad_id}")
async def remove_favorite(ad_id: str, request: Request):
    """Remove an ad from user's favorites"""
    user = await require_auth(request)
    
    result = await db.favorites.delete_one({"user_id": user["user_id"], "ad_id": ad_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Favorite not found")
    
    # Decrement ad's favorite count
    await db.ads.update_one({"ad_id": ad_id}, {"$inc": {"favorites_count": -1}})
    
    return {"message": "Removed from favorites"}

@api_router.get("/favorites")
async def get_favorites(request: Request, page: int = 1, limit: int = 20):
    """Get user's favorite ads"""
    user = await require_auth(request)
    
    skip = (page - 1) * limit
    favorites = await db.favorites.find(
        {"user_id": user["user_id"]}, 
        {"_id": 0}
    ).sort([("created_at", -1)]).skip(skip).limit(limit).to_list(limit)
    
    # Get ad details for each favorite
    result = []
    for fav in favorites:
        ad = await db.ads.find_one({"ad_id": fav["ad_id"]}, {"_id": 0})
        if ad:
            # Check if price dropped
            price_dropped = fav.get("ad_price") and ad.get("price") and ad["price"] < fav["ad_price"]
            result.append({
                **ad,
                "favorited_at": fav["created_at"],
                "original_price": fav.get("ad_price"),
                "price_dropped": price_dropped
            })
    
    total = await db.favorites.count_documents({"user_id": user["user_id"]})
    
    return {
        "favorites": result,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }

@api_router.get("/favorites/check/{ad_id}")
async def check_favorite(ad_id: str, request: Request):
    """Check if an ad is in user's favorites"""
    user = await require_auth(request)
    
    favorite = await db.favorites.find_one({"user_id": user["user_id"], "ad_id": ad_id})
    return {"is_favorite": favorite is not None}

# ===================== MESSAGING SYSTEM =====================

@api_router.post("/messages")
async def send_message(request: Request):
    """Send a message to another user about an ad"""
    user = await require_auth(request)
    body = await request.json()
    
    ad_id = body.get("ad_id")
    receiver_id = body.get("receiver_id")
    content = body.get("content")
    
    if not all([ad_id, receiver_id, content]):
        raise HTTPException(status_code=400, detail="Missing required fields")
    
    # Get or create conversation
    conversation = await db.conversations.find_one({
        "ad_id": ad_id,
        "$or": [
            {"participants": [user["user_id"], receiver_id]},
            {"participants": [receiver_id, user["user_id"]]}
        ]
    })
    
    if not conversation:
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
        ad = await db.ads.find_one({"ad_id": ad_id}, {"_id": 0, "title": 1, "images": 1, "price": 1})
        # Safely get first image or None
        ad_images = ad.get("images", []) if ad else []
        ad_image = ad_images[0] if ad_images else None
        conversation = {
            "conversation_id": conversation_id,
            "ad_id": ad_id,
            "ad_title": ad.get("title") if ad else "Anunț",
            "ad_image": ad_image,
            "ad_price": ad.get("price") if ad else None,
            "participants": [user["user_id"], receiver_id],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.conversations.insert_one(conversation)
    else:
        conversation_id = conversation["conversation_id"]
    
    # Create message
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    message_doc = {
        "message_id": message_id,
        "conversation_id": conversation_id,
        "sender_id": user["user_id"],
        "receiver_id": receiver_id,
        "content": content,
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.messages.insert_one(message_doc)
    
    # Update conversation's last message time
    await db.conversations.update_one(
        {"conversation_id": conversation_id},
        {"$set": {
            "last_message": content[:50] + "..." if len(content) > 50 else content,
            "last_message_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"message_id": message_id, "conversation_id": conversation_id}

@api_router.get("/conversations")
async def get_conversations(request: Request):
    """Get all conversations for the current user"""
    user = await require_auth(request)
    
    conversations = await db.conversations.find(
        {"participants": user["user_id"]},
        {"_id": 0}
    ).sort([("updated_at", -1)]).to_list(100)
    
    # Enrich with other participant info and unread count
    result = []
    for conv in conversations:
        other_user_id = [p for p in conv["participants"] if p != user["user_id"]][0]
        other_user = await db.users.find_one({"user_id": other_user_id}, {"_id": 0, "name": 1, "picture": 1})
        
        unread_count = await db.messages.count_documents({
            "conversation_id": conv["conversation_id"],
            "receiver_id": user["user_id"],
            "is_read": False
        })
        
        result.append({
            **conv,
            "other_user": other_user,
            "unread_count": unread_count
        })
    
    return {"conversations": result}

@api_router.get("/conversations/{conversation_id}")
async def get_conversation_messages(conversation_id: str, request: Request, page: int = 1, limit: int = 50):
    """Get messages in a conversation"""
    user = await require_auth(request)
    
    # Verify user is participant
    conversation = await db.conversations.find_one(
        {"conversation_id": conversation_id, "participants": user["user_id"]},
        {"_id": 0}
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Mark messages as read
    await db.messages.update_many(
        {"conversation_id": conversation_id, "receiver_id": user["user_id"], "is_read": False},
        {"$set": {"is_read": True}}
    )
    
    # Get messages
    skip = (page - 1) * limit
    messages = await db.messages.find(
        {"conversation_id": conversation_id},
        {"_id": 0}
    ).sort([("created_at", -1)]).skip(skip).limit(limit).to_list(limit)
    
    # Get participant info
    other_user_id = [p for p in conversation["participants"] if p != user["user_id"]][0]
    other_user = await db.users.find_one({"user_id": other_user_id}, {"_id": 0, "name": 1, "picture": 1, "user_id": 1})
    
    return {
        "conversation": conversation,
        "other_user": other_user,
        "messages": list(reversed(messages)),  # Oldest first for display
        "page": page
    }

@api_router.get("/messages/unread-count")
async def get_unread_count(request: Request):
    """Get total unread messages count"""
    user = await require_auth(request)
    
    count = await db.messages.count_documents({
        "receiver_id": user["user_id"],
        "is_read": False
    })
    
    return {"unread_count": count}

# ===================== USER ANALYTICS / DASHBOARD =====================

@api_router.get("/analytics/overview")
async def get_analytics_overview(request: Request):
    """Get analytics overview for user's ads"""
    user = await require_auth(request)
    
    # Get user's ads
    ads = await db.ads.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(100)
    
    total_ads = len(ads)
    active_ads = len([a for a in ads if a.get("status") == "active"])
    total_views = sum(a.get("views", 0) for a in ads)
    total_favorites = sum(a.get("favorites_count", 0) for a in ads)
    
    # Get messages count
    total_messages = await db.messages.count_documents({"receiver_id": user["user_id"]})
    
    return {
        "total_ads": total_ads,
        "active_ads": active_ads,
        "total_views": total_views,
        "total_favorites": total_favorites,
        "total_messages": total_messages
    }

@api_router.get("/analytics/views")
async def get_views_analytics(request: Request, days: int = 30):
    """Get views analytics over time"""
    user = await require_auth(request)
    
    # Get user's ads with views
    ads = await db.ads.find(
        {"user_id": user["user_id"]},
        {"_id": 0, "ad_id": 1, "title": 1, "views": 1, "created_at": 1}
    ).to_list(100)
    
    # Sort by views to get top ads
    top_ads = sorted(ads, key=lambda x: x.get("views", 0), reverse=True)[:5]
    
    # Get view events from the last N days (simplified - using ad creation dates)
    # In production, you'd track individual view events
    from_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Generate daily view estimates based on ad age and total views
    daily_views = []
    for i in range(days):
        date = (datetime.now(timezone.utc) - timedelta(days=days-i-1)).strftime("%Y-%m-%d")
        # Estimate daily views (simplified)
        views_estimate = sum(a.get("views", 0) for a in ads) // max(days, 1)
        daily_views.append({"date": date, "views": views_estimate + (i * 2)})  # Slight growth trend
    
    return {
        "top_ads": top_ads,
        "daily_views": daily_views,
        "total_views": sum(a.get("views", 0) for a in ads)
    }

@api_router.get("/analytics/ads-performance")
async def get_ads_performance(request: Request):
    """Get performance metrics for each ad"""
    user = await require_auth(request)
    
    ads = await db.ads.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).to_list(100)
    
    performance = []
    for ad in ads:
        # Get message count for this ad
        msg_count = await db.messages.count_documents({
            "conversation_id": {"$regex": f"^conv_"},
            "receiver_id": user["user_id"]
        })
        
        # Get conversation count for this ad
        conv_count = await db.conversations.count_documents({
            "ad_id": ad["ad_id"],
            "participants": user["user_id"]
        })
        
        performance.append({
            "ad_id": ad["ad_id"],
            "title": ad.get("title"),
            "status": ad.get("status"),
            "views": ad.get("views", 0),
            "favorites": ad.get("favorites_count", 0),
            "conversations": conv_count,
            "created_at": ad.get("created_at"),
            "last_topup": ad.get("last_topup")
        })
    
    # Sort by views
    performance.sort(key=lambda x: x["views"], reverse=True)
    
    return {"ads": performance}

# ===================== ADMIN CATEGORIES MANAGEMENT =====================

@api_router.get("/admin/categories")
async def admin_get_categories(request: Request):
    """Get all categories from database (admin)"""
    await require_admin(request)
    categories = await db.managed_categories.find({}, {"_id": 0}).to_list(100)
    return {"categories": categories}

@api_router.post("/admin/categories")
async def admin_create_category(request: Request):
    """Create a new category"""
    await require_admin(request)
    body = await request.json()
    
    category_id = body.get("id") or f"cat_{uuid.uuid4().hex[:8]}"
    category_doc = {
        "id": category_id,
        "name": body.get("name"),
        "icon": body.get("icon", "folder"),
        "color": body.get("color", "from-blue-600 to-blue-700"),
        "subcategories": body.get("subcategories", []),
        "is_active": body.get("is_active", True),
        "order": body.get("order", 0),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.managed_categories.insert_one(category_doc)
    return {"category_id": category_id}

@api_router.put("/admin/categories/{category_id}")
async def admin_update_category(category_id: str, request: Request):
    """Update a category"""
    await require_admin(request)
    body = await request.json()
    
    update_fields = {}
    for field in ["name", "icon", "color", "subcategories", "is_active", "order"]:
        if field in body:
            update_fields[field] = body[field]
    
    await db.managed_categories.update_one({"id": category_id}, {"$set": update_fields})
    return {"message": "Category updated"}

@api_router.delete("/admin/categories/{category_id}")
async def admin_delete_category(category_id: str, request: Request):
    """Delete a category"""
    await require_admin(request)
    
    # Check if any ads use this category
    ads_count = await db.ads.count_documents({"category_id": category_id})
    if ads_count > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete: {ads_count} ads use this category")
    
    await db.managed_categories.delete_one({"id": category_id})
    return {"message": "Category deleted"}

@api_router.get("/admin/cities")
async def admin_get_cities(request: Request):
    """Get all cities from database (admin)"""
    await require_admin(request)
    cities = await db.managed_cities.find({}, {"_id": 0}).to_list(100)
    return {"cities": cities}

@api_router.post("/admin/cities")
async def admin_create_city(request: Request):
    """Create a new city"""
    await require_admin(request)
    body = await request.json()
    
    city_id = body.get("id") or body.get("name", "").lower().replace(" ", "_")
    city_doc = {
        "id": city_id,
        "name": body.get("name"),
        "region": body.get("region", ""),
        "is_active": body.get("is_active", True),
        "order": body.get("order", 0)
    }
    
    await db.managed_cities.insert_one(city_doc)
    return {"city_id": city_id}

@api_router.put("/admin/cities/{city_id}")
async def admin_update_city(city_id: str, request: Request):
    """Update a city"""
    await require_admin(request)
    body = await request.json()
    
    update_fields = {}
    for field in ["name", "region", "is_active", "order"]:
        if field in body:
            update_fields[field] = body[field]
    
    await db.managed_cities.update_one({"id": city_id}, {"$set": update_fields})
    return {"message": "City updated"}

@api_router.delete("/admin/cities/{city_id}")
async def admin_delete_city(city_id: str, request: Request):
    """Delete a city"""
    await require_admin(request)
    
    ads_count = await db.ads.count_documents({"city_id": city_id})
    if ads_count > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete: {ads_count} ads use this city")
    
    await db.managed_cities.delete_one({"id": city_id})
    return {"message": "City deleted"}

# ===================== STATIC FILES =====================

from fastapi.staticfiles import StaticFiles

# Include router
app.include_router(api_router)

# Mount uploads directory under /api/uploads for proper routing through ingress
app.mount("/api/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
