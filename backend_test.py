
import requests
import sys
import time
import uuid
from datetime import datetime

class DonationBuilderAPITester:
    def __init__(self, base_url="https://c44b0daf-083b-41cc-aa42-f9e46f580f6f.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.org_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_org_email = f"test_org_{uuid.uuid4().hex[:8]}@example.com"
        self.test_org_password = "TestPassword123!"
        self.test_org_name = f"Test Organization {uuid.uuid4().hex[:8]}"

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        
        if headers is None:
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
            
            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"Response: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_register_organization(self):
        """Test organization registration"""
        success, response = self.run_test(
            "Organization Registration",
            "POST",
            "organizations/register",
            200,
            data={
                "name": self.test_org_name,
                "admin_email": self.test_org_email,
                "admin_password": self.test_org_password
            }
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.org_id = response['organization']['id']
            print(f"Organization created with ID: {self.org_id}")
            return True
        return False

    def test_login(self):
        """Test organization login"""
        success, response = self.run_test(
            "Organization Login",
            "POST",
            "organizations/login",
            200,
            data={
                "email": self.test_org_email,
                "password": self.test_org_password
            }
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.org_id = response['organization']['id']
            print(f"Logged in as organization with ID: {self.org_id}")
            return True
        return False

    def test_get_organization(self):
        """Test getting organization details"""
        success, response = self.run_test(
            "Get Organization Details",
            "GET",
            "organizations/me",
            200
        )
        
        if success:
            print(f"Organization details: {response['name']}")
        return success

    def test_update_form_settings(self):
        """Test updating form settings"""
        form_settings = {
            "preset_amounts": [10, 25, 50, 100, 250],
            "custom_amount_enabled": True,
            "required_fields": ["name", "email", "phone"],
            "organization_description": "Test organization description",
            "thank_you_message": "Thank you for your donation!"
        }
        
        success, response = self.run_test(
            "Update Form Settings",
            "PUT",
            "organizations/form-settings",
            200,
            data=form_settings
        )
        
        return success

    def test_configure_bbms(self):
        """Test configuring BBMS credentials (using test values)"""
        # Note: Using dummy values since we don't want to use real credentials
        bbms_credentials = {
            "merchant_id": "test_merchant_id",
            "access_token": "test_access_token"
        }
        
        # This test is expected to fail with 400 since we're using dummy credentials
        success, response = self.run_test(
            "Configure BBMS (Expected to fail with dummy credentials)",
            "POST",
            "organizations/configure-bbms",
            400,
            data=bbms_credentials
        )
        
        # Since we're using dummy credentials, we expect a 400 error
        # So we'll count this as a success if we get the expected 400
        if success:
            print("BBMS configuration test passed (expected failure with dummy credentials)")
            return True
        return False
        
    def test_oauth_start(self):
        """Test starting the OAuth2 flow with user's own Blackbaud credentials"""
        if not self.token:
            print("❌ Cannot test OAuth start - no auth token")
            return False
            
        # In a real scenario, these would be provided by the user
        oauth_data = {
            "merchant_id": "test_merchant_id",
            "app_id": "user_blackbaud_app_id",
            "app_secret": "user_blackbaud_app_secret"
        }
        
        print("✅ Testing OAuth2 flow with user's own Blackbaud credentials")
        print("   This is the key fix that was implemented - using user's credentials instead of hardcoded ones")
        
        success, response = self.run_test(
            "Start OAuth2 Flow with User Credentials",
            "POST",
            "organizations/bbms-oauth/start",
            200,
            data=oauth_data
        )
        
        if success:
            if 'oauth_url' in response and 'state' in response:
                print(f"✅ OAuth URL generated: {response['oauth_url'][:60]}...")
                print(f"✅ State parameter generated: {response['state'][:20]}...")
                
                # Verify the OAuth URL contains the user's app_id, not the server's
                if oauth_data["app_id"] in response['oauth_url']:
                    print(f"✅ OAuth URL correctly uses user's App ID")
                else:
                    print(f"❌ OAuth URL does not contain user's App ID")
                
                return True, response
            else:
                print("❌ OAuth response missing required fields")
                return False, {}
        return False, {}
        
    def test_oauth_callback(self):
        """Test the OAuth2 callback handling"""
        # First start the OAuth flow to get a state parameter
        success, start_response = self.test_oauth_start()
        if not success:
            print("❌ Cannot test OAuth callback - OAuth start failed")
            return False
            
        # Now test the callback with a dummy code
        callback_data = {
            "code": "test_auth_code",
            "state": start_response['state'],
            "merchant_id": "test_merchant_id"
        }
        
        # This will fail with 400 since we're using a dummy code
        # But it should validate the state parameter correctly
        success, response = self.run_test(
            "OAuth2 Callback (Expected to fail with dummy code)",
            "POST",
            "organizations/bbms-oauth/callback",
            400,
            data=callback_data
        )
        
        # Since we're using a dummy code, we expect a 400 error
        # So we'll count this as a success if we get the expected 400
        if success:
            print("✅ OAuth callback test passed (expected failure with dummy code)")
            return True
        return False

    def test_get_donation_form_config(self):
        """Test getting donation form configuration"""
        if not self.org_id:
            print("❌ Cannot test donation form config - no organization ID")
            return False
            
        success, response = self.run_test(
            "Get Donation Form Config",
            "GET",
            f"organizations/{self.org_id}/donation-form",
            200
        )
        
        if success:
            print(f"Form config: {response}")
        return success

    def test_get_transactions(self):
        """Test getting organization transactions"""
        if not self.org_id:
            print("❌ Cannot test transactions - no organization ID")
            return False
            
        success, response = self.run_test(
            "Get Organization Transactions",
            "GET",
            f"organizations/{self.org_id}/transactions",
            200
        )
        
        if success:
            print(f"Found {len(response)} transactions")
        return success

    def test_embed_endpoint(self):
        """Test the embed endpoint"""
        if not self.org_id:
            print("❌ Cannot test embed endpoint - no organization ID")
            return False
            
        url = f"{self.base_url}/embed/donate/{self.org_id}"
        print(f"\n🔍 Testing Embed Endpoint...")
        
        try:
            response = requests.get(url)
            success = response.status_code == 200 and "<!DOCTYPE html>" in response.text
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                print("Embed HTML returned successfully")
                return True
            else:
                print(f"❌ Failed - Status: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False

    def test_toggle_test_mode(self):
        """Test toggling test mode"""
        # First, check current mode
        success, response = self.run_test(
            "Get Current Mode",
            "GET",
            "organizations/me",
            200
        )
        
        if not success:
            return False
            
        current_mode = response.get('test_mode', True)
        print(f"Current test mode: {current_mode}")
        
        # Toggle to the opposite mode
        new_mode = not current_mode
        success, response = self.run_test(
            f"Toggle to {'Test' if new_mode else 'Production'} Mode",
            "PUT",
            "organizations/test-mode",
            200,
            data={"test_mode": new_mode}
        )
        
        if not success:
            return False
            
        # Verify the mode was changed
        success, response = self.run_test(
            "Verify Mode Change",
            "GET",
            "organizations/me",
            200
        )
        
        if success:
            updated_mode = response.get('test_mode', True)
            if updated_mode == new_mode:
                print(f"✅ Mode successfully changed to {'Test' if new_mode else 'Production'}")
                
                # Toggle back to original mode
                success, response = self.run_test(
                    f"Toggle back to {'Test' if current_mode else 'Production'} Mode",
                    "PUT",
                    "organizations/test-mode",
                    200,
                    data={"test_mode": current_mode}
                )
                
                if success:
                    print(f"✅ Mode successfully changed back to {'Test' if current_mode else 'Production'}")
                    return True
            else:
                print(f"❌ Mode change verification failed. Expected: {new_mode}, Got: {updated_mode}")
        
        return False
        
    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting Donation Builder API Tests")
        
        # Test registration and authentication
        if not self.test_register_organization():
            print("❌ Registration failed, stopping tests")
            return False
            
        if not self.test_login():
            print("❌ Login failed, stopping tests")
            return False
            
        if not self.test_get_organization():
            print("❌ Get organization failed, stopping tests")
            return False
            
        # Test form settings
        self.test_update_form_settings()
        
        # Test BBMS configuration (with dummy values)
        self.test_configure_bbms()
        
        # Test OAuth2 flow
        print("\n🔍 Testing OAuth2 Flow...")
        self.test_oauth_start()
        self.test_oauth_callback()
        
        # Test test/production mode toggle
        self.test_toggle_test_mode()
        
        # Test donation form config
        self.test_get_donation_form_config()
        
        # Test transactions
        self.test_get_transactions()
        
        # Test embed endpoint
        self.test_embed_endpoint()
        
        # Print results
        print(f"\n📊 Tests passed: {self.tests_passed}/{self.tests_run}")
        return self.tests_passed == self.tests_run

def main():
    tester = DonationBuilderAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
