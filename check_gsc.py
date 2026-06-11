import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

KEY_FILE_LOCATION = 'gsc-credentials.json'

def get_email_from_json():
    try:
        with open(KEY_FILE_LOCATION, 'r') as f:
            data = json.load(f)
            return data.get('client_email', 'Không tìm thấy email trong file')
    except Exception:
        return 'Lỗi đọc file json'

def initialize_gsc():
    try:
        credentials = service_account.Credentials.from_service_account_file(
            KEY_FILE_LOCATION, 
            scopes=['https://www.googleapis.com/auth/webmasters.readonly']
        )
        service = build('webmasters', 'v3', credentials=credentials)
        return service
    except Exception as e:
        print(f"Lỗi khi xác thực Service Account: {e}")
        return None

def main():
    service = initialize_gsc()
    if not service:
        return

    print("Đã xác thực thành công bằng Service Account!")
    
    try:
        site_list = service.sites().list().execute()
        sites = site_list.get('siteEntry', [])
        
        email = get_email_from_json()
        
        if not sites:
            print("\nCẢNH BÁO: Service Account chưa được cấp quyền truy cập vào bất kỳ trang web nào!")
            print("Vui lòng đăng nhập Google Search Console, thêm email sau làm người dùng (Quyền Đầy đủ/Hạn chế):")
            print(f"Email: {email}")
            print("Tên miền của bạn: https://thanhthaimotor.com/ (hoặc sc-domain:thanhthaimotor.com)")
        else:
            print("\nTUYỆT VỜI! Service Account đã được liên kết với các trang web sau:")
            for site in sites:
                print(f"- {site['siteUrl']} (Quyền: {site['permissionLevel']})")
                
    except Exception as e:
        print(f"Lỗi khi lấy danh sách trang web: {e}")

if __name__ == '__main__':
    main()
