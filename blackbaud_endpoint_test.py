#!/usr/bin/env python3
"""
Blackbaud API Endpoint Verification Test

This script verifies that the Blackbaud payment API endpoint has been updated
from `/payments/v1/checkouts` to `/payments/checkout/sessions` in the server code.
"""

import sys
import os
import re

def check_blackbaud_endpoint():
    """Check if the Blackbaud payment API endpoint has been updated in the server code."""
    server_file = "/app/backend/server.py"
    
    print("\n🔍 Checking Blackbaud payment API endpoint in server code...")
    
    try:
        with open(server_file, "r") as f:
            server_code = f.read()
        
        # Check for the new endpoint
        new_endpoint_pattern = r"['\"]https?://[^'\"]+/payments/checkout/sessions['\"]|f['\"].+/payments/checkout/sessions['\"]"
        new_endpoint_matches = re.findall(new_endpoint_pattern, server_code)
        
        # Check for the old endpoint
        old_endpoint_pattern = r"['\"]https?://[^'\"]+/payments/v1/checkouts['\"]|f['\"].+/payments/v1/checkouts['\"]"
        old_endpoint_matches = re.findall(old_endpoint_pattern, server_code)
        
        print(f"✅ Found {len(new_endpoint_matches)} references to the new endpoint '/payments/checkout/sessions'")
        print(f"✅ Found {len(old_endpoint_matches)} references to the old endpoint '/payments/v1/checkouts'")
        
        if len(new_endpoint_matches) > 0 and len(old_endpoint_matches) == 0:
            print("\n✅ PASS: The Blackbaud payment API endpoint has been successfully updated to '/payments/checkout/sessions'")
            return True
        elif len(new_endpoint_matches) > 0 and len(old_endpoint_matches) > 0:
            print("\n⚠️ WARNING: Both old and new endpoints are present in the code")
            return False
        elif len(new_endpoint_matches) == 0 and len(old_endpoint_matches) > 0:
            print("\n❌ FAIL: The Blackbaud payment API endpoint has not been updated")
            return False
        else:
            print("\n❓ UNKNOWN: No Blackbaud payment API endpoints found in the code")
            return False
    
    except Exception as e:
        print(f"\n❌ ERROR: Failed to check server code: {str(e)}")
        return False

def check_request_structure():
    """Check if the request structure for the Blackbaud payment API is correct."""
    server_file = "/app/backend/server.py"
    
    print("\n🔍 Checking Blackbaud payment API request structure...")
    
    try:
        with open(server_file, "r") as f:
            server_code = f.read()
        
        # Find the section where the API call is made
        api_call_pattern = r"async with httpx\.AsyncClient\(\) as client:.*?response = await client\.post\((.*?)\)"
        api_call_match = re.search(api_call_pattern, server_code, re.DOTALL)
        
        if not api_call_match:
            print("\n❌ FAIL: Could not find the API call in the server code")
            return False
        
        api_call_text = api_call_match.group(0)
        
        # Check if the API call includes the correct headers and JSON data
        headers_check = "headers=headers" in api_call_text
        json_check = "json=checkout_data" in api_call_text
        
        print(f"✅ API call includes headers: {headers_check}")
        print(f"✅ API call includes JSON data: {json_check}")
        
        if headers_check and json_check:
            print("\n✅ PASS: The Blackbaud payment API request structure is correct")
            return True
        else:
            print("\n❌ FAIL: The Blackbaud payment API request structure is incorrect")
            return False
    
    except Exception as e:
        print(f"\n❌ ERROR: Failed to check request structure: {str(e)}")
        return False

def check_checkout_data_structure():
    """Check if the checkout data structure for the Blackbaud payment API is correct."""
    server_file = "/app/backend/server.py"
    
    print("\n🔍 Checking Blackbaud payment API checkout data structure...")
    
    try:
        with open(server_file, "r") as f:
            server_code = f.read()
        
        # Find the section where the checkout data is defined
        checkout_data_pattern = r"checkout_data = {(.*?)}"
        checkout_data_match = re.search(checkout_data_pattern, server_code, re.DOTALL)
        
        if not checkout_data_match:
            print("\n❌ FAIL: Could not find the checkout data in the server code")
            return False
        
        checkout_data_text = checkout_data_match.group(1)
        
        # Check if the checkout data includes the required fields
        required_fields = [
            "merchant_account_id",
            "amount",
            "return_url",
            "cancel_url",
            "metadata"
        ]
        
        field_checks = {field: field in checkout_data_text for field in required_fields}
        
        for field, present in field_checks.items():
            print(f"✅ Checkout data includes {field}: {present}")
        
        # Check if the amount field includes value and currency
        amount_structure_check = '"value"' in checkout_data_text and '"currency"' in checkout_data_text
        print(f"✅ Amount field includes value and currency: {amount_structure_check}")
        
        # Check if the metadata field includes required information
        metadata_fields = ["donor_email", "donor_name", "org_id", "test_mode"]
        metadata_checks = {field: field in checkout_data_text for field in metadata_fields}
        
        for field, present in metadata_checks.items():
            print(f"✅ Metadata includes {field}: {present}")
        
        if all(field_checks.values()) and amount_structure_check and all(metadata_checks.values()):
            print("\n✅ PASS: The Blackbaud payment API checkout data structure is correct")
            return True
        else:
            print("\n❌ FAIL: The Blackbaud payment API checkout data structure is missing required fields")
            return False
    
    except Exception as e:
        print(f"\n❌ ERROR: Failed to check checkout data structure: {str(e)}")
        return False

def main():
    """Main function to run the tests."""
    print("===== BLACKBAUD PAYMENT API ENDPOINT VERIFICATION =====")
    
    # Test 1: Check if the Blackbaud payment API endpoint has been updated
    endpoint_ok = check_blackbaud_endpoint()
    
    # Test 2: Check if the request structure is correct
    request_ok = check_request_structure()
    
    # Test 3: Check if the checkout data structure is correct
    data_ok = check_checkout_data_structure()
    
    # Print summary
    print("\n===== TEST SUMMARY =====")
    print(f"Blackbaud Payment API Endpoint: {'✅ PASS' if endpoint_ok else '❌ FAIL'}")
    print(f"Blackbaud Payment API Request Structure: {'✅ PASS' if request_ok else '❌ FAIL'}")
    print(f"Blackbaud Payment API Checkout Data Structure: {'✅ PASS' if data_ok else '❌ FAIL'}")
    
    # Overall result
    overall_ok = endpoint_ok and request_ok and data_ok
    print(f"\nOverall Result: {'✅ PASS' if overall_ok else '❌ FAIL'}")
    
    return 0 if overall_ok else 1

if __name__ == "__main__":
    sys.exit(main())