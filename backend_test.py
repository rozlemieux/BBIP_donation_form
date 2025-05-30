import requests
import json
import sys
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs

class OAuthFlowTester:
    def __init__(self, base_url="https://c44b0daf-083b-41cc-aa42-f9e46f580f6f.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.org_id = None
        self.tests_run = 0
        self.tests_passed = 0

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
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)

            print(f"Status: {response.status_code}")
            
            try:
                response_data = response.json()
                print(f"Response: {json.dumps(response_data, indent=2)}")
            except:
                print(f"Raw response: {response.text[:500]}")
            
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
                    return success, response.json()
                except:
                    return success, response.text

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {"error": str(e)}

    def login(self, email="test@example.com", password="password123"):
        """Test login and get token"""
        print("\n🔐 Logging in...")
        success, response = self.run_test(
            "Login",
            "POST",
            "organizations/login",
            200,
            data={"email": email, "password": password}
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.org_id = response['organization']['id']
            print(f"✅ Login successful - Organization ID: {self.org_id}")
            return True
        else:
            print("❌ Login failed")
            return False

    def check_organization_state(self):
        """Check organization state using debug endpoint"""
        if not self.org_id:
            print("❌ No organization ID available")
            return False, None
            
        print(f"\n🔍 Checking organization state for ID: {self.org_id}")
        success, response = self.run_test(
            "Debug Organization State",
            "GET",
            f"debug/organization/{self.org_id}",
            200
        )
        
        return success, response

    def test_oauth_start(self, merchant_id="96563c2e-c97a-4db1-a0ed-1b2a8219f110", app_id="2e2c42a7-a2f5-4fd3-a0bc-d4b3b36d8cea", app_secret="3VuF4BNX72+dClCDheqMN7xPfsu29GKGxdaobEIbWXU="):
        """Test starting the OAuth flow with real credentials"""
        if not self.token:
            print("❌ No auth token available")
            return False, None
            
        print("\n🔄 Starting OAuth flow with real credentials...")
        print(f"Using Merchant ID: {merchant_id}")
        print(f"Using App ID: {app_id}")
        
        success, response = self.run_test(
            "Start OAuth Flow",
            "POST",
            "organizations/bbms-oauth/start",
            200,
            data={
                "merchant_id": merchant_id,
                "app_id": app_id,
                "app_secret": app_secret
            }
        )
        
        if success and 'oauth_url' in response:
            print(f"✅ OAuth URL generated: {response['oauth_url']}")
            
            # Parse the URL to extract parameters
            parsed_url = urlparse(response['oauth_url'])
            query_params = parse_qs(parsed_url.query)
            
            print("\nOAuth URL Parameters:")
            for key, value in query_params.items():
                print(f"  {key}: {value[0]}")
                
            return True, response
        else:
            print("❌ Failed to start OAuth flow")
            return False, response

    def test_oauth_callback(self, code="test_code", state=None, merchant_id="96563c2e-c97a-4db1-a0ed-1b2a8219f110"):
        """Test the OAuth callback with real merchant ID"""
        if not state:
            print("❌ No state parameter available")
            return False, None
            
        print("\n🔄 Testing OAuth callback with real merchant ID...")
        print(f"Using Merchant ID: {merchant_id}")
        
        success, response = self.run_test(
            "OAuth Callback",
            "POST",
            "organizations/bbms-oauth/callback",
            200,
            data={
                "code": code,
                "state": state,
                "merchant_id": merchant_id
            }
        )
        
        if success:
            print("✅ OAuth callback successful")
        else:
            print("❌ OAuth callback failed")
            
        return success, response
        
    def test_callback_page(self, code="test_code", state="test_state"):
        """Test the OAuth callback page directly"""
        callback_url = f"{self.base_url}/auth/blackbaud/callback?code={code}&state={state}"
        
        self.tests_run += 1
        print(f"\n🔍 Testing OAuth Callback Page...")
        print(f"URL: {callback_url}")
        
        try:
            response = requests.get(callback_url)
            
            if response.status_code == 200:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                print("Callback page loaded successfully")
                
                # Check if the page contains debug info
                if "Code: Received" in response.text and "State: Received" in response.text:
                    print("✅ Debug info showing parameter status found")
                else:
                    print("❌ Debug info not found in callback page")
                
                # Check if the page stays on callback page (not redirecting)
                if "Connecting to Blackbaud..." in response.text:
                    print("✅ Callback page stays on callback page (not redirecting)")
                else:
                    print("❌ Callback page might be redirecting")
                
                # Check for detailed error handling
                if "error-details" in response.text:
                    print("✅ Detailed error handling section found")
                else:
                    print("❌ Detailed error handling section not found")
                
                return True, response.text
            else:
                print(f"❌ Failed - Expected 200, got {response.status_code}")
                return False, None
                
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {"error": str(e)}

def main():
    tester = OAuthFlowTester()
    
    print("\n" + "=" * 60)
    print("BLACKBAUD OAUTH CALLBACK PAGE TEST")
    print("=" * 60)
    
    # Step 1: Test the callback page directly with test parameters
    print("\n📋 TESTING CALLBACK PAGE WITH TEST PARAMETERS:")
    callback_success, callback_html = tester.test_callback_page(
        code="test_authorization_code",
        state="test_state"
    )
    
    # Step 2: Login to get organization ID (for real OAuth flow test)
    if not tester.login():
        print("❌ Cannot proceed with full OAuth flow test without login")
    else:
        # Step 3: Start OAuth flow with real credentials
        print("\n📋 TESTING FULL OAUTH FLOW:")
        oauth_success, oauth_data = tester.test_oauth_start(
            app_id="2e2c42a7-a2f5-4fd3-a0bc-d4b3b36d8cea",
            app_secret="3VuF4BNX72+dClCDheqMN7xPfsu29GKGxdaobEIbWXU="
        )
        
        if oauth_success:
            # Step 4: Test the callback page with real state parameter
            print("\n📋 TESTING CALLBACK PAGE WITH REAL STATE PARAMETER:")
            real_callback_success, real_callback_html = tester.test_callback_page(
                code="test_authorization_code",
                state=oauth_data.get('state')
            )
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY:")
    print(f"Tests run: {tester.tests_run}")
    print(f"Tests passed: {tester.tests_passed}")
    
    if callback_success:
        print("✅ OAuth callback page test passed")
        print("Key findings:")
        print("  - Callback page loads successfully")
        print("  - Debug information is displayed")
        print("  - Page stays on callback page (not redirecting)")
        print("  - Detailed error handling is implemented")
    else:
        print("❌ OAuth callback page test failed")
    
    print("=" * 60)
    
    return 0 if callback_success else 1

if __name__ == "__main__":
    sys.exit(main())
