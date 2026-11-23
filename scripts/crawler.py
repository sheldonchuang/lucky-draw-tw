import urllib.request
import re
import json
import time
from datetime import datetime
from html import unescape

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    return text.strip()

def fetch_url(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def parse_deadline(date_str):
    # 找最後一個日期 yyyy/mm/dd 或 yyyy-mm-dd
    matches = re.findall(r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})', date_str)
    if matches:
        return matches[-1].replace('-', '/')
    return ""

def crawl():
    print("正在抓取 onelife.tw 活動清單...")
    list_html = fetch_url("https://onelife.tw/lucky-draw")
    if not list_html:
        return []

    # 抓取活動連結
    event_ids = list(dict.fromkeys(re.findall(r'/a/(\d+)', list_html)))
    print(f"共發現 {len(event_ids)} 個活動 ID")

    results = []
    # 抓取前 35 個活動作為精選真實資料
    target_ids = event_ids[:35]

    for idx, eid in enumerate(target_ids, 1):
        url = f"https://onelife.tw/a/{eid}"
        print(f"[{idx}/{len(target_ids)}] 正在解析活動 {eid}...")
        html = fetch_url(url)
        if not html:
            continue

        # 標題
        title_match = re.search(r'<title>(.*?)</title>', html, re.S)
        title = title_match.group(1).replace(' - onelife', '').strip() if title_match else ''

        # 圖片
        og_img = re.search(r'<meta property=\"og:image\" content=\"(.*?)\"', html)
        img_url = og_img.group(1) if og_img else ''

        # 品牌
        brand_match = re.search(r'<a href=\"[^\"]*\" id=\"[^\"]*aShortName\"[^>]*>(.*?)</a>', html)
        brand = clean_text(brand_match.group(1)).replace('活動訊息', '').strip() if brand_match else ''
        if not brand:
            brand_m2 = re.search(r'<h2 class=\"h2\"><a[^>]*>(.*?)</a></h2>', html)
            brand = clean_text(brand_m2.group(1)) if brand_m2 else '精選品牌'

        # 官網
        official_match = re.search(r'<a href=\"(http[^\"]*)\" id=\"[^\"]*aOfficialUrl\"', html)
        official_url = official_match.group(1) if official_match else ''

        # 活動專屬網站 (從外部連結中篩選出活動網站或來源連結)
        ext_links = re.findall(r'<a [^>]*href=[\"\'](https?://(?!onelife\.tw|www\.facebook\.com/onelife|www\.google\.com/search)[^\"\']+)[\"\'][^>]*>(.*?)</a>', html)
        
        act_url = ""
        for h, text in ext_links:
            clean_t = clean_text(text)
            if '活動網站' in clean_t or '來源連結' in clean_t or '活動辦法' in clean_t:
                act_url = h
                break
        if not act_url and ext_links:
            # 取不是官網的那個，或是第一個外部連結
            for h, text in ext_links:
                if h != official_url:
                    act_url = h
                    break
        if not act_url:
            act_url = official_url

        # 時間
        time_match = re.search(r'活動時間：(.*?)</p>', html)
        raw_time = clean_text(time_match.group(1)) if time_match else ''
        deadline = parse_deadline(raw_time)

        # 抽獎資格
        qual_match = re.search(r'抽獎資格：(.*?)</p>', html, re.S)
        qualification = clean_text(qual_match.group(1)) if qual_match else ''

        # 獎項清單 (抓出獎品亮點)
        prizes = []
        p_matches = re.findall(r'●(.*?)<br', html)
        if not p_matches:
            p_matches = re.findall(r'抽(.*?)[，。、\n\r]', title)
        for p in p_matches:
            cp = clean_text(p)
            if cp and len(cp) < 60 and cp not in prizes:
                prizes.append(cp)

        if not prizes:
            prizes = ["依主辦單位公佈獎項為準"]

        # 標籤精準判定 (依照真實活動規則)
        tags = []
        c_qual = qualification + " " + title
        
        # 1. 超商專區
        convenience_stores = ['7-11', '7-ELEVEN', '全家', 'FamilyMart', '萊爾富', 'OK超商', 'OK Mart']
        if any(cs in brand or cs in title or cs in qualification for cs in convenience_stores):
            tags.append('超商專區')

        # 2. 登錄發票即抽
        invoice_keywords = ['發票', '載具', '明細', '購買證明', '電子發票']
        if any(ik in c_qual for ik in invoice_keywords):
            tags.append('登錄發票即抽')

        # 3. 免消費即抽
        free_keywords = ['集章', '留言', '問卷', '免消費', '登入即', '會員簽到', '拍照上傳', '免費參加', '綁定line', '加入會員']
        # 若沒有說需要「購買」或「消費」，或者是集章/留言/問卷
        if any(fk in c_qual for fk in free_keywords) or ('不限消費' in c_qual or '免費' in c_qual):
            tags.append('免消費即抽')
        elif '貼紙' in c_qual or '開瓶' in c_qual or '序號' in c_qual:
            tags.append('開蓋序號抽')
        elif '購買' in c_qual and '登錄發票即抽' not in tags:
            tags.append('消費登錄抽')

        # 4. 抽獎品項核心標籤 (抽機票、抽iPhone、抽家電)
        lower_all = (title + " " + " ".join(prizes) + " " + qualification).lower()
        if any(k in lower_all for k in ['機票', '雙人遊', '機加酒', '旅遊金', '出國', '米蘭', '東京', '北海道', '芬蘭', '峇里島', '泰國', '日本']):
            tags.append('抽機票')
        if any(k in lower_all for k in ['iphone', 'iphone16', 'iphone17', 'iphone18', '手機', '摺疊機', 'apple']):
            tags.append('抽iPhone')
        if any(k in lower_all for k in ['電烤盤', '電視', '空氣清淨機', '音響', '電鍋', '按摩椅', 'dyson', 'panasonic', 'switch', 'bruno', '家電', '自行車', '機車', '吸塵器']):
            tags.append('抽家電')

        if not tags:
            tags.append('熱門好康')

        results.append({
            'id': eid,
            'title': title,
            'brand': brand,
            'tags': tags,
            'time': raw_time,
            'deadline': deadline,
            'qualification': qualification[:300] + ('...' if len(qualification) > 300 else ''),
            'prizes': prizes[:5],
            'imageUrl': img_url,
            'activityUrl': act_url,
            'officialUrl': official_url
        })
        time.sleep(0.3)

    return results

if __name__ == '__main__':
    data = crawl()
    with open('/Users/sheldonair/.gemini/antigravity/scratch/lucky-draw-tw/events.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 同步生成 data.js 保證免伺服器也能即時讀取
    js_content = 'window.INITIAL_EVENTS = ' + json.dumps(data, ensure_ascii=False) + ';'
    with open('/Users/sheldonair/.gemini/antigravity/scratch/lucky-draw-tw/data.js', 'w', encoding='utf-8') as f:
        f.write(js_content)

    print(f"成功儲存 {len(data)} 筆真實活動資料至 events.json 與 data.js！")
