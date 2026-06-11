import os
import json
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

KEY_FILE_LOCATION = 'gsc-credentials.json'

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

    # Thử gọi API để kiểm tra xem đã bật chưa
    try:
        site_list = service.sites().list().execute()
        sites = site_list.get('siteEntry', [])
        
        if not sites:
            print("API đã được bật thành công NHƯNG bạn chưa thêm email Service Account vào Google Search Console (hoặc thêm sai email)!")
            return
            
        print("API đã được bật và Website đã được cấp quyền! Đang lấy dữ liệu traffic...")
        
        # Lấy website đầu tiên trong danh sách (hoặc cố định url)
        site_url = sites[0]['siteUrl']
        
        # Tính toán ngày (7 ngày gần nhất)
        end_date = datetime.datetime.now() - datetime.timedelta(days=2) # GSC thường delay 2 ngày
        start_date = end_date - datetime.timedelta(days=7)
        
        request = {
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': end_date.strftime('%Y-%m-%d'),
            'dimensions': ['query'],
            'rowLimit': 10
        }
        
        response = service.searchanalytics().query(siteUrl=site_url, body=request).execute()
        
        print(f"\n===== DỮ LIỆU TRAFFIC (7 NGÀY QUA) CHO {site_url} =====")
        print(f"{'Từ khóa (Query)':<40} | {'Clicks':<8} | {'Hiển thị (Imp)':<15} | {'CTR (%)':<8} | {'Vị trí (Pos)'}")
        print("-" * 95)
        
        rows = response.get('rows', [])
        for row in rows:
            query = row['keys'][0]
            clicks = row['clicks']
            impressions = row['impressions']
            ctr = round(row['ctr'] * 100, 2)
            position = round(row['position'], 2)
            print(f"{query:<40} | {clicks:<8} | {impressions:<15} | {ctr:<8} | {position}")
            
        if not rows:
            print("Không có dữ liệu traffic nào trong 7 ngày qua.")
            
    except Exception as e:
        if "has not been used in project" in str(e) or "is disabled" in str(e):
            print("LỖI: Google Search Console API VẪN CHƯA ĐƯỢC BẬT (hoặc hệ thống của Google đang bị trễ).")
            print("Vui lòng truy cập link sau và nhấn nút ENABLE:")
            print("https://console.developers.google.com/apis/api/searchconsole.googleapis.com/overview?project=865173717834")
        else:
            print(f"Lỗi API: {e}")

if __name__ == '__main__':
    main()
