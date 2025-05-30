import httpx
import asyncio
import os
import json
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv('/app/backend/.env')

# Blackbaud API Configuration
BB_PAYMENT_API_SUBSCRIPTION = os.environ.get('BB_PAYMENT_API_SUBSCRIPTION', 'e08faf45a0e643e6bfe042a8e4488afb')
BB_STANDARD_API_SUBSCRIPTION = os.environ.get('BB_STANDARD_API_SUBSCRIPTION', '499a30381fe94d01b661957def96b335')
BB_APP_ID = os.environ.get('BB_APP_ID', '2e2c42a7-a2f5-4fd3-a0bc-d4b3b36d8cea')
BB_APP_SECRET = os.environ.get('BB_APP_SECRET', '3VuF4BNX72+dClCDheqMN7xPfsu29GKGxdaobEIbWXU=')
BB_ENVIRONMENT = os.environ.get('BB_ENVIRONMENT', 'sandbox')

# Blackbaud API URLs
BB_BASE_URL = "https://api.sandbox.sky.blackbaud.com"  # Try with sandbox subdomain
BB_OAUTH_URL = "https://oauth2.sky.blackbaud.com"

# Test merchant account ID (from review request)
TEST_MERCHANT_ID = "96563c2e-c97a-4db1-a0ed-1b2a8219f110"

async def test_payment_endpoints():
    """Test various payment endpoint paths"""
    logging.info("Testing various payment endpoint paths...")
    logging.info(f"Using subscription key: {BB_PAYMENT_API_SUBSCRIPTION}")
    
    headers = {
        "Bb-Api-Subscription-Key": BB_PAYMENT_API_SUBSCRIPTION,
        "Content-Type": "application/json"
    }
    
    # List of endpoints to try
    endpoints = [
        "/payments/configurations",
        "/payments/v1/configurations",
        "/payments/v1/checkout-sessions",
        "/payments/checkout-sessions",
        "/payments/v1/checkout/sessions",
        "/payments/checkout/sessions"
    ]
    
    for endpoint in endpoints:
        try:
            url = f"{BB_BASE_URL}{endpoint}"
            logging.info(f"Making GET request to: {url}")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=headers,
                    timeout=30.0
                )
            
            logging.info(f"Response status for {endpoint}: {response.status_code}")
            logging.info(f"Response headers: {response.headers}")
            
            if response.status_code == 200:
                logging.info(f"Endpoint {endpoint} is accessible!")
                logging.info(f"Response: {response.text[:200]}...")  # Show first 200 chars
            else:
                logging.info(f"Response for {endpoint}: {response.text}")
        except Exception as e:
            logging.error(f"Test for endpoint {endpoint} failed: {e}")

async def main():
    logging.info("Starting Blackbaud API Endpoint Tests")
    logging.info("=========================================")
    logging.info(f"Environment: {BB_ENVIRONMENT}")
    logging.info(f"Base URL: {BB_BASE_URL}")
    logging.info(f"OAuth URL: {BB_OAUTH_URL}")
    logging.info(f"Payment API Subscription Key: {BB_PAYMENT_API_SUBSCRIPTION}")
    logging.info(f"Test Merchant ID: {TEST_MERCHANT_ID}")
    logging.info("=========================================")
    
    # Test various payment endpoints
    await test_payment_endpoints()
    
    logging.info("=========================================")
    logging.info("Blackbaud API Endpoint Tests Complete")

if __name__ == "__main__":
    asyncio.run(main())