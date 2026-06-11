import os
import json
import csv
import time
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from google.oauth2 import service_account
from googleapiclient.discovery import build

KEY_FILE_LOCATION = 'gsc-credentials.json'
SITEMAP_URL = 'https://thanhthaimotor.com/sitemap.xml'
SITE_URL = 'https://thanhthaimotor.com/'
OUTPUT_CSV = 'bao_cao_index_thanhthaimotor.csv'
MAX_URLS = 10  # Reduced to 10 for speed and safety

def get_urls_from_sitemap(url, limit=50):
    urls = []
    try:
        print(f"Fetching sitemap: {url}", flush=True)
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return urls
            
        root = ET.fromstring(response.content)
        namespaces = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        if root.tag.endswith('sitemapindex'):
            for sitemap in root.findall('ns:sitemap/ns:loc', namespaces):
                sub_url = sitemap.text
                urls.extend(get_urls_from_sitemap(sub_url, limit))
                if len(urls) > limit:
                    break
        elif root.tag.endswith('urlset'):
            for url_node in root.findall('ns:url/ns:loc', namespaces):
                urls.append(url_node.text)
                if len(urls) > limit:
                    break
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
    except Exception as e:
        print(f"Lỗi khi inspect URL {url}: {e}", flush=True)
        return {
            'url': url,
            'verdict': 'ERROR',
            'coverageState': str(e).split('\n')[0][:50],
            'lastCrawlTime': 'N/A'
        }

def main():
    print(f"Bắt đầu tải và bóc tách sitemap...", flush=True)
    all_urls = get_urls_from_sitemap(SITEMAP_URL, limit=MAX_URLS)
    all_urls = list(set(all_urls))[:MAX_URLS]
    
    print(f"Sẽ tiến hành kiểm tra {len(all_urls)} URL...", flush=True)
    
    service = initialize_gsc()
    if not service:
        return
        
    print(f"Đang ghi ra file {OUTPUT_CSV}...", flush=True)
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['url', 'verdict', 'coverageState', 'lastCrawlTime'])
        writer.writeheader()
        
        for i, url in enumerate(all_urls):
            print(f"[{i+1}/{len(all_urls)}] Đang kiểm tra: {url}", flush=True)
            result = inspect_url(service, url)
            writer.writerow(result)
            f.flush()
            time.sleep(1)
            
    print(f"Hoàn thành xuất báo cáo!", flush=True)

if __name__ == '__main__':
    main()
