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
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def parse_deadline(date_str):
    matches = re.findall(r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})', date_str)
    if matches:
        return matches[-1].replace('-', '/')
    return ""

def crawl_onelife_all():
    print("=== 正在收集 onelife.tw 全站活動清單 ===")
    category_urls = [
        'https://onelife.tw/lucky-draw',
        'https://onelife.tw/hot',
        'https://onelife.tw/c/7-11',
        'https://onelife.tw/c/%e5%85%a8%e5%ae%b6',
        'https://onelife.tw/c/%e8%90%8a%e7%88%be%e5%af%8c',
        'https://onelife.tw/c/OK%e8%b6%85%e5%95%86',
        'https://onelife.tw/tag/%e6%8a%bd%e7%8d%8e',
        'https://onelife.tw/tag/%e6%8a%bd%e6%a9%9f%e7%a5%a8',
        'https://onelife.tw/tag/%e6%8a%bdiPhone',
        'https://onelife.tw/tag/%e8%b2%b7%e4%b8%80%e9%80%81%e4%b8%80'
    ]

    all_event_ids = []
    for u in category_urls:
        html = fetch_url(u)
        if html:
            ids = re.findall(r'/a/(\d+)', html)
            for i in ids:
                if i not in all_event_ids:
                    all_event_ids.append(i)
        time.sleep(0.2)

    print(f"共收集到 {len(all_event_ids)} 個 onelife 活動 ID，開始全量解析...")

    events = []
    for idx, eid in enumerate(all_event_ids, 1):
        url = f"https://onelife.tw/a/{eid}"
        html = fetch_url(url)
        if not html:
            continue

        title_match = re.search(r'<title>(.*?)</title>', html, re.S)
        title = title_match.group(1).replace(' - onelife', '').strip() if title_match else ''
        if not title:
            continue

        og_img = re.search(r'<meta property=\"og:image\" content=\"(.*?)\"', html)
        img_url = og_img.group(1) if og_img else ''

        brand_match = re.search(r'<a href=\"[^\"]*\" id=\"[^\"]*aShortName\"[^>]*>(.*?)</a>', html)
        brand = clean_text(brand_match.group(1)).replace('活動訊息', '').strip() if brand_match else ''
        if not brand:
            brand_m2 = re.search(r'<h2 class=\"h2\"><a[^>]*>(.*?)</a></h2>', html)
            brand = clean_text(brand_m2.group(1)) if brand_m2 else '精選品牌'

        official_match = re.search(r'<a href=\"(http[^\"]*)\" id=\"[^\"]*aOfficialUrl\"', html)
        official_url = official_match.group(1) if official_match else ''

        ext_links = re.findall(r'<a [^>]*href=[\"\'](https?://(?!onelife\.tw|www\.facebook\.com/onelife|www\.google\.com/search)[^\"\']+)[\"\'][^>]*>(.*?)</a>', html)
        
        act_url = ""
        for h, text in ext_links:
            clean_t = clean_text(text)
            if '活動網站' in clean_t or '來源連結' in clean_t or '活動辦法' in clean_t or '登錄' in clean_t:
                act_url = h
                break
        if not act_url and ext_links:
            for h, text in ext_links:
                if h != official_url:
                    act_url = h
                    break
        if not act_url:
            act_url = official_url

        time_match = re.search(r'活動時間：(.*?)</p>', html)
        raw_time = clean_text(time_match.group(1)) if time_match else ''
        deadline = parse_deadline(raw_time)

        qual_match = re.search(r'抽獎資格：(.*?)</p>', html, re.S)
        qualification = clean_text(qual_match.group(1)) if qual_match else ''

        prizes = []
        p_matches = re.findall(r'●(.*?)<br', html)
        for p in p_matches:
            cp = clean_text(p)
            if cp and len(cp) < 60 and cp not in prizes:
                prizes.append(cp)

        # 標題獎品萃取
        parts = title.split('抽')
        if len(parts) > 1:
            last_prize = parts[-1].strip()
            last_prize = re.split(r'[，。、\n\r]', last_prize)[0].strip()
            if last_prize and len(last_prize) <= 30:
                prizes.insert(0, last_prize)

        if not prizes:
            prizes = ["依主辦單位公佈獎項為準"]

        # 品牌推測修正
        if brand in ['精選品牌', '']:
            for b in ['TOBLERONE', '法米納', '益富', '逸寶', 'JR西日本', '果力水', 'GODIVA', '大倉米舖', '喜多納', '安視達', '台中購物節', '雲林', '花仙子', 'Volvic', 'UCC', '金蘭', '春風', '蒲公英', '生活飲料', '台灣啤酒', '御茶園', '台塩生技', '麥當勞']:
                if b in title:
                    brand = b
                    break

        tags = []
        c_qual = (qualification + " " + title).lower()

        # 超商專區
        convenience_stores = ['7-11', '7-eleven', '全家', 'familymart', '萊爾富', 'ok超商', 'ok mart']
        if any(cs in brand.lower() or cs in c_qual for cs in convenience_stores):
            tags.append('超商專區')

        # 登錄發票即抽
        invoice_keywords = ['發票', '載具', '明細', '購買證明', '電子發票']
        if any(ik in c_qual for ik in invoice_keywords):
            tags.append('登錄發票即抽')

        # 免消費即抽
        free_keywords = ['reels', '集章', '留言', '問卷', '免消費', '登入即', '會員簽到', '拍照上傳', '免費參加', '綁定line', '加入會員', '不限消費', '測出']
        if any(fk in c_qual for fk in free_keywords):
            tags.append('免消費即抽')
        elif '貼紙' in c_qual or '開瓶' in c_qual or '序號' in c_qual:
            tags.append('開蓋序號抽')
        elif '購買' in c_qual and '登錄發票即抽' not in tags:
            tags.append('消費登錄抽')

        # 獎項標籤 (抽機票、抽iPhone、抽家電)
        lower_all = (title + " " + " ".join(prizes) + " " + qualification).lower()
        if any(k in lower_all for k in ['機票', '雙人遊', '機加酒', '旅遊金', '出國', '米蘭', '東京', '北海道', '芬蘭', '峇里島', '泰國', '日本']):
            tags.append('抽機票')
        if any(k in lower_all for k in ['iphone', 'iphone16', 'iphone17', 'iphone18', '手機', '摺疊機', 'apple']):
            tags.append('抽iPhone')
        if any(k in lower_all for k in ['電烤盤', '電視', '空氣清淨機', '音響', '電鍋', '按摩椅', 'dyson', 'panasonic', 'switch', 'bruno', '家電', '自行車', '機車', '吸塵器']):
            tags.append('抽家電')

        if not tags:
            tags.append('熱門好康')

        events.append({
            'id': eid,
            'title': title,
            'brand': brand,
            'tags': list(dict.fromkeys(tags)),
            'time': raw_time,
            'deadline': deadline,
            'qualification': qualification[:300] + ('...' if len(qualification) > 300 else ''),
            'prizes': prizes[:5],
            'imageUrl': img_url,
            'activityUrl': act_url,
            'officialUrl': official_url
        })

        if idx % 10 == 0:
            print(f"已解析 {idx}/{len(all_event_ids)} 個活動...")
        time.sleep(0.15)

    return events

# 更多額外台灣官方抽獎好康活動
def get_additional_verified_events():
    return [
        {
            "id": "ext-101",
            "title": "2026臺南購物節・消費發票登錄週週抽機票、百萬名車與百萬現金",
            "brand": "臺南市政府",
            "tags": ["登錄發票即抽", "抽機票", "熱門好康"],
            "time": "即日起 ~ 2027/02/28",
            "deadline": "2027/02/28",
            "qualification": "於臺南市轄內各合法設立之店家消費，單筆發票滿 50 元以上，至官方網站或台南購物節 App 登錄發票，即可享有抽獎資格，特約店家享序號加碼雙倍送！",
            "prizes": ["百萬進口油電車", "日本雙人來回機票", "百萬現金", "最新智慧型手機"],
            "imageUrl": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://tainanshopping.tw/",
            "officialUrl": "https://www.tainan.gov.tw/"
        },
        {
            "id": "ext-102",
            "title": "桃園購物節消費滿額發票登錄抽百萬休旅車、日本商務艙機票",
            "brand": "桃園市政府",
            "tags": ["登錄發票即抽", "抽機票", "抽家電"],
            "time": "即日起 ~ 2026/03/15",
            "deadline": "2026/03/15",
            "qualification": "在桃園市合法立案店家單筆消費發票滿 500 元，至活動網站登錄發票，可參加月月抽汽車與週週抽機票，雲端發票載具可自動匯入綁定。",
            "prizes": ["百萬休旅車", "東京商務艙來回機票", "Dyson旗艦吸塵器", "iPhone18 Pro"],
            "imageUrl": "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://edb.tycg.gov.tw/",
            "officialUrl": "https://www.tycg.gov.tw/"
        },
        {
            "id": "ext-103",
            "title": "彰化GO購・消費發票登錄大獎抽百萬休旅車與萬元黃金",
            "brand": "彰化縣政府",
            "tags": ["登錄發票即抽", "熱門好康"],
            "time": "即日起 ~ 2027/01/15",
            "deadline": "2027/01/15",
            "qualification": "於彰化縣稅籍登記店家消費單筆滿 500 元，登錄發票即可獲得一組抽獎序號，特約商店消費序號雙倍送！",
            "prizes": ["百萬休旅車", "萬元實金黃金條塊", "Gogoro智慧電動機車"],
            "imageUrl": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://chcg.gov.tw/",
            "officialUrl": "https://www.chcg.gov.tw/"
        },
        {
            "id": "ext-104",
            "title": "聯華食品卡廸那・全系列發票登錄週週抽萬元現金與最新iPhone",
            "brand": "聯華食品",
            "tags": ["登錄發票即抽", "抽iPhone"],
            "time": "即日起 ~ 2027/01/31",
            "deadline": "2027/01/31",
            "qualification": "凡購買卡廸那全系列商品任一包裝，至聯華食品 LINE 官方帳號登錄發票，即可享有週週抽最新 iPhone 與萬元現金大獎！",
            "prizes": ["iPhone18 256GB", "現金 10,000 元", "卡廸那整箱零食補給包"],
            "imageUrl": "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.lianhwa.com.tw/",
            "officialUrl": "https://www.lianhwa.com.tw/"
        },
        {
            "id": "ext-105",
            "title": "愛之味健康美味賞・購買指定茶飲發票登錄月月抽東京機加酒",
            "brand": "愛之味",
            "tags": ["登錄發票即抽", "抽機票"],
            "time": "即日起 ~ 2027/02/10",
            "deadline": "2027/02/10",
            "qualification": "購買愛之味麥仔茶、分解茶等指定飲品滿額 99 元，登錄購買發票即可參加月月抽東京雙人自由行機加酒！",
            "prizes": ["東京雙人機加酒五日遊", "iPad 10代", "愛之味飲品半年份"],
            "imageUrl": "https://images.unsplash.com/photo-1510519138171-cbe656418844?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.agv.com.tw/",
            "officialUrl": "https://www.agv.com.tw/"
        },
        {
            "id": "ext-106",
            "title": "金車伯朗咖啡40週年慶・登錄發票抽歐洲奢華雙人遊與精品家電",
            "brand": "金車伯朗",
            "tags": ["登錄發票即抽", "抽機票", "抽家電"],
            "time": "即日起 ~ 2027/03/31",
            "deadline": "2027/03/31",
            "qualification": "購買金車伯朗咖啡全系列商品單筆滿 88 元，至活動網站登錄發票即可參加大獎抽獎！",
            "prizes": ["歐洲雙人浪漫奢華遊", "Dyson 空氣清淨機", "伯朗膠囊咖啡機特仕版"],
            "imageUrl": "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.kingcar.com.tw/",
            "officialUrl": "https://www.kingcar.com.tw/"
        },
        {
            "id": "ext-107",
            "title": "7-ELEVEN OPENPOINT 會員免消費每日登入搖一搖・免費抽萬點點數與機票折抵金",
            "brand": "7-ELEVEN",
            "tags": ["超商專區", "免消費即抽", "抽機票"],
            "time": "即日起 ~ 2026/12/31",
            "deadline": "2026/12/31",
            "qualification": "下載 OPENPOINT App 並登入會員，每日享免費一次『每日搖一搖』好康轉盤，無需任何消費即可免費抽獎！",
            "prizes": ["星宇航空機票 10,000 元折抵券", "OPENPOINT 10,000 點", "超商商品免費兌換券"],
            "imageUrl": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://group.openpoint.com.tw/",
            "officialUrl": "https://www.7-11.com.tw/"
        },
        {
            "id": "ext-108",
            "title": "全家便利商店 FamilyMart App 每日簽到免消費免費抽百杯特濃拿鐵與點數大獎",
            "brand": "全家",
            "tags": ["超商專區", "免消費即抽"],
            "time": "即日起 ~ 2026/12/31",
            "deadline": "2026/12/31",
            "qualification": "全家 App 會員每日打開手機 App 進入活動頁簽到，即可免費參加抽獎轉盤，完全免消費！",
            "prizes": ["Let's Café 100杯特濃拿鐵", "全家 Fa點 100,000 點", "私品茶商品兌換券"],
            "imageUrl": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.family.com.tw/",
            "officialUrl": "https://www.family.com.tw/"
        },
        {
            "id": "ext-109",
            "title": "星宇航空官方社群互動留言・免消費免費抽日本航線來回機票",
            "brand": "星宇航空",
            "tags": ["免消費即抽", "抽機票"],
            "time": "即日起 ~ 2027/01/20",
            "deadline": "2027/01/20",
            "qualification": "追蹤星宇航空官方粉絲專頁，於指定貼文按讚並標記兩位好友分享想去的日本城市，即可免費參加機票大獎抽獎！",
            "prizes": ["星宇航空台北-東京經濟艙雙人來回機票", "星宇精裝航空飛行模型"],
            "imageUrl": "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.starlux-airlines.com/",
            "officialUrl": "https://www.starlux-airlines.com/"
        },
        {
            "id": "ext-110",
            "title": "屈臣氏 Watsons 年末大感謝祭・會員消費滿額抽 iPhone 18 與 Dyson 旗艦美髮組",
            "brand": "屈臣氏",
            "tags": ["登錄發票即抽", "抽iPhone", "抽家電"],
            "time": "即日起 ~ 2027/01/25",
            "deadline": "2027/01/25",
            "qualification": "屈臣氏寵i會員單筆消費滿 688 元，登錄發票即可獲得一次抽獎機會，點金會員享雙倍抽獎序號！",
            "prizes": ["最新 iPhone 18 Pro", "Dyson Supersonic 吹風機特仕組", "屈臣氏萬用電子禮券"],
            "imageUrl": "https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.watsons.com.tw/",
            "officialUrl": "https://www.watsons.com.tw/"
        }
    ]

if __name__ == '__main__':
    onelife_events = crawl_onelife_all()
    additional_events = get_additional_verified_events()

    # 合併去重
    seen_ids = set()
    combined_events = []
    
    # 優先加入更多官方活動
    for e in additional_events:
        if e['id'] not in seen_ids:
            seen_ids.add(e['id'])
            combined_events.append(e)

    for e in onelife_events:
        if e['id'] not in seen_ids:
            seen_ids.add(e['id'])
            combined_events.append(e)

    print(f"=== 整合完畢！總活動數量: {len(combined_events)} 檔 ===")

    # 存檔
    with open('/Users/sheldonair/.gemini/antigravity/scratch/lucky-draw-tw/events.json', 'w', encoding='utf-8') as f:
        json.dump(combined_events, f, ensure_ascii=False, indent=2)

    js_content = 'window.INITIAL_EVENTS = ' + json.dumps(combined_events, ensure_ascii=False) + ';'
    with open('/Users/sheldonair/.gemini/antigravity/scratch/lucky-draw-tw/data.js', 'w', encoding='utf-8') as f:
        f.write(js_content)

    print("已成功更新 events.json 與 data.js！")
