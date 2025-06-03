
import requests
import json
import uuid

# Base URL from the frontend .env file
BASE_URL = "https://e86128f5-e40b-4462-b145-2b55c23a63a0.preview.emergentagent.com"
API_URL = f"{BASE_URL}/api"

# Generate unique test data
test_org_name = f"Test Organization {uuid.uuid4().hex[:8]}"
test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
test_password = "TestPassword123!"

print(f"Testing registration with: {test_org_name}, {test_email}, {test_password}")

# Test registration endpoint
registration_data = {
    "name": test_org_name,
    "admin_email": test_email,
    "admin_password": test_password
}

try:
    response = requests.post(
        f"{API_URL}/organizations/register",
        json=registration_data,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status Code: {response.status_code}")
    
    try:
        response_json = response.json()
        print("Response JSON:")
        print(json.dumps(response_json, indent=2))
    except:
        print("Response Text (not JSON):")
        print(response.text)
        
except Exception as e:
    print(f"Error: {str(e)}")
