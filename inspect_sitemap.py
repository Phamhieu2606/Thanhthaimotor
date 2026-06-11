import os
import json
import csv
import time
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

KEY_FILE_LOCATION = 'gsc-credentials.json'
SITEMAP_URL = 'https://thanhthaimotor.com/sitemap.xml'
SITE_URL = 'https://thanhthaimotor.com/'
OUTPUT_CSV = 'bao_cao_index_thanhthaimotor.csv'
MAX_URLS = 2000  # Quota tối đa một ngày của GSC URL Inspection API

def get_urls_from_sitemap(url):
    urls = []
    try:
        print(f"Fetching sitemap: {url}", flush=True)
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            return urls
            
        root = ET.fromstring(response.content)
        namespaces = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        if root.tag.endswith('sitemapindex'):
            for sitemap in root.findall('ns:sitemap/ns:loc', namespaces):
                sub_url = sitemap.text
                urls.extend(get_urls_from_sitemap(sub_url))
        elif root.tag.endswith('urlset'):
            for url_node in root.findall('ns:url/ns:loc', namespaces):
                urls.append(url_node.text)
    except Exception as e:
        print(f"Lỗi khi đọc sitemap {url}: {e}", flush=True)
        
    return urls

def initialize_gsc():
    try:
        credentials = service_account.Credentials.from_service_account_file(
            KEY_FILE_LOCATION, 
            scopes=['https://www.googleapis.com/auth/webmasters.readonly']
        )
        service = build('searchconsole', 'v1', credentials=credentials)
        return service
    except Exception as e:
        print(f"Lỗi khi xác thực Service Account: {e}", flush=True)
        return None

def inspect_url(service, url):
    try:
        request_body = {
            "inspectionUrl": url,
            "siteUrl": SITE_URL,
            "languageCode": "vi-VN"
        }
        response = service.urlInspection().index().inspect(body=request_body).execute()
        inspection_result = response.get('inspectionResult', {})
        index_status = inspection_result.get('indexStatusResult', {})
        
        return {
            'url': url,
            'verdict': index_status.get('verdict', 'UNKNOWN'),
            'coverageState': index_status.get('coverageState', 'UNKNOWN'),
            'lastCrawlTime': index_status.get('lastCrawlTime', 'N/A')
        }
    except HttpError as e:
        error_details = json.loads(e.content.decode())
        error_message = error_details.get('error', {}).get('message', str(e))
        print(f"Lỗi API khi inspect URL {url}: {error_message}", flush=True)
        if e.resp.status == 429 or 'Quota' in error_message:
            raise Exception("Vượt quá Quota API!") # Bắn lỗi để dừng chương trình
            
        return {
            'url': url,
            'verdict': 'ERROR',
            'coverageState': error_message[:50],
            'lastCrawlTime': 'N/A'
        }
    except Exception as e:
        print(f"Lỗi khi inspect URL {url}: {e}", flush=True)
        return {
            'url': url,
            'verdict': 'ERROR',
            'coverageState': str(e).split('\n')[0][:50],
            'lastCrawlTime': 'N/A'
        }

def get_already_checked_urls():
    checked_urls = set()
    if os.path.exists(OUTPUT_CSV):
        try:
            with open(OUTPUT_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    checked_urls.add(row['url'])
        except Exception as e:
            print(f"Lỗi khi đọc file CSV cũ: {e}")
    return checked_urls

def main():
    print(f"Bắt đầu tải và bóc tách toàn bộ sitemap...", flush=True)
    all_urls = get_urls_from_sitemap(SITEMAP_URL)
    all_urls = list(set(all_urls))
    
    print(f"Đã quét được tổng cộng {len(all_urls)} URL duy nhất từ website.", flush=True)
    
    # Lấy danh sách URL đã kiểm tra để bỏ qua
    checked_urls = get_already_checked_urls()
    print(f"Đã có {len(checked_urls)} URL được kiểm tra trước đó.", flush=True)
    
    # Lọc ra những URL chưa kiểm tra
    urls_to_check = [url for url in all_urls if url not in checked_urls]
    
    if not urls_to_check:
        print("Tất cả URL đã được kiểm tra! Không còn URL mới nào.", flush=True)
        return
        
    print(f"Còn lại {len(urls_to_check)} URL cần kiểm tra.", flush=True)
    
    # Giới hạn số lượng check theo Quota còn lại
    urls_to_check = urls_to_check[:MAX_URLS]
    print(f"Sẽ tiến hành kiểm tra {len(urls_to_check)} URL trong phiên chạy này...", flush=True)
    
    service = initialize_gsc()
    if not service:
        return
        
    file_exists = os.path.exists(OUTPUT_CSV)
    
    print(f"Đang ghi tiếp ra file {OUTPUT_CSV}...", flush=True)
    with open(OUTPUT_CSV, 'a', newline='', encoding='utf-8') as f:
        fieldnames = ['url', 'verdict', 'coverageState', 'lastCrawlTime']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        # Nếu file chưa tồn tại thì ghi Header
        if not file_exists:
            writer.writeheader()
            
        for i, url in enumerate(urls_to_check):
            print(f"[{i+1}/{len(urls_to_check)}] Đang kiểm tra: {url}", flush=True)
            try:
                result = inspect_url(service, url)
                writer.writerow(result)
                f.flush()
                # Nghỉ 1 giây để tránh Rate Limit (600 requests / phút)
                time.sleep(1)
            except Exception as e:
                print(f"Dừng tiến trình: {e}", flush=True)
                break
            
    print(f"Hoàn thành kiểm tra và lưu báo cáo. File đã được cập nhật!", flush=True)
    
    # Tự động commit và push sau khi chạy xong (do script chạy ngầm)
    print("Đang tiến hành Git Push...", flush=True)
    os.system('git add bao_cao_index_thanhthaimotor.csv inspect_sitemap.py')
    os.system('git commit -m "Cập nhật dữ liệu Index của các URL còn lại"')
    os.system('git push origin main')
    print("Đã Push thành công lên GitHub!", flush=True)

if __name__ == '__main__':
    main()
