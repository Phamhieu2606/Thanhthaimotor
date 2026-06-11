import os
import csv
import requests
import xml.etree.ElementTree as ET
import concurrent.futures
from bs4 import BeautifulSoup
import extruct
from urllib.parse import urlparse

SITEMAP_URL = 'https://thanhthaimotor.com/sitemap.xml'
OUTPUT_CSV = 'bao_cao_schema_thanhthaimotor.csv'

def get_urls_from_sitemap(url):
    urls = []
    try:
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

def extract_schema_types(data):
    types = set()
    if isinstance(data, dict):
        # json-ld thường dùng @type
        if '@type' in data:
            val = data['@type']
            if isinstance(val, list):
                types.update(val)
            else:
                types.add(val)
        # microdata thường dùng type
        if 'type' in data:
            val = data['type']
            if isinstance(val, list):
                # remove namespace URLs
                for v in val:
                    types.add(v.split('/')[-1])
            elif isinstance(val, str):
                types.add(val.split('/')[-1])
                
        for k, v in data.items():
            types.update(extract_schema_types(v))
    elif isinstance(data, list):
        for item in data:
            types.update(extract_schema_types(item))
    return types

def process_url(url):
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            return {
                'url': url,
                'schema_types': 'ERROR_HTTP',
                'status': 'Không có Schema'
            }
            
        html = response.text
        # Sử dụng extruct để lấy schema (cả JSON-LD và Microdata)
        data = extruct.extract(html, base_url=url, syntaxes=['json-ld', 'microdata'])
        
        all_types = set()
        
        if data.get('json-ld'):
            all_types.update(extract_schema_types(data['json-ld']))
            
        if data.get('microdata'):
            all_types.update(extract_schema_types(data['microdata']))
            
        if not all_types:
            # Dự phòng: Thử tìm bằng BeautifulSoup thủ công nếu extruct lỗi
            soup = BeautifulSoup(html, 'html.parser')
            for script in soup.find_all('script', type='application/ld+json'):
                import json
                try:
                    json_data = json.loads(script.string)
                    all_types.update(extract_schema_types(json_data))
                except:
                    pass
                    
        types_list = list(all_types)
        
        if types_list:
            return {
                'url': url,
                'schema_types': ', '.join(types_list),
                'status': 'Có Schema'
            }
        else:
            return {
                'url': url,
                'schema_types': '',
                'status': 'Không có Schema'
            }
            
    except Exception as e:
        return {
            'url': url,
            'schema_types': f"Lỗi: {str(e)[:30]}",
            'status': 'Không có Schema'
        }

def main():
    print("Bắt đầu cào Sitemap...", flush=True)
    all_urls = get_urls_from_sitemap(SITEMAP_URL)
    all_urls = list(set(all_urls))
    
    print(f"Tổng số URL cần quét Schema: {len(all_urls)}", flush=True)
    
    results = []
    
    # Sử dụng 10 luồng song song để quét nhanh hơn (không quá cao để tránh sập web)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_url, url): url for url in all_urls}
        
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            result = future.result()
            results.append(result)
            
            if completed % 10 == 0 or completed == len(all_urls):
                print(f"Đã xử lý: {completed}/{len(all_urls)} URLs...", flush=True)
                
    # Ghi ra CSV
    print(f"Đang ghi kết quả ra {OUTPUT_CSV}...", flush=True)
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['url', 'schema_types', 'status'])
        writer.writeheader()
        writer.writerows(results)
        
    print("Hoàn tất! Bắt đầu Commit lên GitHub...", flush=True)
    os.system('git add bao_cao_schema_thanhthaimotor.csv check_schema.py')
    os.system('git commit -m "Cập nhật báo cáo phân tích Schema tự động"')
    os.system('git push origin main')
    print("Đã tự động Push file lên GitHub thành công!", flush=True)

if __name__ == '__main__':
    main()
