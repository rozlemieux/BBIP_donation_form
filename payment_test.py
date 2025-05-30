#!/usr/bin/env python3
"""
Payment API Test Script for Donation Page Builder

This script specifically tests the payment checkout endpoint with the updated
Blackbaud payment API endpoint (/payments/checkout/sessions).
"""

import requests
import sys
import os
import json
import time
import uuid
from urllib.parse import urlparse, parse_qs

class BlackbaudPaymentTester:
    def __init__(self, base_url="https://8b2b653e-9dbe-4e45-9ea1-8a28a59c538d.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.organization_id = None
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

    def authenticate(self):
        """Authenticate with the API using default credentials"""
        print("\n🔍 Authenticating with the API...")
        
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
            # Try to register a new organization
            import random
            import string
            
            # Generate random credentials
            random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            org_name = f"Test Org {random_suffix}"
            email = f"test{random_suffix}@example.com"
            password = "TestPass123!"
            
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
                return False
        
        # Store token and organization ID
        self.token = response.get('access_token')
        self.organization_id = response.get('organization', {}).get('id')
        
        print(f"✅ Authentication successful - Organization ID: {self.organization_id}")
        return True

    def test_payment_checkout_endpoint(self):
        """Test the payment checkout endpoint with the updated Blackbaud payment API endpoint"""
        print("\n🔍 Testing payment checkout endpoint...")
        
        if not self.organization_id:
            print("❌ Organization ID required for testing payment checkout")
            return False
            
        # Create a test donation
        donation_data = {
            "org_id": self.organization_id,
            "amount": 25.00,
            "donor_name": "Test Donor",
            "donor_email": "donor@example.com",
            "payment_method": "credit_card",
            "credit_card": {
                "number": "4111111111111111",
                "exp_month": 12,
                "exp_year": 2030,
                "cvc": "123"
            },
            "billing_address": {
                "line1": "123 Test St",
                "city": "Test City",
                "state": "TS",
                "postal_code": "12345",
                "country": "US"
            }
        }
        
        success, response = self.run_test(
            "Create Donation",
            "POST",
            "donations/checkout",
            200,  # Expecting 200 OK
            data=donation_data
        )
        
        if not success:
            return False
            
        # Check if the response contains information about the Blackbaud API call
        print("\n🔍 Checking Blackbaud API endpoint in the response...")
        
        # The response might contain debug information about the Blackbaud API call
        # Look for the endpoint in the response
        response_str = json.dumps(response)
        
        if "/payments/checkout/sessions" in response_str:
            print("✅ Blackbaud payment API endpoint is correctly set to /payments/checkout/sessions")
            return True
        elif "/payments/v1/checkouts" in response_str:
            print("❌ Blackbaud payment API endpoint is still using the old endpoint: /payments/v1/checkouts")
            return False
        else:
            print("❓ Could not find Blackbaud payment API endpoint in the response")
            
            # Try to extract any information about the Blackbaud API call
            if "blackbaud" in response_str.lower():
                print("ℹ️ Found Blackbaud-related information in the response:")
                blackbaud_info = [line for line in response_str.split("\n") if "blackbaud" in line.lower()]
                for line in blackbaud_info:
                    print(f"  {line}")
            
            # Check server logs for more information
            print("\n🔍 Checking server logs for Blackbaud API endpoint information...")
            try:
                import subprocess
                log_output = subprocess.check_output(
                    "tail -n 100 /var/log/supervisor/backend.*.log | grep -i 'blackbaud\\|payment\\|checkout\\|session'",
                    shell=True
                ).decode('utf-8')
                
                if log_output:
                    print("ℹ️ Found relevant information in server logs:")
                    print(log_output)
                    
                    if "/payments/checkout/sessions" in log_output:
                        print("✅ Server logs confirm the Blackbaud payment API endpoint is correctly set to /payments/checkout/sessions")
                        return True
                    elif "/payments/v1/checkouts" in log_output:
                        print("❌ Server logs show the Blackbaud payment API endpoint is still using the old endpoint: /payments/v1/checkouts")
                        return False
            except Exception as e:
                print(f"❌ Error checking server logs: {str(e)}")
            
            # If we couldn't determine the endpoint from the response or logs, check the code
            print("\n🔍 Checking server code for Blackbaud API endpoint...")
            try:
                with open("/app/backend/server.py", "r") as f:
                    server_code = f.read()
                    
                if "/payments/checkout/sessions" in server_code:
                    print("✅ Server code contains the updated Blackbaud payment API endpoint: /payments/checkout/sessions")
                    return True
                elif "/payments/v1/checkouts" in server_code:
                    print("❌ Server code still contains the old Blackbaud payment API endpoint: /payments/v1/checkouts")
                    return False
                else:
                    print("❓ Could not find Blackbaud payment API endpoint in the server code")
            except Exception as e:
                print(f"❌ Error checking server code: {str(e)}")
            
            return False

def main():
    tester = BlackbaudPaymentTester()
    
    # Run tests
    print("\n===== BLACKBAUD PAYMENT API ENDPOINT TEST =====\n")
    
    # Test 1: Authenticate
    if not tester.authenticate():
        print("❌ Authentication failed, stopping tests")
        return 1
        
    # Test 2: Payment checkout endpoint
    payment_checkout_ok = tester.test_payment_checkout_endpoint()
    
    # Print summary
    print("\n===== TEST SUMMARY =====")
    print(f"Payment Checkout Endpoint: {'✅ PASS' if payment_checkout_ok else '❌ FAIL'}")
    
    # Overall result
    print(f"\nOverall Result: {'✅ PASS' if payment_checkout_ok else '❌ FAIL'}")
    
    return 0 if payment_checkout_ok else 1

if __name__ == "__main__":
    sys.exit(main())