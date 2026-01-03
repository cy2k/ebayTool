import os
import urllib.parse
import base64
import requests
import json
from datetime import datetime, timedelta

# Constants for OAuth
EBAY_OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
EBAY_AUTHORIZE_URL = "https://auth.ebay.com/oauth2/authorize"
SCOPES = (
    "https://api.ebay.com/oauth/api_scope "
    "https://api.ebay.com/oauth/api_scope/sell.inventory "
    "https://api.ebay.com/oauth/api_scope/sell.account"
)

class EbayAuth:
    def __init__(self, app_id, cert_id, ru_name):
        self.app_id = app_id
        self.cert_id = cert_id
        self.ru_name = ru_name
        self.tokens = {}  # { 'type': {'access_token': ..., 'refresh_token': ...} }

    def get_authorization_url(self, state_name):
        """Generates the URL for the user to login and approve the app."""
        params = {
            "client_id": self.app_id,
            "response_type": "code",
            "redirect_uri": self.ru_name,
            "scope": SCOPES,
            "state": state_name # Use to distinguish 'source' vs 'target'
        }
        return f"{EBAY_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    def fetch_token(self, code, account_type):
        """Exchanges the auth code for access and refresh tokens."""
        credentials = f"{self.app_id}:{self.cert_id}"
        encoded_creds = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_creds}"
        }
        
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.ru_name
        }

        response = requests.post(EBAY_OAUTH_URL, headers=headers, data=data)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch token: {response.text}")
            
        token_data = response.json()
        self._save_token(account_type, token_data)
        return token_data

    def refresh_token(self, account_type):
        """Refreshes an expired access token using the refresh token."""
        # Load existing manually to get the refresh token
        saved = self.load_saved_token(account_type)
        if not saved or 'refresh_token' not in saved:
            return None
            
        print(f"Refreshing expired token for {account_type}...")
        
        credentials = f"{self.app_id}:{self.cert_id}"
        encoded_creds = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_creds}"
        }
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": saved['refresh_token']
        }
        
        # Scopes usually not needed for refresh, but if needed, add specific scopes
        # data['scope'] = SCOPES 

        response = requests.post(EBAY_OAUTH_URL, headers=headers, data=data)
        if response.status_code == 200:
            new_data = response.json()
            # Merge new data with old (keep refresh token if not returned)
            if 'refresh_token' not in new_data:
                new_data['refresh_token'] = saved['refresh_token']
                
            self._save_token(account_type, new_data)
            return new_data['access_token']
        else:
            print(f"Failed to refresh token: {response.text}")
            return None

    def _save_token(self, account_type, token_data):
        # Calculate expiry timestamp for easier checking
        expires_in = token_data.get('expires_in', 7200)
        token_data['expiry_time'] = (datetime.now() + timedelta(seconds=expires_in - 60)).isoformat()
        
        self.tokens[account_type] = token_data
        os.makedirs("data/tokens", exist_ok=True)
        with open(f"data/tokens/{account_type}_token.json", "w") as f:
            json.dump(token_data, f)
            
    def load_saved_token(self, account_type):
        if account_type in self.tokens:
            return self.tokens[account_type]
            
        try:
            with open(f"data/tokens/{account_type}_token.json", "r") as f:
                data = json.load(f)
                self.tokens[account_type] = data
                return data
        except FileNotFoundError:
            return None
        except json.JSONDecodeError:
            return None

    def get_access_token(self, account_type):
        """Smart getter: Load -> Check Expiry -> Refresh if needed -> Return"""
        token_data = self.load_saved_token(account_type)
        if not token_data:
            return None
            
        # Check Expiry
        expiry_str = token_data.get('expiry_time')
        if expiry_str:
            expiry = datetime.fromisoformat(expiry_str)
            if datetime.now() > expiry:
                # Expired -> Refresh
                return self.refresh_token(account_type)
        
        return token_data.get('access_token')

