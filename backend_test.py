
import requests
import sys
import os
import json
import time
from urllib.parse import urlparse, parse_qs

class BlackbaudOAuthTester:
    def __init__(self, base_url="https://c44b0daf-083b-41cc-aa42-f9e46f580f6f.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.organization_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        if not headers:
            headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"Error details: {json.dumps(error_data, indent=2)}")
                except:
                    print(f"Response text: {response.text}")
                return False, None

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, None

    def test_register_and_login(self):
        """Register a test organization and login"""
        import random
        import string
        
        # Generate random credentials
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        org_name = f"Test Org {random_suffix}"
        email = f"test{random_suffix}@example.com"
        password = "TestPass123!"
        
        # Register
        success, response = self.run_test(
            "Register Organization",
            "POST",
            "organizations/register",
            200,
            data={
                "name": org_name,
                "admin_email": email,
                "admin_password": password
            }
        )
        
        if not success:
            print("❌ Registration failed, trying login with default credentials")
            # Try login with default credentials
            success, response = self.run_test(
                "Login with Default Credentials",
                "POST",
                "organizations/login",
                200,
                data={
                    "email": "test@example.com",
                    "password": "password123"
                }
            )
            
            if not success:
                return False
        
        # Store token and organization ID
        self.token = response.get('access_token')
        self.organization_id = response.get('organization', {}).get('id')
        
        print(f"✅ Authentication successful - Organization ID: {self.organization_id}")
        return True

    def test_oauth_callback_route(self):
        """Test if the OAuth callback route is accessible"""
        print("\n🔍 Testing OAuth callback route...")
        
        # Test direct access to the callback URL
        callback_url = f"{self.base_url}/api/blackbaud-callback"
        
        try:
            response = requests.get(callback_url)
            if response.status_code == 200:
                print(f"✅ Callback route is accessible - Status: {response.status_code}")
                
                # Check if the response contains expected HTML elements
                html_content = response.text.lower()
                if "blackbaud authentication" in html_content and "oauth callback debug info" in html_content:
                    print("✅ Callback page contains expected content")
                    return True
                else:
                    print("❌ Callback page doesn't contain expected content")
                    return False
            else:
                print(f"❌ Callback route is not accessible - Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error accessing callback route: {str(e)}")
            return False

    def test_oauth_callback_with_params(self):
        """Test the OAuth callback with test parameters"""
        print("\n🔍 Testing OAuth callback with parameters...")
        
        # Test parameters
        test_code = "test_auth_code"
        test_state = "test_state_parameter"
        
        callback_url = f"{self.base_url}/api/blackbaud-callback?code={test_code}&state={test_state}"
        
        try:
            response = requests.get(callback_url)
            if response.status_code == 200:
                print(f"✅ Callback with parameters is accessible - Status: {response.status_code}")
                
                # Check if the response contains our test parameters
                html_content = response.text
                if test_code in html_content and test_state in html_content:
                    print("✅ Callback page correctly displays the provided parameters")
                    return True
                else:
                    print("❌ Callback page doesn't display the provided parameters")
                    return False
            else:
                print(f"❌ Callback with parameters is not accessible - Status: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error accessing callback with parameters: {str(e)}")
            return False

    def test_oauth_start_flow(self):
        """Test starting the OAuth flow"""
        if not self.token or not self.organization_id:
            print("❌ Authentication required before testing OAuth flow")
            return False
            
        print("\n🔍 Testing OAuth start flow...")
        
        # Test data for OAuth start
        oauth_data = {
            "merchant_id": "96563c2e-c97a-4db1-a0ed-1b2a8219f110",
            "app_id": "2e2c42a7-a2f5-4fd3-a0bc-d4b3b36d8cea",
            "app_secret": "3VuF4BNX72+dClCDheqMN7xPfsu29GKGxdaobEIbWXU="
        }
        
        success, response = self.run_test(
            "Start OAuth Flow",
            "POST",
            "organizations/bbms-oauth/start",
            200,
            data=oauth_data
        )
        
        if not success:
            return False
            
        # Check if we got an OAuth URL and state parameter
        oauth_url = response.get('oauth_url')
        state = response.get('state')
        
        if not oauth_url or not state:
            print("❌ OAuth start response missing required fields")
            return False
            
        print(f"✅ OAuth URL generated: {oauth_url[:60]}...")
        print(f"✅ State parameter: {state[:30]}...")
        
        # Parse the OAuth URL to verify parameters
        parsed_url = urlparse(oauth_url)
        query_params = parse_qs(parsed_url.query)
        
        required_params = ['client_id', 'response_type', 'redirect_uri', 'state', 'scope']
        missing_params = [param for param in required_params if param not in query_params]
        
        if missing_params:
            print(f"❌ OAuth URL missing required parameters: {', '.join(missing_params)}")
            return False
            
        # Verify redirect URI
        redirect_uri = query_params.get('redirect_uri', [''])[0]
        expected_redirect = f"{self.base_url}/api/blackbaud-callback"
        
        if redirect_uri != expected_redirect:
            print(f"❌ Incorrect redirect URI. Expected: {expected_redirect}, Got: {redirect_uri}")
            return False
            
        print(f"✅ OAuth URL contains correct redirect URI: {redirect_uri}")
        return True

    def test_oauth_credentials_validation(self):
        """Test the OAuth credentials validation endpoint"""
        if not self.token:
            print("❌ Authentication required before testing OAuth credentials")
            return False
            
        print("\n🔍 Testing OAuth credentials validation...")
        
        # Test data for OAuth credentials
        test_data = {
            "merchant_id": "96563c2e-c97a-4db1-a0ed-1b2a8219f110",
            "app_id": "2e2c42a7-a2f5-4fd3-a0bc-d4b3b36d8cea",
            "app_secret": "3VuF4BNX72+dClCDheqMN7xPfsu29GKGxdaobEIbWXU="
        }
        
        success, response = self.run_test(
            "Test OAuth Credentials",
            "POST",
            "organizations/test-oauth-credentials",
            200,
            data=test_data
        )
        
        if not success:
            return False
            
        # Check if we got the expected response fields
        required_fields = ['oauth_url', 'app_id_used', 'redirect_uri']
        missing_fields = [field for field in required_fields if field not in response]
        
        if missing_fields:
            print(f"❌ Response missing required fields: {', '.join(missing_fields)}")
            return False
            
        # Verify redirect URI
        redirect_uri = response.get('redirect_uri')
        expected_redirect = f"{self.base_url}/api/blackbaud-callback"
        
        if redirect_uri != expected_redirect:
            print(f"❌ Incorrect redirect URI. Expected: {expected_redirect}, Got: {redirect_uri}")
            return False
            
        print(f"✅ OAuth credentials validation successful")
        print(f"✅ Redirect URI: {redirect_uri}")
        return True

def main():
    tester = BlackbaudOAuthTester()
    
    # Run tests
    print("\n===== BLACKBAUD OAUTH INTEGRATION TESTS =====\n")
    
    # Test 1: Register and login
    if not tester.test_register_and_login():
        print("❌ Authentication failed, stopping tests")
        return 1
        
    # Test 2: OAuth callback route
    callback_route_ok = tester.test_oauth_callback_route()
    
    # Test 3: OAuth callback with parameters
    callback_params_ok = tester.test_oauth_callback_with_params()
    
    # Test 4: OAuth start flow
    oauth_start_ok = tester.test_oauth_start_flow()
    
    # Test 5: OAuth credentials validation
    oauth_creds_ok = tester.test_oauth_credentials_validation()
    
    # Print summary
    print("\n===== TEST SUMMARY =====")
    print(f"OAuth Callback Route: {'✅ PASS' if callback_route_ok else '❌ FAIL'}")
    print(f"OAuth Callback Parameters: {'✅ PASS' if callback_params_ok else '❌ FAIL'}")
    print(f"OAuth Start Flow: {'✅ PASS' if oauth_start_ok else '❌ FAIL'}")
    print(f"OAuth Credentials Validation: {'✅ PASS' if oauth_creds_ok else '❌ FAIL'}")
    
    # Overall result
    all_passed = callback_route_ok and callback_params_ok and oauth_start_ok and oauth_creds_ok
    print(f"\nOverall Result: {'✅ PASS' if all_passed else '❌ FAIL'}")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
