import requests
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

# Blackbaud API URLs - Try both formats
BB_BASE_URLS = [
    "https://api.sky.blackbaud.com",
    "https://api.sandbox.sky.blackbaud.com"
]
BB_OAUTH_URL = "https://oauth2.sky.blackbaud.com"

# Test merchant account ID (from review request)
TEST_MERCHANT_ID = "96563c2e-c97a-4db1-a0ed-1b2a8219f110"

def test_checkout_creation(base_url):
    """Test checkout session creation with the correct merchant ID"""
    logging.info(f"Testing checkout session creation with base URL: {base_url}")
    logging.info(f"Using merchant ID: {TEST_MERCHANT_ID}")
    logging.info(f"Using subscription key: {BB_PAYMENT_API_SUBSCRIPTION}")
    
    # Mock access token for testing
    mock_access_token = "mock_access_token"
    
    headers = {
        "Bb-Api-Subscription-Key": BB_PAYMENT_API_SUBSCRIPTION,
        "Authorization": f"Bearer {mock_access_token}",
        "Content-Type": "application/json"
    }
    
    # Test checkout data
    checkout_data = {
        "merchant_account_id": TEST_MERCHANT_ID,
        "amount": {
            "value": 2500,  # $25.00
            "currency": "USD"
        },
        "return_url": "https://example.com/success",
        "cancel_url": "https://example.com/cancel",
        "metadata": {
            "donor_email": "test@example.com",
            "donor_name": "Test Donor",
            "org_id": "test_org_id",
            "test_mode": "true"
        }
    }
    
    try:
        url = f"{base_url}/payments/checkout/sessions"
        logging.info(f"Making request to: {url}")
        logging.info(f"Request payload: {json.dumps(checkout_data, indent=2)}")
        
        response = requests.post(
            url,
            headers=headers,
            json=checkout_data,
            timeout=30.0
        )
        
        logging.info(f"Response status: {response.status_code}")
        logging.info(f"Response headers: {response.headers}")
        
        if response.status_code in [200, 201]:
            logging.info("Checkout session created successfully!")
            logging.info(f"Response: {response.text}")
            return True
        else:
            logging.error(f"Failed to create checkout session: {response.text}")
            
            # Try to parse error details
            try:
                error_details = response.json()
                logging.error(f"Error details: {json.dumps(error_details, indent=2)}")
            except:
                pass
            
            return False
    except Exception as e:
        logging.error(f"Checkout creation test failed: {e}")
        return False

def main():
    logging.info("Starting Blackbaud API Checkout Test")
    logging.info("=========================================")
    logging.info(f"Environment: {BB_ENVIRONMENT}")
    logging.info(f"OAuth URL: {BB_OAUTH_URL}")
    logging.info(f"Payment API Subscription Key: {BB_PAYMENT_API_SUBSCRIPTION}")
    logging.info(f"Test Merchant ID: {TEST_MERCHANT_ID}")
    logging.info("=========================================")
    
    # Test checkout creation with both base URLs
    for base_url in BB_BASE_URLS:
        checkout = test_checkout_creation(base_url)
        logging.info(f"Checkout creation test with {base_url}: {'PASSED' if checkout else 'FAILED'}")
    
    logging.info("=========================================")
    logging.info("Blackbaud API Checkout Test Complete")

if __name__ == "__main__":
    main()