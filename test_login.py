
import requests
import json

# Base URL from the frontend .env file
BASE_URL = "https://8b2b653e-9dbe-4e45-9ea1-8a28a59c538d.preview.emergentagent.com"
API_URL = f"{BASE_URL}/api"

# Use the credentials from the previous test
test_email = "test_93b4d9be@example.com"
test_password = "TestPassword123!"

print(f"Testing login with: {test_email}, {test_password}")

# Test login endpoint
login_data = {
    "email": test_email,
    "password": test_password
}

try:
    response = requests.post(
        f"{API_URL}/organizations/login",
        json=login_data,
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
