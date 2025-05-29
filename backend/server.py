from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import uuid
from datetime import datetime, timedelta
import httpx
import json
from cryptography.fernet import Fernet
import base64
from jose import JWTError, jwt

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI(title="Donation Page Builder API")
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer()
JWT_SECRET = os.environ.get('JWT_SECRET', 'fallback_secret')
ALGORITHM = "HS256"

# Blackbaud Configuration
BB_BASE_URL = "https://api.sky.blackbaud.com/sandbox" if os.environ.get('BB_ENVIRONMENT') == 'sandbox' else "https://api.sky.blackbaud.com"
BB_OAUTH_URL = "https://oauth2.sky.blackbaud.com"

# Encryption setup
def get_encryption_key():
    key = os.environ.get('ENCRYPTION_KEY', 'YourEncryptionKeyHere32BytesLong!')
    return base64.urlsafe_b64encode(key.encode()[:32])

cipher_suite = Fernet(get_encryption_key())

def encrypt_data(data: str) -> str:
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    return cipher_suite.decrypt(encrypted_data.encode()).decode()

# Models
class OrganizationCreate(BaseModel):
    name: str
    admin_email: str
    admin_password: str

class Organization(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    admin_email: str
    admin_password_hash: str
    bb_merchant_id: Optional[str] = None
    bb_access_token: Optional[str] = None
    bb_refresh_token: Optional[str] = None
    test_mode: bool = True  # Organizations start in test mode for safety
    form_settings: Dict = Field(default_factory=lambda: {
        "preset_amounts": [25, 50, 100, 250, 500],
        "custom_amount_enabled": True,
        "required_fields": ["name", "email"],
        "organization_description": "Help us make a difference",
        "thank_you_message": "Thank you for your generous donation!"
    })
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class BBMSCredentials(BaseModel):
    merchant_id: str
    access_token: str

class BBMSOAuthStart(BaseModel):
    merchant_id: str

class BBMSOAuthCallback(BaseModel):
    code: str
    state: str
    merchant_id: str

class DonationRequest(BaseModel):
    amount: float = Field(..., gt=0)
    donor_email: str
    donor_name: str
    org_id: str
    custom_fields: Optional[Dict] = {}

class DonationTransaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    org_id: str
    amount: float
    donor_name: str
    donor_email: str
    status: str = "pending"  # pending, completed, failed, cancelled
    bb_transaction_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    metadata: Dict = Field(default_factory=dict)

class AdminLogin(BaseModel):
    email: str
    password: str

class FormSettings(BaseModel):
    preset_amounts: List[int]
    custom_amount_enabled: bool
    required_fields: List[str]
    organization_description: str
    thank_you_message: str

class TestModeToggle(BaseModel):
    test_mode: bool

# Blackbaud API Client
class BlackbaudClient:
    def __init__(self):
        self.base_url = BB_BASE_URL
        self.oauth_url = BB_OAUTH_URL
        self.app_id = os.environ.get('BB_APP_ID')
        self.app_secret = os.environ.get('BB_APP_SECRET')
        self.payment_subscription_key = os.environ.get('BB_PAYMENT_API_SUBSCRIPTION')
        self.standard_subscription_key = os.environ.get('BB_STANDARD_API_SUBSCRIPTION')

    async def generate_oauth_url(self, state: str, redirect_uri: str) -> str:
        """Generate OAuth2 authorization URL"""
        from urllib.parse import urlencode
        
        params = {
            "client_id": self.app_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": "payments"
        }
        
        query_string = urlencode(params)
        return f"{self.oauth_url}/authorization?{query_string}"

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict:
        """Exchange authorization code for access token"""
        try:
            import base64
            
            # Create basic auth header
            auth_string = f"{self.app_id}:{self.app_secret}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.oauth_url}/token",
                    headers=headers,
                    data=data,
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    logging.error(f"Token exchange failed: {response.status_code} - {response.text}")
                    raise HTTPException(400, f"Failed to exchange code for token: {response.text}")
                
                token_data = response.json()
                logging.info("Successfully exchanged code for access token")
                
                return token_data
                
        except Exception as e:
            logging.error(f"Error exchanging code for token: {e}")
            raise HTTPException(500, f"Token exchange failed: {str(e)}")

    async def refresh_access_token(self, refresh_token: str) -> Dict:
        """Refresh an expired access token"""
        try:
            import base64
            
            # Create basic auth header
            auth_string = f"{self.app_id}:{self.app_secret}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.oauth_url}/token",
                    headers=headers,
                    data=data,
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    logging.error(f"Token refresh failed: {response.status_code} - {response.text}")
                    raise HTTPException(400, f"Failed to refresh token: {response.text}")
                
                token_data = response.json()
                logging.info("Successfully refreshed access token")
                
                return token_data
                
        except Exception as e:
            logging.error(f"Error refreshing token: {e}")
            raise HTTPException(500, f"Token refresh failed: {str(e)}")

    async def test_credentials(self, access_token: str, test_mode: bool = True) -> bool:
        """Test if the provided access token is valid"""
        try:
            base_url = "https://api.sky.blackbaud.com/sandbox" if test_mode else "https://api.sky.blackbaud.com"
            headers = {
                "Bb-Api-Subscription-Key": self.standard_subscription_key,
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/constituent/v1/constituents?limit=1",
                    headers=headers,
                    timeout=30.0
                )
                return response.status_code == 200
        except Exception as e:
            logging.error(f"Error testing Blackbaud credentials: {e}")
            return False

    async def create_payment_checkout(self, donation: DonationRequest, merchant_id: str, access_token: str, test_mode: bool = True) -> Dict:
        """Create a payment checkout session"""
        try:
            base_url = "https://api.sky.blackbaud.com/sandbox" if test_mode else "https://api.sky.blackbaud.com"
            headers = {
                "Bb-Api-Subscription-Key": self.payment_subscription_key,
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Use test URLs for sandbox environment
            return_url = f"https://c44b0daf-083b-41cc-aa42-f9e46f580f6f.preview.emergentagent.com/success"
            cancel_url = f"https://c44b0daf-083b-41cc-aa42-f9e46f580f6f.preview.emergentagent.com/cancel"
            
            checkout_data = {
                "merchant_account_id": merchant_id,
                "amount": {
                    "value": int(donation.amount * 100),  # Convert to cents
                    "currency": "USD"
                },
                "return_url": return_url,
                "cancel_url": cancel_url,
                "metadata": {
                    "donor_email": donation.donor_email,
                    "donor_name": donation.donor_name,
                    "org_id": donation.org_id,
                    "test_mode": "true" if test_mode else "false"
                }
            }
            
            mode_text = "sandbox" if test_mode else "production"
            logging.info(f"Creating checkout in {mode_text} mode for ${donation.amount}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base_url}/payments/v1/checkouts",
                    headers=headers,
                    json=checkout_data,
                    timeout=30.0
                )
                
                if response.status_code != 201:
                    logging.error(f"Checkout creation failed: {response.status_code} - {response.text}")
                    raise HTTPException(400, f"Failed to create checkout: {response.text}")
                
                checkout_response = response.json()
                logging.info(f"Checkout created successfully: {checkout_response.get('id')} in {mode_text} mode")
                
                return checkout_response
                
        except Exception as e:
            logging.error(f"Error creating payment checkout: {e}")
            raise HTTPException(500, f"Checkout creation failed: {str(e)}")

bb_client = BlackbaudClient()

# Helper functions
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[ALGORITHM])
        org_id: str = payload.get("org_id")
        if org_id is None:
            raise HTTPException(401, "Invalid authentication")
        return org_id
    except JWTError:
        raise HTTPException(401, "Invalid authentication")

async def get_organization(org_id: str) -> Organization:
    org_data = await db.organizations.find_one({"id": org_id})
    if not org_data:
        raise HTTPException(404, "Organization not found")
    return Organization(**org_data)

# API Routes
@api_router.post("/organizations/register")
async def register_organization(org_data: OrganizationCreate):
    """Register a new organization"""
    try:
        # Validate input data
        if not org_data.name or not org_data.admin_email or not org_data.admin_password:
            raise HTTPException(400, "Name, email, and password are required")
        
        if len(org_data.admin_password) < 6:
            raise HTTPException(400, "Password must be at least 6 characters long")
        
        # Check if email already exists
        existing = await db.organizations.find_one({"admin_email": org_data.admin_email})
        if existing:
            raise HTTPException(400, "Organization with this email already exists")
        
        # Hash password (simple implementation)
        import hashlib
        password_hash = hashlib.sha256(org_data.admin_password.encode()).hexdigest()
        
        organization = Organization(
            name=org_data.name,
            admin_email=org_data.admin_email,
            admin_password_hash=password_hash
        )
        
        await db.organizations.insert_one(organization.dict())
        
        # Create access token
        access_token = create_access_token({"org_id": organization.id})
        
        return {
            "message": "Organization registered successfully",
            "access_token": access_token,
            "organization": {
                "id": organization.id,
                "name": organization.name,
                "email": organization.admin_email
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Registration error: {e}")
        raise HTTPException(500, f"Registration failed: {str(e)}")

@api_router.post("/organizations/login")
async def login_organization(login_data: AdminLogin):
    """Login for organization admin"""
    try:
        # Validate input data
        if not login_data.email or not login_data.password:
            raise HTTPException(400, "Email and password are required")
        
        import hashlib
        password_hash = hashlib.sha256(login_data.password.encode()).hexdigest()
        
        org_data = await db.organizations.find_one({
            "admin_email": login_data.email,
            "admin_password_hash": password_hash
        })
        
        if not org_data:
            raise HTTPException(401, "Invalid email or password")
        
        access_token = create_access_token({"org_id": org_data["id"]})
        
        return {
            "access_token": access_token,
            "organization": {
                "id": org_data["id"],
                "name": org_data["name"],
                "email": org_data["admin_email"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Login error: {e}")
        raise HTTPException(500, f"Login failed: {str(e)}")

@api_router.post("/organizations/configure-bbms")
async def configure_bbms(
    credentials: BBMSCredentials,
    org_id: str = Depends(verify_token)
):
    """Configure BBMS credentials for organization"""
    # Get organization to check test mode
    organization = await get_organization(org_id)
    
    # Test the credentials first
    is_valid = await bb_client.test_credentials(credentials.access_token, organization.test_mode)
    if not is_valid:
        mode_text = "test" if organization.test_mode else "production"
        raise HTTPException(400, f"Invalid Blackbaud credentials for {mode_text} environment")
    
    # Encrypt and store credentials
    encrypted_token = encrypt_data(credentials.access_token)
    
    await db.organizations.update_one(
        {"id": org_id},
        {
            "$set": {
                "bb_merchant_id": credentials.merchant_id,
                "bb_access_token": encrypted_token,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return {"message": "BBMS credentials configured successfully"}

@api_router.get("/organizations/me")
async def get_my_organization(org_id: str = Depends(verify_token)):
    """Get current organization details"""
    organization = await get_organization(org_id)
    
    # Don't return sensitive data
    return {
        "id": organization.id,
        "name": organization.name,
        "email": organization.admin_email,
        "has_bbms_configured": bool(organization.bb_access_token),
        "test_mode": organization.test_mode,
        "form_settings": organization.form_settings,
        "created_at": organization.created_at
    }

@api_router.put("/organizations/form-settings")
async def update_form_settings(
    settings: FormSettings,
    org_id: str = Depends(verify_token)
):
    """Update organization form settings"""
    await db.organizations.update_one(
        {"id": org_id},
        {
            "$set": {
                "form_settings": settings.dict(),
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return {"message": "Form settings updated successfully"}

@api_router.put("/organizations/test-mode")
async def toggle_test_mode(
    toggle_data: TestModeToggle,
    org_id: str = Depends(verify_token)
):
    """Toggle test mode for organization"""
    await db.organizations.update_one(
        {"id": org_id},
        {
            "$set": {
                "test_mode": toggle_data.test_mode,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    mode_text = "test" if toggle_data.test_mode else "production"
    return {"message": f"Switched to {mode_text} mode successfully"}

@api_router.post("/donations/checkout")
async def create_donation_checkout(donation: DonationRequest):
    """Create a checkout session for donation"""
    # Get organization
    org_data = await db.organizations.find_one({"id": donation.org_id})
    if not org_data:
        raise HTTPException(404, "Organization not found")
    
    organization = Organization(**org_data)
    
    if not organization.bb_access_token or not organization.bb_merchant_id:
        raise HTTPException(400, "Organization has not configured payment processing")
    
    # Decrypt access token
    access_token = decrypt_data(organization.bb_access_token)
    
    # Create checkout session using organization's test mode setting
    checkout_response = await bb_client.create_payment_checkout(
        donation, organization.bb_merchant_id, access_token, organization.test_mode
    )
    
    # Store transaction
    transaction = DonationTransaction(
        session_id=checkout_response.get("id"),
        org_id=donation.org_id,
        amount=donation.amount,
        donor_name=donation.donor_name,
        donor_email=donation.donor_email,
        metadata=donation.custom_fields or {}
    )
    
    await db.transactions.insert_one(transaction.dict())
    
    return {
        "session_id": checkout_response.get("id"),
        "checkout_url": checkout_response.get("checkout_url")
    }

@api_router.get("/donations/status/{session_id}")
async def get_donation_status(session_id: str):
    """Get donation status"""
    transaction = await db.transactions.find_one({"session_id": session_id})
    if not transaction:
        raise HTTPException(404, "Transaction not found")
    
    return {
        "status": transaction["status"],
        "amount": transaction["amount"],
        "donor_name": transaction["donor_name"],
        "created_at": transaction["created_at"]
    }

@api_router.get("/organizations/{org_id}/donation-form")
async def get_donation_form_config(org_id: str):
    """Get donation form configuration for public use"""
    organization = await get_organization(org_id)
    
    return {
        "organization_name": organization.name,
        "description": organization.form_settings.get("organization_description", ""),
        "preset_amounts": organization.form_settings.get("preset_amounts", [25, 50, 100]),
        "custom_amount_enabled": organization.form_settings.get("custom_amount_enabled", True),
        "required_fields": organization.form_settings.get("required_fields", ["name", "email"])
    }

@api_router.get("/organizations/{org_id}/transactions")
async def get_organization_transactions(
    org_id: str,
    current_org: str = Depends(verify_token)
):
    """Get transactions for organization (admin only)"""
    if org_id != current_org:
        raise HTTPException(403, "Access denied")
    
    transactions = await db.transactions.find({"org_id": org_id}).sort("created_at", -1).to_list(100)
    return transactions

# Embed route for iframe
@app.get("/embed/donate/{org_id}")
async def serve_donation_embed(org_id: str):
    """Serve donation form for iframe embedding"""
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Donation Form</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            body {{ margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif; }}
        </style>
    </head>
    <body>
        <div id="donation-root" class="max-w-md mx-auto"></div>
        <script>
            const ORG_ID = '{org_id}';
            const API_BASE = 'https://c44b0daf-083b-41cc-aa42-f9e46f580f6f.preview.emergentagent.com/api';
            
            // Simple donation form implementation
            window.addEventListener('DOMContentLoaded', function() {{
                initDonationForm();
            }});
            
            async function initDonationForm() {{
                try {{
                    const response = await fetch(`${{API_BASE}}/organizations/${{ORG_ID}}/donation-form`);
                    const config = await response.json();
                    renderDonationForm(config);
                }} catch (error) {{
                    console.error('Failed to load form config:', error);
                    document.getElementById('donation-root').innerHTML = '<p class="text-red-500">Failed to load donation form</p>';
                }}
            }}
            
            function renderDonationForm(config) {{
                const root = document.getElementById('donation-root');
                root.innerHTML = `
                    <div class="bg-white rounded-lg shadow-lg p-6">
                        <h2 class="text-2xl font-bold text-gray-800 mb-2">${{config.organization_name}}</h2>
                        <p class="text-gray-600 mb-6">${{config.description}}</p>
                        
                        <form id="donation-form" class="space-y-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">Donation Amount</label>
                                <div class="grid grid-cols-3 gap-2 mb-3">
                                    ${{config.preset_amounts.map(amount => `
                                        <button type="button" class="amount-btn bg-gray-100 hover:bg-blue-100 border border-gray-300 rounded px-3 py-2 text-sm font-medium" data-amount="${{amount}}">
                                            $$${{amount}}
                                        </button>
                                    `).join('')}}
                                </div>
                                ${{config.custom_amount_enabled ? `
                                    <div class="flex items-center space-x-2">
                                        <button type="button" id="custom-btn" class="amount-btn bg-gray-100 hover:bg-blue-100 border border-gray-300 rounded px-3 py-2 text-sm font-medium">
                                            Custom
                                        </button>
                                        <input type="number" id="custom-amount" class="hidden flex-1 border border-gray-300 rounded px-3 py-2 text-sm" placeholder="Enter amount" min="1" step="0.01">
                                    </div>
                                ` : ''}}
                            </div>
                            
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                                <input type="text" id="donor-name" required class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                            </div>
                            
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
                                <input type="email" id="donor-email" required class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                            </div>
                            
                            <button type="submit" id="donate-btn" disabled class="w-full bg-blue-600 text-white font-medium py-3 px-4 rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed">
                                Donate Now
                            </button>
                        </form>
                        
                        <div id="loading" class="hidden text-center py-8">
                            <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                            <p class="mt-2 text-gray-600">Processing your donation...</p>
                        </div>
                    </div>
                `;
                
                setupFormInteractions();
            }}
            
            function setupFormInteractions() {{
                let selectedAmount = null;
                
                // Amount button handlers
                document.querySelectorAll('.amount-btn').forEach(btn => {{
                    btn.addEventListener('click', function() {{
                        document.querySelectorAll('.amount-btn').forEach(b => b.classList.remove('bg-blue-500', 'text-white'));
                        this.classList.add('bg-blue-500', 'text-white');
                        
                        if (this.id === 'custom-btn') {{
                            document.getElementById('custom-amount').classList.remove('hidden');
                            selectedAmount = null;
                        }} else {{
                            document.getElementById('custom-amount').classList.add('hidden');
                            selectedAmount = parseFloat(this.dataset.amount);
                        }}
                        updateDonateButton();
                    }});
                }});
                
                // Custom amount input
                const customAmountInput = document.getElementById('custom-amount');
                if (customAmountInput) {{
                    customAmountInput.addEventListener('input', function() {{
                        selectedAmount = parseFloat(this.value);
                        updateDonateButton();
                    }});
                }}
                
                // Form fields
                document.getElementById('donor-name').addEventListener('input', updateDonateButton);
                document.getElementById('donor-email').addEventListener('input', updateDonateButton);
                
                // Form submission
                document.getElementById('donation-form').addEventListener('submit', handleDonationSubmit);
                
                function updateDonateButton() {{
                    const name = document.getElementById('donor-name').value.trim();
                    const email = document.getElementById('donor-email').value.trim();
                    const donateBtn = document.getElementById('donate-btn');
                    
                    const isValid = selectedAmount > 0 && name && email && email.includes('@');
                    donateBtn.disabled = !isValid;
                }}
                
                async function handleDonationSubmit(e) {{
                    e.preventDefault();
                    
                    const donationData = {{
                        amount: selectedAmount,
                        donor_name: document.getElementById('donor-name').value.trim(),
                        donor_email: document.getElementById('donor-email').value.trim(),
                        org_id: ORG_ID
                    }};
                    
                    // Show loading
                    document.getElementById('donation-form').classList.add('hidden');
                    document.getElementById('loading').classList.remove('hidden');
                    
                    try {{
                        const response = await fetch(`${{API_BASE}}/donations/checkout`, {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json'
                            }},
                            body: JSON.stringify(donationData)
                        }});
                        
                        if (!response.ok) {{
                            throw new Error('Failed to create checkout');
                        }}
                        
                        const result = await response.json();
                        
                        // Redirect to Blackbaud checkout
                        window.top.location.href = result.checkout_url;
                        
                    }} catch (error) {{
                        console.error('Donation failed:', error);
                        alert('Failed to process donation. Please try again.');
                        
                        // Show form again
                        document.getElementById('loading').classList.add('hidden');
                        document.getElementById('donation-form').classList.remove('hidden');
                    }}
                }}
            }}
        </script>
    </body>
    </html>
    """)

# Include router in app
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()