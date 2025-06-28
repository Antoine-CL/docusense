import os
import msal
import requests
import tempfile
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

class GraphClient:
    def __init__(self):
        self.client_id = os.getenv("AAD_CLIENT_ID")
        self.tenant_id = os.getenv("AAD_TENANT_ID")
        self.client_secret = os.getenv("AAD_CLIENT_SECRET")
        
        if not all([self.client_id, self.tenant_id, self.client_secret]):
            print("⚠️  Missing Azure AD configuration. Please set AAD_CLIENT_ID, AAD_TENANT_ID, and AAD_CLIENT_SECRET")
            return
        
        # Create MSAL app for daemon/service authentication (v2.0 authority URL)
        self.app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret
        )
        
        self.scope = ["https://graph.microsoft.com/.default"]
        self.graph_url = "https://graph.microsoft.com/v1.0"
        self._token = None
    
    def get_token(self) -> Optional[str]:
        """Get access token for Microsoft Graph API"""
        try:
            # Remove any cached app tokens to force MSAL to request a new one
            try:
                self.app.remove_tokens_for_client()
            except AttributeError:
                # Older MSAL versions: clear the token cache manually
                self.app.token_cache.clear()

            result = self.app.acquire_token_for_client(scopes=self.scope)
            
            if "access_token" in result:
                self._token = result["access_token"]
                return self._token
            else:
                print(f"❌ Failed to acquire token: {result.get('error_description', 'Unknown error')}")
                return None
                
        except Exception as e:
            print(f"❌ Error acquiring token: {e}")
            return None
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers with authorization token"""
        token = self.get_token()
        if not token:
            raise Exception("Failed to get access token")
        
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def list_drives(self) -> List[Dict]:
        """List all drives accessible to the application"""
        try:
            headers = self.get_headers()
            
            # First try to get all drives
            response = requests.get(f"{self.graph_url}/drives", headers=headers)
            response.raise_for_status()
            
            drives = response.json().get("value", [])
            print(f"📁 Found {len(drives)} drives via /drives endpoint")
            
            # Also try to get sites and their document libraries
            try:
                sites_response = requests.get(f"{self.graph_url}/sites", headers=headers)
                if sites_response.status_code == 200:
                    sites = sites_response.json().get("value", [])
                    print(f"📁 Found {len(sites)} sites")
                    
                    # Get drives from each site
                    for site in sites[:3]:  # Limit to first 3 sites
                        site_id = site.get("id")
                        site_name = site.get("displayName", "Unknown")
                        try:
                            site_drives_response = requests.get(
                                f"{self.graph_url}/sites/{site_id}/drives",
                                headers=headers
                            )
                            if site_drives_response.status_code == 200:
                                site_drives = site_drives_response.json().get("value", [])
                                print(f"  📁 Site '{site_name}' has {len(site_drives)} drives")
                                drives.extend(site_drives)
                        except Exception as e:
                            print(f"  ⚠️  Could not get drives for site '{site_name}': {e}")
            except Exception as e:
                print(f"⚠️  Could not access sites: {e}")
            
            return drives
            
        except Exception as e:
            print(f"❌ Error listing drives: {e}")
            return []
    
    def list_files(self, drive_id: str, folder_path: str = "root") -> List[Dict]:
        """List files in a specific drive and folder"""
        try:
            headers = self.get_headers()
            
            # First try the standard approach
            url = f"{self.graph_url}/drives/{drive_id}/{folder_path}/children"
            params = {
                "$select": "id,name,size,lastModifiedDateTime,webUrl,file",
                "$filter": "file ne null",
                "$top": 100
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            # First try with filter
            if response.status_code == 200:
                files = response.json().get("value", [])
                print(f"📄 Found {len(files)} files in drive")
                return files
            
            # If 400/403, retry without the $filter (some SharePoint libraries don't support it)
            if response.status_code in (400, 403):
                params.pop("$filter", None)  # Remove the problematic filter
                response = requests.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    all_items = response.json().get("value", [])
                    # Filter files manually since we can't use $filter
                    files = [item for item in all_items if 'file' in item]
                    print(f"📄 Found {len(files)} files in drive (no $filter)")
                    return files
            
            # Final fallback - try search
            return self._search_files_recursive(drive_id, headers)
            
        except Exception as e:
            print(f"❌ Error listing files: {e}")
            return self._list_files_fallback(drive_id, headers)
    
    def _search_files_recursive(self, drive_id: str, headers: Dict[str, str]) -> List[Dict]:
        """Search for files recursively in the drive"""
        try:
            # Use search endpoint with simpler query
            url = f"{self.graph_url}/drives/{drive_id}/root/search(q='')"
            params = {
                "$select": "id,name,size,lastModifiedDateTime,webUrl,file",
                "$top": 50
            }
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            all_items = response.json().get("value", [])
            # Filter to only include files (items with 'file' property)
            files = [item for item in all_items if 'file' in item]
            
            print(f"📄 Found {len(files)} files through recursive search")
            return files
            
        except Exception as e:
            print(f"❌ Error in recursive search: {e}")
            return []
    
    def _list_files_fallback(self, drive_id: str, headers: Dict[str, str]) -> List[Dict]:
        """Fallback method to list files"""
        try:
            # Try the simplest possible query
            url = f"{self.graph_url}/drives/{drive_id}/root/children"
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                all_items = response.json().get("value", [])
                # Filter to only include files
                files = [item for item in all_items if 'file' in item]
                print(f"📄 Found {len(files)} files")
                return files
            else:
                return []
            
        except Exception as e:
            print(f"❌ Error in fallback method: {e}")
            return []
    
    def download_file(self, drive_id: str, item_id: str) -> Optional[str]:
        """Download a file and return the temporary file path"""
        try:
            headers = self.get_headers()
            
            # Get download URL
            download_url = f"{self.graph_url}/drives/{drive_id}/items/{item_id}/content"
            response = requests.get(download_url, headers=headers, stream=True)
            response.raise_for_status()
            
            # Create temporary file
            fd, temp_path = tempfile.mkstemp()
            
            # Write content to temporary file
            with open(fd, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return temp_path
            
        except Exception as e:
            print(f"❌ Error downloading file {item_id}: {e}")
            return None
    
    def get_file_info(self, drive_id: str, item_id: str) -> Optional[Dict]:
        """Get detailed information about a file"""
        try:
            headers = self.get_headers()
            response = requests.get(
                f"{self.graph_url}/drives/{drive_id}/items/{item_id}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            print(f"❌ Error getting file info: {e}")
            return None

# Create a global instance
graph_client = GraphClient()

def get_token():
    """Helper function to get token (for backward compatibility)"""
    return graph_client.get_token() 