import sys
import os
import logging
import requests
import json

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

class DriveCleaner:
    def __init__(self):
        try:
            self.config = Config()
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
            sys.exit(1)
            
        self.token = self._get_tenant_token()

    def _get_tenant_token(self):
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": self.config.APP_ID, "app_secret": self.config.APP_SECRET})
        if resp.status_code == 200:
            return resp.json().get("tenant_access_token")
        logging.error(f"Failed to get token: {resp.text}")
        sys.exit(1)

    def list_files(self):
        """List all files owned by the bot."""
        url = "https://open.feishu.cn/open-apis/drive/v1/files"
        headers = {"Authorization": f"Bearer {self.token}"}
        
        files = []
        page_token = None
        
        print("🔍 Scanning for files... (This might take a moment)")
        
        while True:
            params = {
                "page_size": 50,
                "direction": "DESC", 
                "order_by": "CreatedTime" 
            }
            if page_token:
                params["page_token"] = page_token
                
            try:
                resp = requests.get(url, headers=headers, params=params)
                if resp.status_code != 200:
                    logging.error(f"Error listing files: {resp.text}")
                    break
                    
                data = resp.json().get("data", {})
                current_files = data.get("files", [])
                if not current_files:
                    break
                    
                files.extend(current_files)
                
                if not data.get("has_more"):
                    break
                page_token = data.get("page_token")
                
            except Exception as e:
                logging.error(f"Exception listing files: {e}")
                break
        
        return files

    def delete_file(self, file_token, file_type):
        """Delete a file (move to trash)."""
        url = f"https://open.feishu.cn/open-apis/drive/v1/files/{file_token}"
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {"type": file_type}
        
        try:
            resp = requests.delete(url, headers=headers, params=params)
            if resp.status_code == 200:
                return True
            else:
                logging.error(f"Failed to delete {file_token}: {resp.text}")
                return False
        except Exception as e:
            logging.error(f"Exception deleting file: {e}")
            return False

def main():
    cleaner = DriveCleaner()
    
    # 1. List Files
    files = cleaner.list_files()
    if not files:
        print("✅ No files found.")
        return

    print(f"\n📂 Found {len(files)} files total.")
    
    # 2. Filter (Optional: You can hardcode a filter here if you want)
    # For now, let's just list them and ask for a range or keyword
    
    print("\n--- Recent Files ---")
    for i, f in enumerate(files[:20]): # Show top 20
        print(f"[{i}] {f['name']} (Type: {f['type']}, Token: {f['token']})")
    
    if len(files) > 20:
        print(f"... and {len(files) - 20} more.")

    print("\n⚠️  DANGER ZONE ⚠️")
    print("Options:")
    print("1. Delete specific file by index")
    print("2. Delete by keyword (matches filename)")
    print("3. Delete ALL files (Type 'DELETE_ALL')")
    print("4. Exit (default)")
    
    choice = input("\nSelect an option (1-4): ").strip()
    
    to_delete = []
    
    if choice == '1':
        idx_str = input("Enter file index (e.g. 0): ").strip()
        if idx_str.isdigit():
            idx = int(idx_str)
            if 0 <= idx < len(files):
                to_delete.append(files[idx])
            else:
                print("❌ Invalid index.")
                return
    
    elif choice == '2':
        keyword = input("Enter keyword to match: ").strip()
        if not keyword:
            print("❌ No keyword provided.")
            return
            
        to_delete = [f for f in files if keyword.lower() in f['name'].lower()]
        print(f"Found {len(to_delete)} files matching '{keyword}'.")

    elif choice == 'DELETE_ALL' or choice == '3': # Allow 3 as well, but still ask for rigorous confirmation
        if choice == '3':
             confirm_text = input("Type 'DELETE_ALL' to proceed with deleting EVERYTHING: ")
             if confirm_text != "DELETE_ALL":
                 print("❌ Aborted.")
                 return

        confirm = input("Wait. Are you SURE you want to delete EVERYTHING? (Type 'yes I am sure'): ")
        if confirm == "yes I am sure":
            to_delete = files
        else:
            print("❌ Aborted.")
            return
    else:
        print("Exiting.")
        return

    if not to_delete:
        print("No files selected to delete.")
        return

    # Final Confirmation
    print(f"\nPreparing to delete {len(to_delete)} files...")
    for f in to_delete[:5]:
        print(f"- {f['name']}")
    if len(to_delete) > 5:
        print(f"... and {len(to_delete) - 5} others")
        
    confirm = input("\nType 'yes' to confirm deletion: ")
    if confirm.lower() != 'yes':
        print("❌ Cancelled.")
        return
        
    # Execute
    count = 0
    for f in to_delete:
        if cleaner.delete_file(f['token'], f['type']):
            print(f"🗑️ Deleted: {f['name']}")
            count += 1
        else:
            print(f"❌ Failed: {f['name']}")
            
    print(f"\n✅ Operation complete. Deleted {count} files.")

if __name__ == "__main__":
    main()
