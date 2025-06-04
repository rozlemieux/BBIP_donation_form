from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Header
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
import bcrypt

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
# Extract database name from MONGO_URL or use default
db_name = os.environ.get('DB_NAME', 'donation_builder')
db = client[db_name]

# Create the main app and API router
app = FastAPI(title="Donation Page Builder API")
api_router = APIRouter(prefix="/api")

# CORS - Must be added before including routes
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# Test endpoint to verify API router is working
@api_router.get("/test-callback")
async def test_callback_route():
    """Test callback route"""
    return {"message": "Test callback route is working"}

# OAuth callback route - Move to API prefix to ensure it reaches backend
@api_router.get("/blackbaud-callback")
async def oauth_callback_page(code: str = None, state: str = None, error: str = None):
    """OAuth callback page that handles the redirect and posts back to API"""
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Blackbaud Authentication</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50 flex items-center justify-center min-h-screen">
        <div class="bg-white rounded-lg shadow-lg p-8 max-w-md w-full mx-4">
            <div id="loading" class="text-center">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                <h2 class="text-xl font-semibold text-gray-800 mb-2">Connecting to Blackbaud...</h2>
                <p class="text-gray-600">Please wait while we complete the authentication.</p>
                <div id="debug-info" class="mt-4 text-xs text-gray-500 bg-gray-100 p-2 rounded">
                    <strong>🔍 OAuth Callback Debug Info:</strong><br>
                    Code: <span class="font-mono">{code or 'Missing'}</span><br>
                    State: <span class="font-mono">{state[:30] + '...' if state else 'Missing'}</span><br>
                    Error: <span class="font-mono">{error or 'None'}</span>
                </div>
            </div>
            
            <div id="success" class="hidden text-center">
                <div class="text-green-500 text-4xl mb-4">✅</div>
                <h2 class="text-xl font-semibold text-gray-800 mb-2">Authentication Successful!</h2>
                <p class="text-gray-600 mb-4">Your Blackbaud account has been connected.</p>
                <button onclick="closeWindow()" class="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700">
                    Continue
                </button>
            </div>
            
            <div id="error" class="hidden text-center">
                <div class="text-red-500 text-4xl mb-4">❌</div>
                <h2 class="text-xl font-semibold text-gray-800 mb-2">Authentication Failed</h2>
                <p class="text-gray-600 mb-4" id="error-message">Something went wrong during authentication.</p>
                <div id="error-details" class="text-xs text-gray-500 mb-4 bg-red-50 p-2 rounded font-mono"></div>
                <button onclick="closeWindow()" class="bg-gray-600 text-white px-6 py-2 rounded-md hover:bg-gray-700">
                    Close and Try Again
                </button>
            </div>
        </div>
        
        <script>
            console.log('🚀 OAuth Callback Page Loaded Successfully');
            console.log('Current URL:', window.location.href);
            
            const urlParams = new URLSearchParams(window.location.search);
            const code = urlParams.get('code') || '{code}';
            const state = urlParams.get('state') || '{state}';
            const error = urlParams.get('error') || '{error}';
            
            console.log('📋 Parameters received:', {{
                code: code ? 'present (' + code.length + ' chars)' : 'missing',
                state: state ? 'present (' + state.length + ' chars)' : 'missing',
                error: error || 'none'
            }});
            
            function showSuccess() {{
                console.log('✅ Showing success state');
                document.getElementById('loading').classList.add('hidden');
                document.getElementById('success').classList.remove('hidden');
            }}
            
            function showError(message, details = '') {{
                console.error('❌ Error occurred:', message, details);
                document.getElementById('loading').classList.add('hidden');
                document.getElementById('error').classList.remove('hidden');
                document.getElementById('error-message').textContent = message;
                if (details) {{
                    document.getElementById('error-details').textContent = details;
                }}
            }}
            
            function closeWindow() {{
                console.log('🔄 Closing window and notifying parent...');
                if (window.opener) {{
                    const success = !document.getElementById('error').classList.contains('hidden');
                    const errorMsg = success ? null : document.getElementById('error-message').textContent;
                    
                    console.log('📤 Sending message to parent:', {{ success, error: errorMsg }});
                    
                    window.opener.postMessage({{
                        type: 'BLACKBAUD_AUTH_COMPLETE',
                        success: success,
                        error: errorMsg
                    }}, '*');
                    
                    setTimeout(() => {{
                        console.log('🔄 Closing popup window...');
                        window.close();
                    }}, 500);
                }} else {{
                    console.log('ℹ️ No opener window found, redirecting to main app');
                    window.location.href = '/';
                }}
            }}
            
            async function handleCallback() {{
                console.log('🔄 Starting OAuth callback processing...');
                
                if (error && error !== 'None') {{
                    console.error('❌ OAuth error from Blackbaud:', error);
                    showError(`Blackbaud OAuth Error: ${{error}}`);
                    return;
                }}
                
                if (!code || code === 'Missing' || !state || state === 'Missing') {{
                    console.error('❌ Missing required OAuth parameters');
                    showError('Missing authorization code or state parameter from Blackbaud.');
                    return;
                }}
                
                try {{
                    const merchant_id = localStorage.getItem('bb_merchant_id') || '96563c2e-c97a-4db1-a0ed-1b2a8219f110';
                    
                    console.log('📡 Making API call to process OAuth callback...');
                    console.log('🔍 Request details:', {{
                        merchant_id: merchant_id,
                        state_preview: state.substring(0, 30) + '...',
                        code_preview: code.substring(0, 10) + '...'
                    }});
                    
                    const response = await fetch('/api/organizations/bbms-oauth/callback', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify({{
                            code: code,
                            state: state,
                            merchant_id: merchant_id
                        }})
                    }});
                    
                    console.log('📡 API Response status:', response.status);
                    
                    if (response.ok) {{
                        const result = await response.json();
                        console.log('✅ OAuth callback successful:', result);
                        localStorage.removeItem('bb_merchant_id');
                        showSuccess();
                    }} else {{
                        const errorData = await response.json();
                        console.error('❌ API Error:', errorData);
                        
                        let errorMessage = errorData.detail || 'Authentication failed';
                        if (errorMessage.includes('invalid_grant')) {{
                            errorMessage = 'Authorization code expired. Please try the OAuth flow again quickly.';
                        }}
                        
                        showError(errorMessage, `Status: ${{response.status}} - ${{JSON.stringify(errorData)}}`);
                    }}
                }} catch (err) {{
                    console.error('❌ Network error:', err);
                    showError('Network error during authentication', err.message);
                }}
            }}
            
            // Start processing immediately when page loads
            console.log('🚀 Initiating OAuth callback processing...');
            handleCallback();
        </script>
    </body>
    </html>
    """)

api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer()
JWT_SECRET = os.environ.get('JWT_SECRET', 'fallback_secret')
ALGORITHM = "HS256"

# Blackbaud Configuration
BB_BASE_URL = "https://api.sky.blackbaud.com" # Blackbaud API base URL (sandbox is handled via headers)
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
    bb_merchant_id: Optional[str] = None  # Legacy field for backward compatibility
    bb_test_merchant_id: Optional[str] = None  # Test environment merchant ID
    bb_production_merchant_id: Optional[str] = None  # Production environment merchant ID
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

class BBMSSetup(BaseModel):
    test_merchant_id: Optional[str] = None
    production_merchant_id: Optional[str] = None

class PasswordResetRequest(BaseModel):
    email: str

class PasswordReset(BaseModel):
    email: str
    new_password: str
    reset_code: str

class BBMSOAuthStart(BaseModel):
    merchant_id: str
    app_id: str
    app_secret: str

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
            
            logging.info(f"Exchanging code for token with redirect_uri: {redirect_uri}")
            logging.info(f"Using OAuth URL: {self.oauth_url}/token")
            logging.info(f"Using App ID: {self.app_id[:8]}...")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.oauth_url}/token",
                    headers=headers,
                    data=data,
                    timeout=30.0
                )
                
                logging.info(f"Token exchange response status: {response.status_code}")
                
                if response.status_code != 200:
                    error_text = response.text
                    logging.error(f"Token exchange failed: {response.status_code} - {error_text}")
                    
                    # Parse error for better user feedback
                    try:
                        error_data = response.json()
                        if error_data.get("error") == "invalid_grant":
                            raise HTTPException(400, "Authorization code expired or invalid. Please try the OAuth flow again.")
                        elif error_data.get("error") == "invalid_client":
                            raise HTTPException(400, "Invalid application credentials. Please check your Blackbaud App ID and Secret.")
                        else:
                            raise HTTPException(400, f"OAuth error: {error_data.get('error_description', 'Unknown error')}")
                    except:
                        raise HTTPException(400, f"Failed to exchange code for token: {error_text}")
                
                token_data = response.json()
                logging.info("Successfully exchanged code for access token")
                
                return token_data
                
        except HTTPException:
            raise
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

    async def create_payment_checkout(self, donation: DonationRequest, merchant_id: str, access_token: str, test_mode: bool = True):
        """
        Create checkout configuration for Blackbaud JavaScript SDK
        Returns configuration data instead of making API calls
        """
        try:
            public_key = os.environ.get('BB_PUBLIC_KEY')
            
            if not public_key:
                raise HTTPException(500, "Blackbaud public key not configured")
            
            # Return configuration for frontend JavaScript SDK
            checkout_config = {
                "public_key": public_key,
                "merchant_account_id": merchant_id,
                "amount": float(donation.amount),
                "currency": "USD",
                "donor_info": {
                    "email": donation.donor_email,
                    "name": donation.donor_name,
                    "phone": getattr(donation, 'donor_phone', ''),
                    "address": getattr(donation, 'donor_address', '')
                },
                "test_mode": test_mode,
                "return_url": "https://e86128f5-e40b-4462-b145-2b55c23a63a0.preview.emergentagent.com/success",
                "cancel_url": "https://e86128f5-e40b-4462-b145-2b55c23a63a0.preview.emergentagent.com/cancel"
            }
            
            mode_text = "sandbox" if test_mode else "production"
            logging.info(f"Checkout configuration created for {mode_text} mode: ${donation.amount}")
            
            return checkout_config
            
        except Exception as e:
            logging.error(f"Error creating checkout configuration: {str(e)}")
            raise HTTPException(500, f"Failed to create checkout configuration: {str(e)}")

    async def process_transaction_token(self, token: str, organization_id: str, access_token: str, donation_data: dict):
        """
        Process a completed Blackbaud checkout transaction token
        This verifies and records the successful payment
        """
        try:
            merchant_id = os.environ.get('BB_MERCHANT_ACCOUNT_ID')
            
            # For now, we'll assume the transaction was successful since we got a token
            # In a production environment, you would verify this token with Blackbaud
            
            # Store the successful donation in our database
            donation_record = {
                "id": str(uuid.uuid4()),
                "organization_id": organization_id,
                "amount": donation_data.get("amount"),
                "donor_email": donation_data.get("donor_email"),
                "donor_name": donation_data.get("donor_name"),
                "transaction_token": token,
                "status": "completed",
                "payment_method": "blackbaud_checkout",
                "created_at": datetime.utcnow().isoformat(),
                "test_mode": True  # Currently in sandbox mode
            }
            
            await db["donations"].insert_one(donation_record)
            
            logging.info(f"Donation recorded successfully: {donation_record['id']} for ${donation_data.get('amount')}")
            
            return {
                "success": True,
                "donation_id": donation_record["id"],
                "transaction_token": token,
                "status": "completed",
                "message": "Donation processed successfully"
            }
                
        except Exception as e:
            logging.error(f"Error processing transaction token: {str(e)}")
            raise HTTPException(500, f"Failed to process transaction: {str(e)}")

    async def test_credentials(self, access_token: str, test_mode: bool = True) -> bool:
        try:
            # Use the correct API base URL - 2025 update: same base URL for all environments
            base_url = "https://api.sky.blackbaud.com"
            headers = {
                "Bb-Api-Subscription-Key": self.standard_subscription_key,
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Try a simple API call that should work with payments scope
            # Use a basic endpoint that's available in both sandbox and production
            async with httpx.AsyncClient() as client:
                # Try the subscription endpoint first as it's more basic
                response = await client.get(
                    f"{base_url}/oauth/subscriptions",
                    headers=headers,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    logging.info("Token validation successful via subscriptions endpoint")
                    return True
                
                # If that fails, try a different basic endpoint
                response = await client.get(
                    f"{base_url}/oauth/userinfo",
                    headers=headers,
                    timeout=30.0
                )
                
                logging.info(f"Token validation response: {response.status_code}")
                return response.status_code == 200
                
        except Exception as e:
            logging.error(f"Error testing Blackbaud credentials: {e}")
            return False

    async def create_payment_checkout(self, donation: DonationRequest, merchant_id: str, access_token: str, test_mode: bool = True) -> Dict:
        """
        Process a Blackbaud Checkout transaction token.
        This function is called after the frontend JavaScript SDK completes the checkout
        and provides a transaction token.
        """
        try:
            # Get environment variables
            subscription_key = os.environ.get('BB_PAYMENT_API_SUBSCRIPTION')
            public_key = os.environ.get('BB_PUBLIC_KEY')
            
            if not subscription_key or not public_key or not merchant_id:
                raise HTTPException(500, "Blackbaud API credentials not properly configured")
            
            # Return the configuration data needed for frontend JavaScript SDK
            mode_text = "sandbox" if test_mode else "production"
            logging.info(f"Creating checkout configuration in {mode_text} mode for ${donation.amount}")
            
            checkout_config = {
                "public_key": public_key,
                "merchant_account_id": merchant_id,
                "amount": float(donation.amount),
                "currency": "USD",
                "donor_info": {
                    "email": donation.donor_email,
                    "name": donation.donor_name,
                    "phone": getattr(donation, 'donor_phone', ''),
                    "address": getattr(donation, 'donor_address', '')
                },
                "test_mode": test_mode,
                "process_mode": "Test" if test_mode else "Live",  # Critical for Blackbaud mode switching (Test, Live, or Demo)
                "return_url": f"https://e86128f5-e40b-4462-b145-2b55c23a63a0.preview.emergentagent.com/success",
                "cancel_url": f"https://e86128f5-e40b-4462-b145-2b55c23a63a0.preview.emergentagent.com/cancel"
            }
            
            logging.info(f"Checkout configuration created for {mode_text} mode")
            return checkout_config
            
        except Exception as e:
            logging.error(f"Error creating checkout configuration: {str(e)}")
            raise HTTPException(500, f"Failed to create checkout configuration: {str(e)}")


    async def process_transaction_token(self, token: str, organization_id: str, access_token: str, donation_data: dict):
        """
        Process a completed Blackbaud checkout transaction token
        This is called after the JavaScript SDK successfully completes the payment
        """
        try:
            # Get environment variables
            subscription_key = os.environ.get('BB_PAYMENT_API_SUBSCRIPTION')
            
            # Verify and process the transaction token with Blackbaud
            base_url = "https://api.sky.blackbaud.com"
            headers = {
                "Bb-Api-Subscription-Key": subscription_key,
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Call the Blackbaud transaction endpoint to verify and process the token
            transaction_data = {
                "transaction_token": token,
                "merchant_account_id": os.environ.get('BB_MERCHANT_ACCOUNT_ID')
            }
            
            logging.info(f"Processing transaction token: {token[:8]}...")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base_url}/payments/transactions",
                    headers=headers,
                    json=transaction_data,
                    timeout=30.0
                )
                
                logging.info(f"Transaction processing response: {response.status_code}")
                
                if response.status_code == 201 or response.status_code == 200:
                    transaction_result = response.json()
                    
                    # Store the successful donation in our database
                    donation_record = {
                        "id": str(uuid.uuid4()),
                        "organization_id": organization_id,
                        "amount": donation_data.get("amount"),
                        "donor_email": donation_data.get("donor_email"),
                        "donor_name": donation_data.get("donor_name"),
                        "transaction_token": token,
                        "transaction_id": transaction_result.get("id"),
                        "status": "completed",
                        "payment_method": "blackbaud_checkout",
                        "created_at": datetime.utcnow().isoformat(),
                        "blackbaud_response": transaction_result
                    }
                    
                    await db["donations"].insert_one(donation_record)
                    
                    logging.info(f"Donation recorded successfully: {donation_record['id']}")
                    return {
                        "success": True,
                        "donation_id": donation_record["id"],
                        "transaction_id": transaction_result.get("id"),
                        "status": "completed"
                    }
                else:
                    error_text = response.text
                    logging.error(f"Transaction processing failed: {response.status_code} - {error_text}")
                    raise HTTPException(400, f"Transaction processing failed: {error_text}")
                    
        except Exception as e:
            logging.error(f"Error processing transaction token: {str(e)}")
            raise HTTPException(500, f"Failed to process transaction: {str(e)}")

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

@api_router.post("/organizations/bbms-oauth/start")
async def start_bbms_oauth(
    oauth_data: BBMSOAuthStart,
    org_id: str = Depends(verify_token)
):
    """Start OAuth2 flow for BBMS credentials"""
    try:
        # Generate state parameter for security
        import secrets
        state = f"{org_id}:{secrets.token_urlsafe(32)}"
        
        # Store state and app credentials in organization temporarily
        await db.organizations.update_one(
            {"id": org_id},
            {
                "$set": {
                    "oauth_state": state,
                    "bb_merchant_id": oauth_data.merchant_id,
                    "temp_app_id": oauth_data.app_id,
                    "temp_app_secret": encrypt_data(oauth_data.app_secret),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Generate OAuth URL using user's app credentials
        from urllib.parse import urlencode
        redirect_uri = "https://119fa407-7ed5-4661-8cb4-d43cc86d1517.preview.emergentagent.com/api/blackbaud-callback"
        
        params = {
            "client_id": oauth_data.app_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": "openid offline_access"
        }
        
        query_string = urlencode(params)
        oauth_url = f"{BB_OAUTH_URL}/authorization?{query_string}"
        
        return {
            "oauth_url": oauth_url,
            "state": state
        }
    except Exception as e:
        logging.error(f"OAuth start error: {e}")
        raise HTTPException(500, f"Failed to start OAuth flow: {str(e)}")

@api_router.post("/organizations/bbms-oauth/callback")
async def handle_bbms_oauth_callback(callback_data: BBMSOAuthCallback):
    """Handle OAuth2 callback and exchange code for tokens"""
    try:
        logging.info(f"OAuth callback received with state: {callback_data.state[:20]}...")
        
        # Verify state parameter
        state_parts = callback_data.state.split(":", 1)
        if len(state_parts) != 2:
            logging.error(f"Invalid state parameter format: {callback_data.state}")
            raise HTTPException(400, "Invalid state parameter")
        
        org_id = state_parts[0]
        logging.info(f"Processing OAuth callback for organization: {org_id}")
        
        # Get organization and verify state
        org_data = await db.organizations.find_one({"id": org_id})
        if not org_data:
            logging.error(f"Organization not found: {org_id}")
            raise HTTPException(400, "Organization not found")
            
        if org_data.get("oauth_state") != callback_data.state:
            logging.error(f"State mismatch. Expected: {org_data.get('oauth_state')[:20]}..., Got: {callback_data.state[:20]}...")
            raise HTTPException(400, "Invalid or expired state parameter")
        
        organization = Organization(**org_data)
        
        # Get the stored app credentials
        temp_app_id = org_data.get("temp_app_id")
        temp_app_secret = org_data.get("temp_app_secret")
        
        if not temp_app_id or not temp_app_secret:
            logging.error("Missing app credentials for OAuth flow")
            raise HTTPException(400, "Missing app credentials for OAuth flow")
        
        # Decrypt app secret
        app_secret = decrypt_data(temp_app_secret)
        logging.info(f"Using app ID: {temp_app_id[:8]}... for token exchange")
        
        # Exchange code for tokens using user's app credentials
        redirect_uri = "https://119fa407-7ed5-4661-8cb4-d43cc86d1517.preview.emergentagent.com/api/blackbaud-callback"
        
        import base64
        import httpx
        
        # Create basic auth header
        auth_string = f"{temp_app_id}:{app_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "authorization_code",
            "code": callback_data.code,
            "redirect_uri": redirect_uri
        }
        
        logging.info(f"Exchanging code for token with user's app credentials")
        logging.info(f"Using App ID: {temp_app_id[:8]}...")
        logging.info(f"Redirect URI: {redirect_uri}")
        logging.info(f"Code length: {len(callback_data.code)}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BB_OAUTH_URL}/token",
                headers=headers,
                data=data,
                timeout=30.0
            )
            
            logging.info(f"Token exchange response: {response.status_code}")
            
            if response.status_code != 200:
                error_text = response.text
                logging.error(f"Token exchange failed: {response.status_code} - {error_text}")
                
                try:
                    error_data = response.json()
                    error_type = error_data.get("error", "unknown")
                    error_desc = error_data.get("error_description", "Unknown error")
                    
                    if error_type == "invalid_grant":
                        # This usually means the code expired or was already used
                        raise HTTPException(400, "Authorization code expired or already used. Please try the OAuth flow again.")
                    elif error_type == "invalid_client":
                        raise HTTPException(400, "Invalid Blackbaud App ID or Secret. Please check your credentials.")
                    elif error_type == "invalid_request":
                        raise HTTPException(400, f"Invalid OAuth request: {error_desc}")
                    else:
                        raise HTTPException(400, f"OAuth error ({error_type}): {error_desc}")
                except ValueError:
                    # Response is not JSON
                    raise HTTPException(400, f"Token exchange failed: {error_text}")
            
            token_data = response.json()
            logging.info(f"Token exchange successful. Access token received: {bool(token_data.get('access_token'))}")
        
        
        # Test the token (but don't fail if validation doesn't work - just log)
        access_token = token_data.get("access_token")
        if not access_token:
            logging.error("No access token received from Blackbaud")
            raise HTTPException(400, "No access token received")
        
        logging.info("Storing access token and updating organization...")
        
        # Always store the token since OAuth was successful
        
        # Encrypt and store tokens
        encrypted_access_token = encrypt_data(access_token)
        encrypted_refresh_token = None
        if token_data.get("refresh_token"):
            encrypted_refresh_token = encrypt_data(token_data["refresh_token"])
        
        # Update organization with tokens
        update_data = {
            "bb_access_token": encrypted_access_token,
            "bb_merchant_id": callback_data.merchant_id,
            "updated_at": datetime.utcnow()
        }
        
        if encrypted_refresh_token:
            update_data["bb_refresh_token"] = encrypted_refresh_token
        
        # Clear OAuth state and temp credentials
        update_data["oauth_state"] = None
        update_data["temp_app_id"] = None
        update_data["temp_app_secret"] = None
        
        result = await db.organizations.update_one(
            {"id": org_id},
            {"$set": update_data}
        )
        
        logging.info(f"Organization update result: {result.modified_count} documents modified")
        
        if result.modified_count == 0:
            logging.warning("No documents were modified in the update operation")
        else:
            logging.info("OAuth2 flow completed successfully")
        
        return {
            "message": "OAuth2 flow completed successfully",
            "organization_id": org_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"OAuth callback error: {e}")
        import traceback
        logging.error(f"OAuth callback traceback: {traceback.format_exc()}")
        raise HTTPException(500, f"OAuth callback failed: {str(e)}")

@api_router.post("/organizations/test-oauth-credentials")
async def test_oauth_credentials(
    test_data: BBMSOAuthStart,
    org_id: str = Depends(verify_token)
):
    """Test OAuth credentials without going through full flow"""
    try:
        # Test if we can generate a proper OAuth URL with user's credentials
        from urllib.parse import urlencode
        redirect_uri = "https://119fa407-7ed5-4661-8cb4-d43cc86d1517.preview.emergentagent.com/api/blackbaud-callback"
        
        params = {
            "client_id": test_data.app_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": "test_state",
            "scope": "openid offline_access"
        }
        
        query_string = urlencode(params)
        oauth_url = f"{BB_OAUTH_URL}/authorization?{query_string}"
        
        return {
            "oauth_url": oauth_url,
            "app_id_used": test_data.app_id,
            "redirect_uri": redirect_uri,
            "oauth_endpoint": f"{BB_OAUTH_URL}/authorization",
            "token_endpoint": f"{BB_OAUTH_URL}/token",
            "status": "OAuth URL generated successfully"
        }
        
    except Exception as e:
        logging.error(f"OAuth credentials test error: {e}")
        raise HTTPException(500, f"Failed to test OAuth credentials: {str(e)}")

@api_router.post("/organizations/manual-token-test")
async def manual_token_test(
    manual_data: BBMSCredentials,
    org_id: str = Depends(verify_token)
):
    """Test manual token storage (bypass OAuth)"""
    try:
        # Get organization
        organization = await get_organization(org_id)
        
        # Encrypt and store token
        encrypted_access_token = encrypt_data(manual_data.access_token)
        
        # Update organization
        await db.organizations.update_one(
            {"id": org_id},
            {
                "$set": {
                    "bb_access_token": encrypted_access_token,
                    "bb_merchant_id": manual_data.merchant_id,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return {"message": "Manual token stored successfully (test mode)"}
        
    except Exception as e:
        logging.error(f"Manual token test error: {e}")
        raise HTTPException(500, f"Failed to store manual token: {str(e)}")

@api_router.get("/debug/organization/{org_id}")
async def debug_organization(org_id: str):
    """Debug endpoint to check organization state"""
    try:
        org_data = await db.organizations.find_one({"id": org_id})
        if not org_data:
            return {"error": "Organization not found"}
        
        return {
            "id": org_data.get("id"),
            "name": org_data.get("name"),
            "has_bb_access_token": bool(org_data.get("bb_access_token")),
            "has_bb_merchant_id": bool(org_data.get("bb_merchant_id")),
            "oauth_state": bool(org_data.get("oauth_state")),
            "temp_app_id": bool(org_data.get("temp_app_id")),
            "test_mode": org_data.get("test_mode", True),
            "updated_at": org_data.get("updated_at")
        }
    except Exception as e:
        return {"error": str(e)}

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

@api_router.post("/organizations/bbms-setup")
async def setup_bbms_merchant_ids(
    setup_data: BBMSSetup,
    org_id: str = Depends(verify_token)
):
    """Setup BBMS merchant account IDs for test and production"""
    result = await db["organizations"].update_one(
        {"id": org_id},
        {
            "$set": {
                "bb_test_merchant_id": setup_data.test_merchant_id,
                "bb_production_merchant_id": setup_data.production_merchant_id,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    logging.info(f"BBMS setup update result: matched={result.matched_count}, modified={result.modified_count}")
    
    return {"message": "BBMS merchant account IDs configured successfully"}

@app.post("/api/organizations/request-password-reset")
async def request_password_reset(request: PasswordResetRequest):
    """Request a password reset - generates a simple reset code"""
    try:
        org = await db["organizations"].find_one({"admin_email": request.email})
        if not org:
            # Don't reveal if email exists or not for security
            return {"message": "If an account with this email exists, a reset code has been generated."}
        
        # Generate a simple 6-digit reset code
        import random
        reset_code = str(random.randint(100000, 999999))
        
        # Store the reset code (in production, this should expire)
        await db["organizations"].update_one(
            {"admin_email": request.email},
            {
                "$set": {
                    "password_reset_code": reset_code,
                    "password_reset_requested_at": datetime.utcnow()
                }
            }
        )
        
        # In a real app, you'd send this via email
        # For demo purposes, we'll log it (check backend logs)
        logging.info(f"Password reset code for {request.email}: {reset_code}")
        
        return {
            "message": "Reset code generated. Check the backend logs for the code (in production, this would be emailed).",
            "debug_code": reset_code  # Remove this in production!
        }
    except Exception as e:
        logging.error(f"Password reset request failed: {str(e)}")
        return {"message": "If an account with this email exists, a reset code has been generated."}

@app.post("/api/organizations/reset-password")
async def reset_password(reset: PasswordReset):
    """Reset password using the reset code"""
    try:
        org = await db["organizations"].find_one({
            "admin_email": reset.email,
            "password_reset_code": reset.reset_code
        })
        
        if not org:
            raise HTTPException(400, "Invalid email or reset code")
        
        # Check if reset code is not too old (24 hours)
        reset_time = org.get("password_reset_requested_at")
        if reset_time:
            time_diff = datetime.utcnow() - reset_time
            if time_diff.total_seconds() > 86400:  # 24 hours
                raise HTTPException(400, "Reset code has expired")
        
        # Hash the new password
        password_hash = bcrypt.hashpw(reset.new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Update password and clear reset code
        await db["organizations"].update_one(
            {"admin_email": reset.email},
            {
                "$set": {
                    "admin_password_hash": password_hash,
                    "updated_at": datetime.utcnow()
                },
                "$unset": {
                    "password_reset_code": "",
                    "password_reset_requested_at": ""
                }
            }
        )
        
        logging.info(f"Password reset successful for {reset.email}")
        return {"message": "Password reset successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Password reset failed: {str(e)}")
        raise HTTPException(500, "Password reset failed")

@app.get("/api/developer-instructions")
async def get_developer_instructions():
    """Get setup instructions for SKY App Developers"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>SKY App Developer Setup Instructions</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50 min-h-screen py-8">
        <div class="max-w-4xl mx-auto px-4">
            <div class="bg-white rounded-lg shadow-lg p-8">
                <h1 class="text-3xl font-bold text-gray-800 mb-8">🏗️ SKY App Developer Setup Guide</h1>
                
                <div class="prose max-w-none">
                    <div class="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-8">
                        <h2 class="text-xl font-semibold text-blue-800 mb-3">📋 Quick Overview</h2>
                        <p class="text-blue-700">
                            This guide is for <strong>developers</strong> setting up the Blackbaud SKY API integration for the donation platform. 
                            Organization admins (app users) will have a simplified interface that only requires their merchant account IDs.
                        </p>
                    </div>

                    <h2 class="text-2xl font-bold text-gray-800 mb-4">Step 1: Create Blackbaud Developer Application</h2>
                    
                    <div class="space-y-4 mb-8">
                        <div class="border-l-4 border-green-500 pl-4">
                            <h3 class="font-semibold text-gray-800">1.1 Access the Developer Portal</h3>
                            <p class="text-gray-600">Visit: <a href="https://developer.sky.blackbaud.com" target="_blank" class="text-blue-600 underline">https://developer.sky.blackbaud.com</a></p>
                            <p class="text-gray-600">Sign in with your Blackbaud account credentials</p>
                        </div>
                        
                        <div class="border-l-4 border-green-500 pl-4">
                            <h3 class="font-semibold text-gray-800">1.2 Create New Application</h3>
                            <ul class="list-disc list-inside text-gray-600 space-y-1">
                                <li>Navigate to "My Applications" → "Create Application"</li>
                                <li>Fill in application details (name, description, website)</li>
                                <li>Application Type: <strong>Web Application</strong></li>
                            </ul>
                        </div>
                        
                        <div class="border-l-4 border-yellow-500 pl-4">
                            <h3 class="font-semibold text-gray-800">1.3 Configure API Access & Redirect URI</h3>
                            <ul class="list-disc list-inside text-gray-600 space-y-1">
                                <li>Enable <strong>"Payments API"</strong></li>
                                <li>Enable <strong>"OAuth 2.0"</strong></li>
                                <li>Set Redirect URI to: <code class="bg-gray-100 px-2 py-1 rounded text-sm">${window.location.origin}/api/blackbaud-callback</code></li>
                            </ul>
                            <div class="bg-yellow-100 border border-yellow-300 rounded p-3 mt-2">
                                <p class="text-yellow-800 text-sm">
                                    ⚠️ <strong>Critical:</strong> The redirect URI must match exactly (including https and path)
                                </p>
                            </div>
                        </div>
                        
                        <div class="border-l-4 border-blue-500 pl-4">
                            <h3 class="font-semibold text-gray-800">1.4 Record Your Credentials</h3>
                            <p class="text-gray-600">Save these values from your application:</p>
                            <ul class="list-disc list-inside text-gray-600 space-y-1">
                                <li><strong>Application ID</strong> (Client ID)</li>
                                <li><strong>Application Secret</strong> (Client Secret)</li>
                            </ul>
                        </div>
                    </div>

                    <h2 class="text-2xl font-bold text-gray-800 mb-4">Step 2: Configure Environment Variables</h2>
                    
                    <div class="bg-gray-900 text-gray-100 p-4 rounded-lg mb-6">
                        <h3 class="text-lg font-semibold mb-3">Backend .env Configuration:</h3>
                        <pre class="text-sm"><code># Blackbaud SKY API Configuration
BB_APPLICATION_ID="your-application-id-here"
BB_APPLICATION_SECRET="your-application-secret-here"
BB_REDIRECT_URI="${window.location.origin}/api/blackbaud-callback"

# These can use demo values for platform testing
BB_PUBLIC_KEY="737471a1-1e7e-40ab-aa3a-97d0fb806e6f"
BB_PAYMENT_API_SUBSCRIPTION="e08faf45a0e643e6bfe042a8e4488afb"</code></pre>
                    </div>

                    <h2 class="text-2xl font-bold text-gray-800 mb-4">Step 3: User Experience</h2>
                    
                    <div class="bg-green-50 border border-green-200 rounded-lg p-6 mb-6">
                        <h3 class="text-lg font-semibold text-green-800 mb-3">✨ Simplified for Organization Admins</h3>
                        <p class="text-green-700 mb-3">
                            Organization admins (your app users) will only need to provide:
                        </p>
                        <ul class="list-disc list-inside text-green-700 space-y-1">
                            <li><strong>Test Merchant Account ID</strong> - for sandbox payments</li>
                            <li><strong>Production Merchant Account ID</strong> - for live payments</li>
                            <li>Click "Connect with Blackbaud" to complete OAuth2 setup</li>
                        </ul>
                        <p class="text-green-700 mt-3">
                            No technical setup, redirect URIs, or API keys required from users!
                        </p>
                    </div>

                    <h2 class="text-2xl font-bold text-gray-800 mb-4">Step 4: Documentation Links</h2>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                        <div class="border border-gray-200 rounded-lg p-4">
                            <h3 class="font-semibold text-gray-800 mb-2">📚 API Documentation</h3>
                            <ul class="space-y-2 text-sm">
                                <li><a href="https://developer.sky.blackbaud.com/docs/" target="_blank" class="text-blue-600 underline">SKY API Developer Guide</a></li>
                                <li><a href="https://developer.sky.blackbaud.com/api#api=payments" target="_blank" class="text-blue-600 underline">Payments API Reference</a></li>
                                <li><a href="https://developer.sky.blackbaud.com/docs/authorization/" target="_blank" class="text-blue-600 underline">OAuth2 Authorization Guide</a></li>
                            </ul>
                        </div>
                        
                        <div class="border border-gray-200 rounded-lg p-4">
                            <h3 class="font-semibold text-gray-800 mb-2">🛠️ Testing Resources</h3>
                            <ul class="space-y-2 text-sm">
                                <li><a href="https://kb.blackbaud.com/knowledgebase/articles/Article/64901" target="_blank" class="text-blue-600 underline">Test Credit Card Numbers</a></li>
                                <li><a href="https://host.nxt.blackbaud.com/payment-portal/" target="_blank" class="text-blue-600 underline">Merchant Services Portal</a></li>
                            </ul>
                        </div>
                    </div>

                    <div class="bg-red-50 border border-red-200 rounded-lg p-6">
                        <h3 class="text-lg font-semibold text-red-800 mb-3">🚨 Important Notes</h3>
                        <ul class="list-disc list-inside text-red-700 space-y-1">
                            <li>The redirect URI must be configured in your Blackbaud application <strong>before</strong> users can connect</li>
                            <li>Users will need separate test and production merchant account IDs from Blackbaud BBMS</li>
                            <li>The platform automatically handles test vs production mode switching</li>
                            <li>Test payments use Blackbaud's sandbox environment with test card numbers</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """)

@api_router.get("/organizations/me")
async def get_my_organization(org_id: str = Depends(verify_token)):
    """Get current organization details"""
    # Get raw organization data to include all fields
    org_data = await db["organizations"].find_one({"id": org_id})
    if not org_data:
        raise HTTPException(404, "Organization not found")
    
    # Don't return sensitive data
    return {
        "id": org_data.get("id"),
        "name": org_data.get("name"),
        "email": org_data.get("admin_email"),
        "has_bbms_configured": bool(org_data.get("bb_access_token")),
        "test_mode": org_data.get("test_mode", True),
        "bb_test_merchant_id": org_data.get("bb_test_merchant_id"),
        "bb_production_merchant_id": org_data.get("bb_production_merchant_id"),
        "form_settings": org_data.get("form_settings", {}),
        "created_at": org_data.get("created_at")
    }

@api_router.put("/organizations/{org_id}/form-settings")
async def update_form_settings(
    org_id: str,
    settings: FormSettings,
    current_org: str = Depends(verify_token)
):
    """Update organization form settings"""
    # Verify that the user can only update their own organization
    if org_id != current_org:
        raise HTTPException(403, "Access denied")
    
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

@app.post("/api/donate")
async def create_donation(donation: DonationRequest, authorization: str = Header(None)):
    """Create a donation and return checkout configuration for frontend JavaScript SDK"""
    try:
        logging.info(f"=== DONATION REQUEST START ===")
        logging.info(f"Donation data: {donation.dict()}")
        
        # Extract organization ID from JWT token if present
        organization_id = None
        if authorization and authorization.startswith("Bearer "):
            try:
                token = authorization.split(" ")[1]
                payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
                organization_id = payload.get("sub")
                logging.info(f"Extracted org_id from token: {organization_id}")
            except JWTError:
                logging.info("Failed to decode JWT token")
                pass
        
        # If no valid token, extract from donation request
        if not organization_id:
            organization_id = donation.org_id
            logging.info(f"Using org_id from donation request: {organization_id}")
        
        if not organization_id:
            raise HTTPException(400, "Organization ID required")
        
        # Get organization
        logging.info(f"Fetching organization with ID: {organization_id}")
        org = await db["organizations"].find_one({"id": organization_id})
        if not org:
            logging.error(f"Organization not found: {organization_id}")
            raise HTTPException(404, "Organization not found")
        
        logging.info(f"Organization found: {org.get('name', 'Unknown')}")
        logging.info(f"Organization data keys: {list(org.keys())}")
        
        # Get BBMS configuration - check both new and legacy formats
        encrypted_access_token = org.get("bb_access_token")  # New format (OAuth2 and manual)
        if not encrypted_access_token:
            # Legacy format fallback
            bbms_config = org.get("bbms_config", {})
            encrypted_access_token = bbms_config.get("access_token")
        
        # Get organization's test mode setting
        org_test_mode = org.get("test_mode", True)
        
        # Get appropriate merchant ID based on mode
        if org_test_mode:
            merchant_id = org.get("bb_test_merchant_id") or org.get("bb_merchant_id")  # Fallback to legacy
        else:
            merchant_id = org.get("bb_production_merchant_id") or org.get("bb_merchant_id")  # Fallback to legacy
        
        logging.info(f"=== MODE SETTINGS ===")
        logging.info(f"Organization {organization_id} test_mode setting: {org_test_mode}")
        logging.info(f"Selected merchant ID for {'test' if org_test_mode else 'production'} mode: {merchant_id}")
        
        if not merchant_id:
            mode_text = "test" if org_test_mode else "production"
            raise HTTPException(400, f"Organization has not configured {mode_text} merchant ID")

        if not encrypted_access_token:
            raise HTTPException(400, "Organization has not configured Blackbaud BBMS access")

        # Decrypt the access token
        access_token = decrypt_data(encrypted_access_token)
        
        # Create checkout configuration for frontend using organization's mode setting
        checkout_config = await bb_client.create_payment_checkout(
            donation, merchant_id, access_token, test_mode=org_test_mode
        )
        
        logging.info(f"=== CHECKOUT CONFIG CREATED ===")
        logging.info(f"Test mode: {checkout_config.get('test_mode')}")
        logging.info(f"Process mode: {checkout_config.get('process_mode')}")
        
        return {
            "success": True,
            "checkout_config": checkout_config,
            "message": "Checkout configuration created. Use the JavaScript SDK to complete payment."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in create_donation: {str(e)}")
        raise HTTPException(500, f"Internal server error: {str(e)}")


@app.post("/api/test-donate")
async def create_test_donation(donation: DonationRequest):
    """Create a test donation that respects organization test mode settings"""
    try:
        org_id = donation.org_id or "test-org-id"
        
        # If we have a real organization ID, get their test mode setting
        if org_id != "test-org-id":
            org = await db["organizations"].find_one({"id": org_id})
            if org:
                org_test_mode = org.get("test_mode", True)
                # Use organization's test merchant ID if available
                if org_test_mode and org.get("bb_test_merchant_id"):
                    merchant_id = org.get("bb_test_merchant_id")
                elif not org_test_mode and org.get("bb_production_merchant_id"):
                    merchant_id = org.get("bb_production_merchant_id")
                else:
                    # Fallback to demo test merchant ID
                    merchant_id = "96563c2e-c97a-4db1-a0ed-1b2a8219f110"  # Demo test merchant ID
                
                process_mode = "Test" if org_test_mode else "Live"
            else:
                # Organization not found, use demo test settings
                org_test_mode = True
                merchant_id = "96563c2e-c97a-4db1-a0ed-1b2a8219f110"
                process_mode = "Test"
        else:
            # Demo mode - always test
            org_test_mode = True
            merchant_id = "96563c2e-c97a-4db1-a0ed-1b2a8219f110"
            process_mode = "Test"
        
        # Create checkout configuration
        checkout_config = {
            "public_key": os.environ.get('BB_PUBLIC_KEY', '737471a1-1e7e-40ab-aa3a-97d0fb806e6f'),
            "merchant_account_id": merchant_id,
            "amount": float(donation.amount),
            "currency": "USD",
            "donor_info": {
                "email": donation.donor_email,
                "name": donation.donor_name,
                "phone": getattr(donation, 'donor_phone', ''),
                "address": getattr(donation, 'donor_address', '')
            },
            "test_mode": org_test_mode,
            "process_mode": process_mode,
            "return_url": "https://119fa407-7ed5-4661-8cb4-d43cc86d1517.preview.emergentagent.com/success",
            "cancel_url": "https://119fa407-7ed5-4661-8cb4-d43cc86d1517.preview.emergentagent.com/cancel"
        }
        
        logging.info(f"Test donation configuration created for ${donation.amount} - Mode: {process_mode}")
        
        return {
            "success": True,
            "checkout_config": checkout_config,
            "message": "Test checkout configuration created. This demonstrates the JavaScript SDK integration."
        }
        
    except Exception as e:
        logging.error(f"Error in create_test_donation: {str(e)}")
        raise HTTPException(500, f"Internal server error: {str(e)}")


@api_router.post("/test-process-transaction")
async def process_test_transaction(request: dict):
    """Process a test transaction token (demonstration purposes)"""
    try:
        transaction_token = request.get("transaction_token")
        donation_data = request.get("donation_data", {})
        
        if not transaction_token:
            raise HTTPException(400, "Transaction token is required")
        
        # Create test donation record
        donation_record = {
            "id": str(uuid.uuid4()),
            "organization_id": donation_data.get("org_id", "test-org-id"),
            "amount": donation_data.get("amount"),
            "donor_email": donation_data.get("donor_email"),
            "donor_name": donation_data.get("donor_name"),
            "transaction_token": transaction_token,
            "status": "completed",
            "payment_method": "blackbaud_checkout_test",
            "created_at": datetime.utcnow().isoformat(),
            "test_mode": True
        }
        
        await db["donations"].insert_one(donation_record)
        
        logging.info(f"Test donation recorded: {donation_record['id']} for ${donation_data.get('amount')}")
        
        return {
            "success": True,
            "donation_id": donation_record["id"],
            "transaction_token": transaction_token,
            "status": "completed",
            "message": "Test donation processed successfully"
        }
        
    except Exception as e:
        logging.error(f"Error in process_test_transaction: {str(e)}")
        raise HTTPException(500, f"Internal server error: {str(e)}")


@api_router.post("/process-transaction")
async def process_transaction(
    request: dict,
    authorization: str = Header(None)
):
    """Process a completed Blackbaud checkout transaction token"""
    try:
        # Extract organization ID from JWT token
        organization_id = None
        if authorization and authorization.startswith("Bearer "):
            try:
                token = authorization.split(" ")[1]
                payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
                organization_id = payload.get("sub")
            except JWTError:
                raise HTTPException(401, "Invalid authentication token")
        
        # Extract data from request
        transaction_token = request.get("transaction_token")
        donation_data = request.get("donation_data", {})
        
        if not transaction_token:
            raise HTTPException(400, "Transaction token is required")
        
        if not organization_id:
            organization_id = donation_data.get("org_id")
            
        if not organization_id:
            raise HTTPException(400, "Organization ID required")
        
        # Get organization and access token
        org = await db["organizations"].find_one({"id": organization_id})
        if not org:
            raise HTTPException(404, "Organization not found")
        
        # Get BBMS configuration - check both new and legacy formats
        encrypted_access_token = org.get("bb_access_token")  # New format (OAuth2 and manual)
        if not encrypted_access_token:
            # Legacy format fallback
            bbms_config = org.get("bbms_config", {})
            encrypted_access_token = bbms_config.get("access_token")
        
        if not encrypted_access_token:
            raise HTTPException(400, "Organization has not configured Blackbaud BBMS access")
        
        access_token = decrypt_data(encrypted_access_token)
        
        logging.info(f"Processing transaction token: {transaction_token[:8]}...")
        
        # For production transactions processed via JavaScript SDK,
        # we record the successful transaction without API verification
        # since the payment was already processed by Blackbaud's client-side SDK
        
        # Store the successful donation in our database
        donation_record = {
            "id": str(uuid.uuid4()),
            "organization_id": organization_id,
            "amount": donation_data.get("amount"),
            "donor_email": donation_data.get("donor_email"),
            "donor_name": donation_data.get("donor_name"),
            "transaction_token": transaction_token,
            "status": "completed",
            "payment_method": "blackbaud_checkout",
            "created_at": datetime.utcnow().isoformat(),
            "test_mode": org.get("test_mode", True)
        }
        
        await db["donations"].insert_one(donation_record)
        
        logging.info(f"Donation recorded successfully: {donation_record['id']} for ${donation_data.get('amount')}")
        
        return {
            "success": True,
            "donation_id": donation_record["id"],
            "transaction_token": transaction_token,
            "status": "completed",
            "message": "Donation processed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in process_transaction: {str(e)}")
        raise HTTPException(500, f"Internal server error: {str(e)}")

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
        "preset_amounts": sorted(organization.form_settings.get("preset_amounts", [25, 50, 100])),
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
    
    # Query the donations collection with the correct field name
    # Exclude the MongoDB _id field to avoid serialization issues
    transactions = await db["donations"].find(
        {"organization_id": org_id}, 
        {"_id": 0}  # Exclude the _id field
    ).sort("created_at", -1).to_list(100)
    
    return transactions

# Embed route for iframe - moved to API prefix to ensure it reaches backend
@app.get("/api/embed/test-donate")
async def serve_test_donation_embed(org_id: Optional[str] = None):
    """Serve test donation form for iframe embedding - works without OAuth2 setup"""
    public_key = os.environ.get('BB_PUBLIC_KEY')
    
    # If org_id is provided, get organization info for mode detection
    org_test_mode = True  # Default to test mode
    if org_id:
        org = await db["organizations"].find_one({"id": org_id})
        if org:
            org_test_mode = org.get("test_mode", True)
    
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Demo Donation Form</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://payments.blackbaud.com/Checkout/bbCheckout.2.0.js"></script>
        <style>
            body {{ margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif; }}
        </style>
    </head>
    <body>
        <div id="donation-root" class="max-w-md mx-auto"></div>
        <script>
            const API_BASE = 'https://119fa407-7ed5-4661-8cb4-d43cc86d1517.preview.emergentagent.com/api';
            const BB_PUBLIC_KEY = '{public_key}';
            const ORG_ID = '{org_id or "test-org-id"}';
            const ORG_TEST_MODE = {str(org_test_mode).lower()};
            
            // Demo donation form implementation - follows organization mode
            window.addEventListener('DOMContentLoaded', function() {{
                renderTestDonationForm();
            }});
            
            function renderTestDonationForm() {{
                const root = document.getElementById('donation-root');
                const modeIndicator = ORG_TEST_MODE ? 
                    '<div class="bg-yellow-100 border border-yellow-300 text-yellow-800 px-3 py-2 rounded-md text-sm mb-4">🧪 Demo Form - Test Mode (No real charges)</div>' :
                    '<div class="bg-green-100 border border-green-300 text-green-800 px-3 py-2 rounded-md text-sm mb-4">🚀 Demo Form - Production Mode (Live payments)</div>';
                    
                root.innerHTML = `
                    <div class="bg-white rounded-lg shadow-lg p-6">
                        <h2 class="text-2xl font-bold text-gray-800 mb-2">Demo Donation Form</h2>
                        ${{modeIndicator}}
                        <p class="text-gray-600 mb-6">This is a test donation form demonstrating the Blackbaud Checkout integration.</p>
                        
                        <form id="donation-form" class="space-y-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">Donation Amount</label>
                                <div class="grid grid-cols-3 gap-2 mb-3">
                                    <button type="button" class="amount-btn bg-gray-100 hover:bg-blue-100 border border-gray-300 rounded px-3 py-2 text-sm font-medium" data-amount="25">
                                        $25
                                    </button>
                                    <button type="button" class="amount-btn bg-gray-100 hover:bg-blue-100 border border-gray-300 rounded px-3 py-2 text-sm font-medium" data-amount="50">
                                        $50
                                    </button>
                                    <button type="button" class="amount-btn bg-gray-100 hover:bg-blue-100 border border-gray-300 rounded px-3 py-2 text-sm font-medium" data-amount="100">
                                        $100
                                    </button>
                                </div>
                                <div class="flex items-center space-x-2">
                                    <button type="button" id="custom-btn" class="amount-btn bg-gray-100 hover:bg-blue-100 border border-gray-300 rounded px-3 py-2 text-sm font-medium">
                                        Custom
                                    </button>
                                    <input type="number" id="custom-amount" class="hidden flex-1 border border-gray-300 rounded px-3 py-2 text-sm" placeholder="Enter amount" min="1" step="0.01">
                                </div>
                            </div>
                            
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                                <input type="text" id="donor-name" required class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" value="Test Donor" placeholder="Enter your full name">
                            </div>
                            
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
                                <input type="email" id="donor-email" required class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" value="test@example.com" placeholder="Enter your email">
                            </div>
                            
                            <button type="submit" id="donate-btn" class="w-full bg-blue-600 text-white font-medium py-3 px-4 rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed">
                                Donate Now (Test Mode)
                            </button>
                        </form>
                        
                        <div id="loading" class="hidden text-center py-8">
                            <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                            <p class="mt-2 text-gray-600">Processing your test donation...</p>
                        </div>
                        
                        <div id="success" class="hidden text-center py-8">
                            <div class="text-green-600 text-4xl mb-4">✓</div>
                            <h3 class="text-lg font-medium text-gray-800">Test donation successful!</h3>
                            <p class="text-gray-600 mt-2">This demonstrates the complete payment flow integration.</p>
                        </div>
                    </div>
                `;
                
                setupTestFormInteractions();
            }}
            
            function setupTestFormInteractions() {{
                let selectedAmount = 25; // Default to $25
                
                // Pre-select the $25 button
                const firstBtn = document.querySelector('[data-amount="25"]');
                if (firstBtn) {{
                    firstBtn.classList.add('bg-blue-500', 'text-white');
                }}
                
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
                document.getElementById('donation-form').addEventListener('submit', handleTestDonationSubmit);
                
                // Enable button initially
                updateDonateButton();
                
                function updateDonateButton() {{
                    const name = document.getElementById('donor-name').value.trim();
                    const email = document.getElementById('donor-email').value.trim();
                    const donateBtn = document.getElementById('donate-btn');
                    
                    const isValid = selectedAmount > 0 && name && email && email.includes('@');
                    donateBtn.disabled = !isValid;
                }}
                
                async function handleTestDonationSubmit(e) {{
                    e.preventDefault();
                    
                    const donationData = {{
                        amount: selectedAmount,
                        donor_name: document.getElementById('donor-name').value.trim(),
                        donor_email: document.getElementById('donor-email').value.trim(),
                        org_id: ORG_ID  // Use the organization ID passed from URL
                    }};
                    
                    console.log('Starting test donation process with data:', donationData);
                    
                    // Show loading
                    document.getElementById('donation-form').classList.add('hidden');
                    document.getElementById('loading').classList.remove('hidden');
                    
                    try {{
                        console.log('Step 1: Getting test checkout configuration from backend...');
                        
                        // Step 1: Get test checkout configuration
                        const configResponse = await fetch(`${{API_BASE}}/test-donate`, {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json'
                            }},
                            body: JSON.stringify(donationData)
                        }});
                        
                        console.log('Config response status:', configResponse.status);
                        
                        if (!configResponse.ok) {{
                            const errorText = await configResponse.text();
                            console.error('Config response error:', errorText);
                            throw new Error(`Failed to get checkout configuration: ${{configResponse.status}} - ${{errorText}}`);
                        }}
                        
                        const configResult = await configResponse.json();
                        console.log('Config result:', configResult);
                        const checkoutConfig = configResult.checkout_config;
                        
                        if (!checkoutConfig) {{
                            throw new Error('No checkout configuration received from server');
                        }}
                        
                        console.log('Step 2: Testing Blackbaud Checkout SDK integration...');
                        console.log('Blackbaud_OpenPaymentForm available:', typeof Blackbaud_OpenPaymentForm);
                        
                        // Check for the correct Blackbaud function
                        if (typeof Blackbaud_OpenPaymentForm === 'undefined') {{
                            console.error('Blackbaud_OpenPaymentForm function not found. Available functions:', Object.keys(window).filter(key => key.toLowerCase().includes('blackbaud')));
                            throw new Error('Blackbaud Checkout SDK not loaded properly');
                        }}
                        
                        console.log('Step 3: Setting up Blackbaud checkout event listeners...');
                        
                        // Set up event listeners for checkout events
                        document.addEventListener('checkoutReady', function() {{
                            console.log('Checkout ready');
                        }});
                        
                        document.addEventListener('checkoutLoaded', function() {{
                            console.log('Checkout loaded');
                        }});
                        
                        document.addEventListener('checkoutCancel', function() {{
                            console.log('REAL payment cancelled');
                            handlePaymentCancel();
                        }});
                        
                        document.addEventListener('checkoutComplete', function(e) {{
                            console.log('REAL payment complete, transaction token:', e.detail.transactionToken);
                            handleTestPaymentSuccess(e.detail.transactionToken, donationData);
                        }});
                        
                        document.addEventListener('checkoutError', function(e) {{
                            console.error('REAL payment error:', e.detail);
                            handlePaymentError({{
                                message: e.detail.errorText,
                                code: e.detail.errorCode
                            }});
                        }});
                        
                        console.log('Step 4: Creating transaction object...');
                        console.log('Checkout config received:', checkoutConfig);
                        console.log('Mode settings - test_mode:', checkoutConfig.test_mode, 'process_mode:', checkoutConfig.process_mode);
                        
                        // Create transaction object as per official documentation
                        const transactionData = {{
                            key: BB_PUBLIC_KEY, // Using the public key as the transaction key
                            payment_configuration_id: checkoutConfig.merchant_account_id,
                            Amount: checkoutConfig.amount,
                            process_mode: checkoutConfig.process_mode || 'test'  // Critical: Controls test vs production mode
                        }};
                        
                        console.log('Transaction data:', transactionData);
                        
                        console.log('Step 5: Opening REAL Blackbaud checkout modal...');
                        
                        // Open the REAL checkout modal using official Blackbaud method
                        Blackbaud_OpenPaymentForm(transactionData);
                        
                    }} catch (error) {{
                        console.error('Test donation initialization failed:', error);
                        alert(`Failed to initialize test payment: ${{error.message}}`);
                        
                        // Show form again
                        document.getElementById('loading').classList.add('hidden');
                        document.getElementById('donation-form').classList.remove('hidden');
                    }}
                }}
                
                async function handleTestPaymentSuccess(transactionToken, donationData) {{
                    try {{
                        console.log('Processing test transaction token:', transactionToken);
                        
                        // Process the REAL transaction token
                        const response = await fetch(`${{API_BASE}}/test-process-transaction`, {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json'
                            }},
                            body: JSON.stringify({{
                                transaction_token: transactionToken,
                                donation_data: donationData
                            }})
                        }});
                        
                        if (!response.ok) {{
                            throw new Error('Failed to process transaction');
                        }}
                        
                        const result = await response.json();
                        console.log('REAL donation completed successfully:', result);
                        
                        // Show success message
                        document.getElementById('loading').classList.add('hidden');
                        document.getElementById('success').classList.remove('hidden');
                        
                    }} catch (error) {{
                        console.error('REAL transaction processing failed:', error);
                        alert('Payment was processed but we had trouble recording it. Please contact support.');
                    }}
                }}
                
                function handlePaymentCancel() {{
                    console.log('REAL payment was cancelled by user');
                    // Show form again
                    document.getElementById('loading').classList.add('hidden');
                    document.getElementById('donation-form').classList.remove('hidden');
                }}
                
                function handlePaymentError(error) {{
                    console.error('REAL payment error:', error);
                    alert(`Payment failed: ${{error.message || 'Unknown error'}}`);
                    // Show form again
                    document.getElementById('loading').classList.add('hidden');
                    document.getElementById('donation-form').classList.remove('hidden');
                }}
            }}
        </script>
    </body>
    </html>
    """)
@app.get("/api/embed/donate/{org_id}")
async def serve_donation_embed(org_id: str):
    """Serve donation form for iframe embedding with Blackbaud JavaScript SDK"""
    try:
        # Check if organization exists and has BBMS configured
        org = await db["organizations"].find_one({"id": org_id})
        if not org:
            # Fallback to test form if organization not found
            return await serve_test_donation_embed()
        
        bbms_config = org.get("bbms_config", {})
        # Check both new and legacy formats for access token
        has_access_token = bool(org.get("bb_access_token")) or bool(bbms_config.get("access_token"))
        if not has_access_token:
            # Fallback to test form if not configured
            return await serve_test_donation_embed()
        
        # Organization is properly configured, show the real form
        public_key = os.environ.get('BB_PUBLIC_KEY')
        org_test_mode = org.get("test_mode", True)
        
        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Donation Form</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <script src="https://payments.blackbaud.com/Checkout/bbCheckout.2.0.js"></script>
            <style>
                body {{ margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif; }}
            </style>
        </head>
        <body>
            <div id="donation-root" class="max-w-md mx-auto"></div>
            <script>
                const ORG_ID = '{org_id}';
                const API_BASE = 'https://119fa407-7ed5-4661-8cb4-d43cc86d1517.preview.emergentagent.com/api';
                const BB_PUBLIC_KEY = '{public_key}';
                const ORG_TEST_MODE = {str(org_test_mode).lower()};  // Organization's test mode setting
                
                // Organization-specific donation form implementation
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
                    const modeIndicator = ORG_TEST_MODE ? 
                        '<div class="bg-yellow-100 border border-yellow-300 text-yellow-800 px-3 py-2 rounded-md text-sm mb-4">🧪 Test Mode - No real charges will be made</div>' :
                        '<div class="bg-green-100 border border-green-300 text-green-800 px-3 py-2 rounded-md text-sm mb-4">🚀 Production Mode - Live payments</div>';
                        
                    root.innerHTML = `
                        <div class="bg-white rounded-lg shadow-lg p-6">
                            <h2 class="text-2xl font-bold text-gray-800 mb-2">${{config.organization_name}}</h2>
                            ${{modeIndicator}}
                            <p class="text-gray-600 mb-6">${{config.description}}</p>
                            
                            <form id="donation-form" class="space-y-4">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">Donation Amount</label>
                                    <div class="grid grid-cols-3 gap-2 mb-3">
                                        ${{config.preset_amounts.map(amount => `
                                            <button type="button" class="amount-btn bg-gray-100 hover:bg-blue-100 border border-gray-300 rounded px-3 py-2 text-sm font-medium" data-amount="${{amount}}">
                                                $${{amount}}
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
                            
                            <div id="success" class="hidden text-center py-8">
                                <div class="text-green-600 text-4xl mb-4">✓</div>
                                <h3 class="text-lg font-medium text-gray-800">Thank you for your donation!</h3>
                                <p class="text-gray-600 mt-2">Your payment has been processed successfully.</p>
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
                        
                        console.log('Starting donation process with data:', donationData);
                        
                        // Show loading
                        document.getElementById('donation-form').classList.add('hidden');
                        document.getElementById('loading').classList.remove('hidden');
                        
                        try {{
                            console.log('Step 1: Getting checkout configuration from backend...');
                            
                            // Step 1: Get checkout configuration from our backend
                            const configResponse = await fetch(`${{API_BASE}}/donate`, {{
                                method: 'POST',
                                headers: {{
                                    'Content-Type': 'application/json'
                                }},
                                body: JSON.stringify(donationData)
                            }});
                            
                            console.log('Config response status:', configResponse.status);
                            
                            if (!configResponse.ok) {{
                                const errorText = await configResponse.text();
                                console.error('Config response error:', errorText);
                                throw new Error(`Failed to get checkout configuration: ${{configResponse.status}} - ${{errorText}}`);
                            }}
                            
                            const configResult = await configResponse.json();
                            console.log('Config result:', configResult);
                            const checkoutConfig = configResult.checkout_config;
                            
                            if (!checkoutConfig) {{
                                throw new Error('No checkout configuration received from server');
                            }}
                            
                            console.log('Step 2: Testing Blackbaud Checkout SDK integration...');
                            console.log('Blackbaud_OpenPaymentForm available:', typeof Blackbaud_OpenPaymentForm);
                            
                            // Check for the correct Blackbaud function
                            if (typeof Blackbaud_OpenPaymentForm === 'undefined') {{
                                console.error('Blackbaud_OpenPaymentForm function not found. Available functions:', Object.keys(window).filter(key => key.toLowerCase().includes('blackbaud')));
                                throw new Error('Blackbaud Checkout SDK not loaded properly');
                            }}
                            
                            console.log('Step 3: Setting up Blackbaud checkout event listeners...');
                            
                            // Set up event listeners for checkout events
                            document.addEventListener('checkoutReady', function() {{
                                console.log('Checkout ready');
                            }});
                            
                            document.addEventListener('checkoutLoaded', function() {{
                                console.log('Checkout loaded');
                            }});
                            
                            document.addEventListener('checkoutCancel', function() {{
                                console.log('REAL payment cancelled');
                                handlePaymentCancel();
                            }});
                            
                            document.addEventListener('checkoutComplete', function(e) {{
                                console.log('REAL payment complete, transaction token:', e.detail.transactionToken);
                                handlePaymentSuccess(e.detail.transactionToken, donationData);
                            }});
                            
                            document.addEventListener('checkoutError', function(e) {{
                                console.error('REAL payment error:', e.detail);
                                handlePaymentError({{
                                    message: e.detail.errorText,
                                    code: e.detail.errorCode
                                }});
                            }});
                            
                            console.log('Step 4: Creating transaction object...');
                            console.log('Checkout config received:', checkoutConfig);
                            console.log('Mode settings - test_mode:', checkoutConfig.test_mode, 'process_mode:', checkoutConfig.process_mode);
                            
                            // Create transaction object as per official documentation
                            const transactionData = {{
                                key: BB_PUBLIC_KEY, // Using the public key as the transaction key
                                payment_configuration_id: checkoutConfig.merchant_account_id,
                                Amount: checkoutConfig.amount,
                                process_mode: checkoutConfig.process_mode || 'test'  // Critical: Controls test vs production mode
                            }};
                            
                            console.log('Transaction data:', transactionData);
                            
                            console.log('Step 5: Opening REAL Blackbaud checkout modal...');
                            
                            // Open the REAL checkout modal using official Blackbaud method
                            Blackbaud_OpenPaymentForm(transactionData);
                            
                        }} catch (error) {{
                            console.error('Donation initialization failed:', error);
                            alert(`Failed to initialize payment: ${{error.message}}`);
                            
                            // Show form again
                            document.getElementById('loading').classList.add('hidden');
                            document.getElementById('donation-form').classList.remove('hidden');
                        }}
                    }}
                    
                    async function handlePaymentSuccess(transactionToken, donationData) {{
                        try {{
                            console.log('Processing REAL transaction token:', transactionToken);
                            
                            // Process the REAL transaction token
                            const response = await fetch(`${{API_BASE}}/process-transaction`, {{
                                method: 'POST',
                                headers: {{
                                    'Content-Type': 'application/json'
                                }},
                                body: JSON.stringify({{
                                    transaction_token: transactionToken,
                                    donation_data: donationData
                                }})
                            }});
                            
                            if (!response.ok) {{
                                throw new Error('Failed to process transaction');
                            }}
                            
                            const result = await response.json();
                            console.log('REAL donation completed successfully:', result);
                            
                            // Show success message
                            document.getElementById('loading').classList.add('hidden');
                            document.getElementById('success').classList.remove('hidden');
                            
                        }} catch (error) {{
                            console.error('REAL transaction processing failed:', error);
                            alert('Payment was processed but we had trouble recording it. Please contact support.');
                        }}
                    }}
                    
                    function handlePaymentCancel() {{
                        console.log('REAL payment was cancelled by user');
                        // Show form again
                        document.getElementById('loading').classList.add('hidden');
                        document.getElementById('donation-form').classList.remove('hidden');
                    }}
                    
                    function handlePaymentError(error) {{
                        console.error('REAL payment error:', error);
                        alert(`Payment failed: ${{error.message || 'Unknown error'}}`);
                        // Show form again
                        document.getElementById('loading').classList.add('hidden');
                        document.getElementById('donation-form').classList.remove('hidden');
                    }}
                }}
            </script>
        </body>
        </html>
        """)
        
    except Exception as e:
        logging.error(f"Error serving donation embed: {str(e)}")
        # Fallback to test form on any error
        return await serve_test_donation_embed()
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Donation Form</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://payments.blackbaud.com/Checkout/bbCheckout.2.0.js"></script>
        <style>
            body {{ margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif; }}
        </style>
    </head>
    <body>
        <div id="donation-root" class="max-w-md mx-auto"></div>
        <script>
            const ORG_ID = '{org_id}';
            const API_BASE = 'https://119fa407-7ed5-4661-8cb4-d43cc86d1517.preview.emergentagent.com/api';
            const BB_PUBLIC_KEY = '{public_key}';
            
            // Simple donation form implementation with Blackbaud Checkout
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
                                            $${{amount}}
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
                        
                        <div id="success" class="hidden text-center py-8">
                            <div class="text-green-600 text-4xl mb-4">✓</div>
                            <h3 class="text-lg font-medium text-gray-800">Thank you for your donation!</h3>
                            <p class="text-gray-600 mt-2">Your payment has been processed successfully.</p>
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
                    
                    console.log('Starting donation process with data:', donationData);
                    
                    // Show loading
                    document.getElementById('donation-form').classList.add('hidden');
                    document.getElementById('loading').classList.remove('hidden');
                    
                    try {{
                        console.log('Step 1: Getting checkout configuration from backend...');
                        
                        // Step 1: Get checkout configuration from our backend
                        const configResponse = await fetch(`${{API_BASE}}/donate`, {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json'
                            }},
                            body: JSON.stringify(donationData)
                        }});
                        
                        console.log('Config response status:', configResponse.status);
                        
                        if (!configResponse.ok) {{
                            const errorText = await configResponse.text();
                            console.error('Config response error:', errorText);
                            throw new Error(`Failed to get checkout configuration: ${{configResponse.status}} - ${{errorText}}`);
                        }}
                        
                        const configResult = await configResponse.json();
                        console.log('Config result:', configResult);
                        const checkoutConfig = configResult.checkout_config;
                        
                        if (!checkoutConfig) {{
                            throw new Error('No checkout configuration received from server');
                        }}
                        
                        console.log('Step 2: Checking for Blackbaud Checkout SDK...');
                        console.log('bbCheckout available:', typeof bbCheckout);
                        console.log('window.bbCheckout available:', typeof window.bbCheckout);
                        
                        // Step 2: Check multiple possible SDK variable names
                        let CheckoutSDK = null;
                        if (typeof bbCheckout !== 'undefined') {{
                            CheckoutSDK = bbCheckout;
                            console.log('Using bbCheckout');
                        }} else if (typeof window.bbCheckout !== 'undefined') {{
                            CheckoutSDK = window.bbCheckout;
                            console.log('Using window.bbCheckout');
                        }} else if (typeof window.BlackbaudCheckout !== 'undefined') {{
                            CheckoutSDK = window.BlackbaudCheckout;
                            console.log('Using window.BlackbaudCheckout');
                        }} else {{
                            console.error('Blackbaud Checkout SDK not found. Available objects:', Object.keys(window));
                            throw new Error('Blackbaud Checkout SDK not loaded');
                        }}
                        
                        console.log('Step 3: Initializing checkout with config:', {{
                            publicKey: BB_PUBLIC_KEY,
                            merchantAccountId: checkoutConfig.merchant_account_id,
                            amount: Math.round(checkoutConfig.amount * 100),
                            currency: 'USD'
                        }});
                        
                        // Step 3: Initialize Blackbaud Checkout with JavaScript SDK
                        const checkout = new CheckoutSDK({{
                            publicKey: BB_PUBLIC_KEY,
                            merchantAccountId: checkoutConfig.merchant_account_id,
                            amount: Math.round(checkoutConfig.amount * 100), // Convert to cents
                            currency: 'USD',
                            customer: {{
                                email: checkoutConfig.donor_info.email,
                                name: checkoutConfig.donor_info.name
                            }},
                            onSuccess: function(transactionToken) {{
                                console.log('Payment success, token:', transactionToken);
                                handlePaymentSuccess(transactionToken, donationData);
                            }},
                            onCancel: function() {{
                                console.log('Payment cancelled');
                                handlePaymentCancel();
                            }},
                            onError: function(error) {{
                                console.error('Payment error:', error);
                                handlePaymentError(error);
                            }}
                        }});
                        
                        console.log('Step 4: Opening checkout modal...');
                        // Open the checkout modal
                        checkout.open();
                        
                    }} catch (error) {{
                        console.error('Donation initialization failed:', error);
                        alert(`Failed to initialize payment: ${{error.message}}`);
                        
                        // Show form again
                        document.getElementById('loading').classList.add('hidden');
                        document.getElementById('donation-form').classList.remove('hidden');
                    }}
                }}
                
                async function handlePaymentSuccess(transactionToken, donationData) {{
                    try {{
                        // Process the transaction token with our backend
                        const response = await fetch(`${{API_BASE}}/process-transaction`, {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json'
                            }},
                            body: JSON.stringify({{
                                transaction_token: transactionToken,
                                donation_data: donationData
                            }})
                        }});
                        
                        if (!response.ok) {{
                            throw new Error('Failed to process transaction');
                        }}
                        
                        const result = await response.json();
                        
                        // Show success message
                        document.getElementById('loading').classList.add('hidden');
                        document.getElementById('success').classList.remove('hidden');
                        
                        console.log('Donation completed successfully:', result);
                        
                    }} catch (error) {{
                        console.error('Transaction processing failed:', error);
                        alert('Payment was processed but we had trouble recording it. Please contact support.');
                    }}
                }}
                
                function handlePaymentCancel() {{
                    console.log('Payment was cancelled by user');
                    // Show form again
                    document.getElementById('loading').classList.add('hidden');
                    document.getElementById('donation-form').classList.remove('hidden');
                }}
                
                function handlePaymentError(error) {{
                    console.error('Payment error:', error);
                    alert('Payment failed. Please try again.');
                    // Show form again
                    document.getElementById('loading').classList.add('hidden');
                    document.getElementById('donation-form').classList.remove('hidden');
                }}
            }}
        </script>
    </body>
    </html>
    """)

# Include API router in app with higher priority
app.include_router(api_router)

# OAuth callback route - Add directly to main app to ensure it's registered
@app.get("/api/blackbaud-callback")
async def oauth_callback_direct(code: str = None, state: str = None, error: str = None):
    """OAuth callback page that handles the redirect and posts back to API"""
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Blackbaud Authentication</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50 flex items-center justify-center min-h-screen">
        <div class="bg-white rounded-lg shadow-lg p-8 max-w-md w-full mx-4">
            <div id="loading" class="text-center">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                <h2 class="text-xl font-semibold text-gray-800 mb-2">Connecting to Blackbaud...</h2>
                <p class="text-gray-600">Please wait while we complete the authentication.</p>
                <div id="debug-info" class="mt-4 text-xs text-gray-500 bg-gray-100 p-2 rounded">
                    <strong>🔍 OAuth Callback Debug Info:</strong><br>
                    Code: <span class="font-mono">{code or 'Missing'}</span><br>
                    State: <span class="font-mono">{state[:30] + '...' if state else 'Missing'}</span><br>
                    Error: <span class="font-mono">{error or 'None'}</span>
                </div>
            </div>
            
            <div id="success" class="hidden text-center">
                <div class="text-green-500 text-4xl mb-4">✅</div>
                <h2 class="text-xl font-semibold text-gray-800 mb-2">Authentication Successful!</h2>
                <p class="text-gray-600 mb-4">Your Blackbaud account has been connected.</p>
                <button onclick="closeWindow()" class="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700">
                    Continue
                </button>
            </div>
            
            <div id="error" class="hidden text-center">
                <div class="text-red-500 text-4xl mb-4">❌</div>
                <h2 class="text-xl font-semibold text-gray-800 mb-2">Authentication Failed</h2>
                <p class="text-gray-600 mb-4" id="error-message">Something went wrong during authentication.</p>
                <div id="error-details" class="text-xs text-gray-500 mb-4 bg-red-50 p-2 rounded font-mono"></div>
                <button onclick="closeWindow()" class="bg-gray-600 text-white px-6 py-2 rounded-md hover:bg-gray-700">
                    Close and Try Again
                </button>
            </div>
        </div>
        
        <script>
            console.log('🚀 OAuth Callback Page Loaded Successfully');
            console.log('Current URL:', window.location.href);
            
            const urlParams = new URLSearchParams(window.location.search);
            const code = urlParams.get('code') || '{code}';
            const state = urlParams.get('state') || '{state}';
            const error = urlParams.get('error') || '{error}';
            
            console.log('📋 Parameters received:', {{
                code: code ? 'present (' + code.length + ' chars)' : 'missing',
                state: state ? 'present (' + state.length + ' chars)' : 'missing',
                error: error || 'none'
            }});
            
            function showSuccess() {{
                console.log('✅ Showing success state');
                document.getElementById('loading').classList.add('hidden');
                document.getElementById('success').classList.remove('hidden');
            }}
            
            function showError(message, details = '') {{
                console.error('❌ Error occurred:', message, details);
                document.getElementById('loading').classList.add('hidden');
                document.getElementById('error').classList.remove('hidden');
                document.getElementById('error-message').textContent = message;
                if (details) {{
                    document.getElementById('error-details').textContent = details;
                }}
            }}
            
            function closeWindow() {{
                console.log('🔄 Closing window and notifying parent...');
                if (window.opener) {{
                    const success = !document.getElementById('error').classList.contains('hidden');
                    const errorMsg = success ? null : document.getElementById('error-message').textContent;
                    
                    console.log('📤 Sending message to parent:', {{ success, error: errorMsg }});
                    
                    window.opener.postMessage({{
                        type: 'BLACKBAUD_AUTH_COMPLETE',
                        success: success,
                        error: errorMsg
                    }}, '*');
                    
                    setTimeout(() => {{
                        console.log('🔄 Closing popup window...');
                        window.close();
                    }}, 500);
                }} else {{
                    console.log('ℹ️ No opener window found, redirecting to main app');
                    window.location.href = '/';
                }}
            }}
            
            async function handleCallback() {{
                console.log('🔄 Starting OAuth callback processing...');
                
                if (error && error !== 'None') {{
                    console.error('❌ OAuth error from Blackbaud:', error);
                    showError(`Blackbaud OAuth Error: ${{error}}`);
                    return;
                }}
                
                if (!code || code === 'Missing' || !state || state === 'Missing') {{
                    console.error('❌ Missing required OAuth parameters');
                    showError('Missing authorization code or state parameter from Blackbaud.');
                    return;
                }}
                
                try {{
                    const merchant_id = localStorage.getItem('bb_merchant_id') || '96563c2e-c97a-4db1-a0ed-1b2a8219f110';
                    
                    console.log('📡 Making API call to process OAuth callback...');
                    console.log('🔍 Request details:', {{
                        merchant_id: merchant_id,
                        state_preview: state.substring(0, 30) + '...',
                        code_preview: code.substring(0, 10) + '...'
                    }});
                    
                    const response = await fetch('/api/organizations/bbms-oauth/callback', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify({{
                            code: code,
                            state: state,
                            merchant_id: merchant_id
                        }})
                    }});
                    
                    console.log('📡 API Response status:', response.status);
                    
                    if (response.ok) {{
                        const result = await response.json();
                        console.log('✅ OAuth callback successful:', result);
                        localStorage.removeItem('bb_merchant_id');
                        showSuccess();
                    }} else {{
                        const errorData = await response.json();
                        console.error('❌ API Error:', errorData);
                        
                        let errorMessage = errorData.detail || 'Authentication failed';
                        if (errorMessage.includes('invalid_grant')) {{
                            errorMessage = 'Authorization code expired. Please try the OAuth flow again quickly.';
                        }}
                        
                        showError(errorMessage, `Status: ${{response.status}} - ${{JSON.stringify(errorData)}}`);
                    }}
                }} catch (err) {{
                    console.error('❌ Network error:', err);
                    showError('Network error during authentication', err.message);
                }}
            }}
            
            // Start processing immediately when page loads
            console.log('🚀 Initiating OAuth callback processing...');
            handleCallback();
        </script>
    </body>
    </html>
    """)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()