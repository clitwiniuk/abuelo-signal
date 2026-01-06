#!/usr/bin/env python3
"""
Create TradeTally user and get API token for local instance
"""
import requests
import json

def create_tradetally_user():
    """Create user and get API token for local TradeTally instance"""
    base_url = "http://localhost:3001/api"
    
    # User registration data
    user_data = {
        "username": "trading_system",
        "email": "trading@example.com",
        "password": "TradingSystem2025!"
    }
    
    print("🔐 Creating TradeTally user...")
    
    try:
        # Register user
        response = requests.post(f"{base_url}/auth/register", json=user_data)
        
        if response.status_code == 201:
            print("✅ User created successfully")
        elif response.status_code == 400 and "already exists" in response.text:
            print("ℹ️ User already exists, proceeding to login...")
        else:
            print(f"❌ Registration failed: {response.status_code} - {response.text}")
            return None
        
        # Login to get token
        login_data = {
            "email": user_data["email"],
            "password": user_data["password"]
        }
        
        print("🔑 Logging in to get API token...")
        response = requests.post(f"{base_url}/auth/login", json=login_data)
        
        if response.status_code == 200:
            data = response.json()
            token = data.get('token')
            user_id = data.get('user', {}).get('id')
            
            print(f"✅ Login successful!")
            print(f"📋 User ID: {user_id}")
            print(f"🔑 API Token: {token}")
            
            # Test the token
            headers = {'Authorization': f'Bearer {token}'}
            test_response = requests.get(f"{base_url}/trades", headers=headers)
            
            if test_response.status_code == 200:
                print("✅ Token validation successful")
                return token
            else:
                print(f"❌ Token validation failed: {test_response.status_code}")
                return None
        else:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to TradeTally. Make sure the backend is running on localhost:3001")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    token = create_tradetally_user()
    if token:
        print(f"\n🎯 Update your config.ini with:")
        print(f"api_key = {token}")
    else:
        print("\n💥 Failed to create user or get token")
