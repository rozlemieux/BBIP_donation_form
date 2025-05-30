
import requests
import unittest
import json
import os
import sys
from urllib.parse import urlparse, parse_qs

# Use the public endpoint from the frontend .env file
BACKEND_URL = "https://c44b0daf-083b-41cc-aa42-f9e46f580f6f.preview.emergentagent.com"
API_URL = f"{BACKEND_URL}/api"

class BlackbaudOAuthTest(unittest.TestCase):
    def setUp(self):
        # Test organization credentials
        self.org_data = {
            "name": "Test Organization",
            "admin_email": f"test_org_{os.urandom(4).hex()}@example.com",
            "admin_password": "TestPassword123!"
        }
        
        # Blackbaud OAuth test data
        self.oauth_data = {
            "merchant_id": "96563c2e-c97a-4db1-a0ed-1b2a8219f110",
            "app_id": "2e2c42a7-a2f5-4fd3-a0bc-d4b3b36d8cea",
            "app_secret": "3VuF4BNX72+dClCDheqMN7xPfsu29GKGxdaobEIbWXU="
        }
        
        # Register and login
        self.register_and_login()
    
    def register_and_login(self):
        """Register a test organization and login to get auth token"""
        # Register
        response = requests.post(f"{API_URL}/organizations/register", json=self.org_data)
        if response.status_code != 200:
            print(f"Registration failed: {response.text}")
            self.auth_token = None
            self.org_id = None
            return
            
        data = response.json()
        self.auth_token = data.get("access_token")
        self.org_id = data.get("organization", {}).get("id")
        
        print(f"Registered test organization with ID: {self.org_id}")
    
    def test_01_oauth_start_endpoint(self):
        """Test the OAuth start endpoint"""
        if not self.auth_token:
            self.skipTest("Authentication failed during setup")
        
        print("\n🔍 Testing OAuth start endpoint...")
        
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        response = requests.post(
            f"{API_URL}/organizations/bbms-oauth/start", 
            json=self.oauth_data,
            headers=headers
        )
        
        self.assertEqual(response.status_code, 200, f"Expected 200, got {response.status_code}: {response.text}")
        
        data = response.json()
        self.assertIn("oauth_url", data, "Response should contain oauth_url")
        self.assertIn("state", data, "Response should contain state parameter")
        
        # Parse the OAuth URL to verify parameters
        parsed_url = urlparse(data["oauth_url"])
        query_params = parse_qs(parsed_url.query)
        
        self.assertEqual(query_params.get("client_id", [""])[0], self.oauth_data["app_id"], 
                         "OAuth URL should contain correct client_id")
        self.assertEqual(query_params.get("response_type", [""])[0], "code", 
                         "OAuth URL should have response_type=code")
        self.assertEqual(query_params.get("state", [""])[0], data["state"], 
                         "OAuth URL state should match response state")
        
        # Store state for callback test
        self.oauth_state = data["state"]
        
        print("✅ OAuth start endpoint working correctly")
        print(f"🔗 OAuth URL generated: {data['oauth_url'][:60]}...")
        return data
    
    def test_02_oauth_callback_route(self):
        """Test that the OAuth callback route exists and returns HTML"""
        print("\n🔍 Testing OAuth callback route...")
        
        # Make a GET request to the callback URL without parameters
        response = requests.get(f"{BACKEND_URL}/auth/blackbaud/callback")
        
        self.assertEqual(response.status_code, 200, 
                         f"Expected 200, got {response.status_code}: {response.text}")
        self.assertIn("text/html", response.headers.get("Content-Type", ""), 
                      "Response should be HTML")
        
        # Check for key elements in the HTML
        html_content = response.text
        self.assertIn("Blackbaud Authentication", html_content, 
                      "HTML should contain title")
        self.assertIn("OAuth Callback Debug Info", html_content, 
                      "HTML should contain debug info section")
        
        print("✅ OAuth callback route exists and returns HTML")
    
    def test_03_oauth_callback_with_parameters(self):
        """Test the OAuth callback route with mock parameters"""
        print("\n🔍 Testing OAuth callback route with parameters...")
        
        # First, get a valid state from the OAuth start endpoint
        if not hasattr(self, 'oauth_state'):
            oauth_data = self.test_01_oauth_start_endpoint()
            if not oauth_data:
                self.skipTest("Failed to get OAuth state")
        
        # Make a GET request to the callback URL with mock parameters
        params = {
            "code": "mock_auth_code",
            "state": self.oauth_state
        }
        
        response = requests.get(f"{BACKEND_URL}/auth/blackbaud/callback", params=params)
        
        self.assertEqual(response.status_code, 200, 
                         f"Expected 200, got {response.status_code}: {response.text}")
        
        # Check that the parameters are displayed in the HTML
        html_content = response.text
        self.assertIn("mock_auth_code", html_content, 
                      "HTML should display the code parameter")
        self.assertIn(self.oauth_state[:10], html_content, 
                      "HTML should display the state parameter")
        
        print("✅ OAuth callback route correctly displays parameters")
    
    def test_04_oauth_callback_api_endpoint(self):
        """Test the OAuth callback API endpoint"""
        if not self.auth_token:
            self.skipTest("Authentication failed during setup")
            
        if not hasattr(self, 'oauth_state'):
            oauth_data = self.test_01_oauth_start_endpoint()
            if not oauth_data:
                self.skipTest("Failed to get OAuth state")
        
        print("\n🔍 Testing OAuth callback API endpoint...")
        
        # This will fail with invalid_grant since we're using a mock code
        # but we can test that the endpoint exists and processes the request
        callback_data = {
            "code": "mock_auth_code",
            "state": self.oauth_state,
            "merchant_id": self.oauth_data["merchant_id"]
        }
        
        response = requests.post(f"{API_URL}/organizations/bbms-oauth/callback", json=callback_data)
        
        # We expect a 400 error because the code is invalid
        self.assertEqual(response.status_code, 400, 
                         f"Expected 400 for invalid code, got {response.status_code}: {response.text}")
        
        error_data = response.json()
        self.assertIn("detail", error_data, "Error response should contain detail")
        self.assertIn("code", error_data.get("detail", "").lower(), 
                      "Error should mention invalid code or authorization code")
        
        print("✅ OAuth callback API endpoint correctly rejects invalid code")
    
    def test_05_test_oauth_credentials_endpoint(self):
        """Test the endpoint for testing OAuth credentials"""
        if not self.auth_token:
            self.skipTest("Authentication failed during setup")
        
        print("\n🔍 Testing OAuth credentials test endpoint...")
        
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        response = requests.post(
            f"{API_URL}/organizations/test-oauth-credentials", 
            json=self.oauth_data,
            headers=headers
        )
        
        self.assertEqual(response.status_code, 200, 
                         f"Expected 200, got {response.status_code}: {response.text}")
        
        data = response.json()
        self.assertIn("oauth_url", data, "Response should contain oauth_url")
        self.assertIn("app_id_used", data, "Response should contain app_id_used")
        self.assertEqual(data.get("app_id_used"), self.oauth_data["app_id"], 
                         "Response should use the provided app_id")
        
        print("✅ OAuth credentials test endpoint working correctly")

def run_tests():
    # Create a test suite with our tests
    suite = unittest.TestSuite()
    suite.addTest(BlackbaudOAuthTest('test_01_oauth_start_endpoint'))
    suite.addTest(BlackbaudOAuthTest('test_02_oauth_callback_route'))
    suite.addTest(BlackbaudOAuthTest('test_03_oauth_callback_with_parameters'))
    suite.addTest(BlackbaudOAuthTest('test_04_oauth_callback_api_endpoint'))
    suite.addTest(BlackbaudOAuthTest('test_05_test_oauth_credentials_endpoint'))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return appropriate exit code
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    sys.exit(run_tests())
