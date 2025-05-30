import requests
import json
import sys
import time
from datetime import datetime

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

    def test_oauth_start(self, merchant_id="96563c2e-c97a-4db1-a0ed-1b2a8219f110", app_id="3VuF4BNX72+dClCDheqMN7xPfsu29GKGxdaobEIbWXU=", app_secret="3VuF4BNX72+dClCDheqMN7xPfsu29GKGxdaobEIbWXU="):
        """Test starting the OAuth flow with real credentials"""
        if not self.token:
            print("❌ No auth token available")
            return False, None
            
        print("\n🔄 Starting OAuth flow with real credentials...")
        print(f"Using Merchant ID: {merchant_id}")
        print(f"Using App ID: {app_id[:10]}...")
        
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

def main():
    tester = OAuthFlowTester()
    
    # Step 1: Login to get organization ID
    if not tester.login():
        print("❌ Cannot proceed without login")
        return 1
    
    # Step 2: Check initial organization state
    print("\n📊 INITIAL ORGANIZATION STATE:")
    initial_success, initial_state = tester.check_organization_state()
    
    if not initial_success:
        print("❌ Failed to get initial organization state")
    else:
        print(f"Initial has_bb_access_token: {initial_state.get('has_bb_access_token', False)}")
        print(f"Initial has_bb_merchant_id: {initial_state.get('has_bb_merchant_id', False)}")
    
    # Step 3: Start OAuth flow
    oauth_success, oauth_data = tester.test_oauth_start()
    
    if not oauth_success:
        print("❌ Cannot proceed with OAuth flow")
        return 1
    
    # Step 4: Simulate OAuth callback
    # In a real scenario, the user would be redirected to Blackbaud and then back to our callback URL
    # Here we're simulating the callback with a test code
    callback_success, callback_data = tester.test_oauth_callback(
        code="test_authorization_code",
        state=oauth_data.get('state'),
        merchant_id="test_merchant_123"
    )
    
    # Step 5: Check final organization state
    print("\n📊 FINAL ORGANIZATION STATE:")
    final_success, final_state = tester.check_organization_state()
    
    if not final_success:
        print("❌ Failed to get final organization state")
    else:
        print(f"Final has_bb_access_token: {final_state.get('has_bb_access_token', False)}")
        print(f"Final has_bb_merchant_id: {final_state.get('has_bb_merchant_id', False)}")
    
    # Print summary
    print("\n📋 TEST SUMMARY:")
    print(f"Tests run: {tester.tests_run}")
    print(f"Tests passed: {tester.tests_passed}")
    
    if callback_success:
        print("✅ OAuth flow completed successfully")
    else:
        print("❌ OAuth flow failed")
    
    return 0 if callback_success else 1

if __name__ == "__main__":
    sys.exit(main())
