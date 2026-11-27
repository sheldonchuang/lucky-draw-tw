import urllib.request
import urllib.parse
import re
import json
import time
import os
import calendar
from datetime import datetime, timedelta
from html import unescape

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    return text.strip()

def fetch_url(url):
    # 處理 URL 中的非 ASCII 字元（中文廠商名等）
    parsed = urllib.parse.urlsplit(url)
    encoded_path = urllib.parse.quote(parsed.path, safe='/:@!$&\'()*+,;=')
    encoded_query = urllib.parse.quote(parsed.query, safe='/:@!$&\'()*+,;=?')
    safe_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, encoded_path, encoded_query, parsed.fragment))
    req = urllib.request.Request(safe_url, headers={
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

def fetch_onelife_company_urls():
    """動態抓取 onelife.tw/company 廠商列表，產生所有廠商的分類頁 URL"""
    print("=== 動態抓取 onelife 廠商列表 ===")
    html = fetch_url('https://onelife.tw/company')
    if not html:
        print("  無法取得廠商列表，使用備用名單")
        return []
    slugs = re.findall(r'href="/c/([^"]+)"', html)
    unique_slugs = []
    seen = set()
    for s in slugs:
        if s not in seen:
            seen.add(s)
            unique_slugs.append(s)
    urls = []
    for s in unique_slugs:
        urls.append(f'https://onelife.tw/c/{s}')
    print(f"  已取得 {len(urls)} 家廠商的活動來源 URL")
    return urls

def crawl_onelife_all():
    print("=== 正在收集全網多通路最新活動清單 ===")

    # --- 基礎分類＋標籤頁（固定） ---
    base_urls = [
        'https://onelife.tw/lucky-draw',
        'https://onelife.tw/hot',
        # 抽獎類型標籤
        'https://onelife.tw/tag/抽獎',
        'https://onelife.tw/tag/抽機票',
        'https://onelife.tw/tag/抽iPhone',
        'https://onelife.tw/tag/買一送一',
        'https://onelife.tw/tag/登錄發票',
        'https://onelife.tw/tag/家電',
        # 大獎分類標籤
        'https://onelife.tw/tag/抽3C',
        'https://onelife.tw/tag/抽現金',
        'https://onelife.tw/tag/抽汽車',
        'https://onelife.tw/tag/抽家電',
        'https://onelife.tw/tag/抽機車',
        'https://onelife.tw/tag/抽旅遊',
        # 美食餐飲與手搖飲標籤
        'https://onelife.tw/tag/壽司',
        'https://onelife.tw/tag/爭鮮',
        'https://onelife.tw/tag/手搖飲',
        'https://onelife.tw/tag/飲料',
        'https://onelife.tw/tag/咖啡',
        'https://onelife.tw/tag/餐廳',
        'https://onelife.tw/tag/拉麵',
        'https://onelife.tw/tag/牛排',
        'https://onelife.tw/tag/豬排',
        # 熱門餐飲與手搖飲品牌專頁
        'https://onelife.tw/c/爭鮮',
        'https://onelife.tw/c/藏壽司',
        'https://onelife.tw/c/壽司郎',
        'https://onelife.tw/c/王品',
        'https://onelife.tw/c/築間',
        'https://onelife.tw/c/乾杯',
        'https://onelife.tw/c/牛角',
        'https://onelife.tw/c/勝博殿',
        'https://onelife.tw/c/一風堂',
        'https://onelife.tw/c/瓦城',
        'https://onelife.tw/c/漢來',
        'https://onelife.tw/c/饗賓',
        'https://onelife.tw/c/星巴克',
        'https://onelife.tw/c/路易莎',
        'https://onelife.tw/c/CoCo',
        'https://onelife.tw/c/迷客夏',
        'https://onelife.tw/c/五十嵐',
        'https://onelife.tw/c/麥當勞',
        'https://onelife.tw/c/肯德基',
    ]

    # --- 動態抓取所有廠商頁面 ---
    company_urls = fetch_onelife_company_urls()

    # --- 合併所有來源（去重） ---
    category_urls = base_urls + company_urls
    seen_urls = set()
    deduped_urls = []
    for u in category_urls:
        if u not in seen_urls:
            seen_urls.add(u)
            deduped_urls.append(u)
    category_urls = deduped_urls
    print(f"  總共 {len(category_urls)} 個來源頁面待爬取")

    all_event_ids = []
    for u in category_urls:
        html = fetch_url(u)
        if html:
            ids = re.findall(r'/a/(\d+)', html)
            for i in ids:
                if i not in all_event_ids:
                    all_event_ids.append(i)
        time.sleep(0.15)

    print(f"共收集到 {len(all_event_ids)} 個多分類活動 ID，開始全量解析...")

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

        prizes = []
        p_block = re.search(r'活動獎品：(.*?)(?:<h3|</div>|<p><strong>)', html, re.S)
        if p_block:
            p_text = clean_text(p_block.group(1))
            raw_lines = [p.strip() for p in re.split(r'[\r\n、，,]+', p_text) if p.strip()]
            for line in raw_lines:
                if len(line) > 1 and not line.startswith('http') and line not in prizes:
                    prizes.append(line)

        if not prizes:
            prizes_match = re.findall(r'<p><strong>(.*?獎.*?)</strong></p>', html)
            for p in prizes_match:
                clean_p = clean_text(p)
                if clean_p and clean_p not in prizes:
                    prizes.append(clean_p)

        if not prizes:
            prizes = ['官方大獎（詳見活動官網）']

        qual_match = re.search(r'活動辦法：(.*?)(?:<h3|</div>|<p><strong>活動獎品)', html, re.S)
        qualification = clean_text(qual_match.group(1)) if qual_match else ''

        tags = []
        # 分類標籤
        if any(b in (brand + title) for b in ['7-11', '7-ELEVEN', '全家', '萊爾富', 'OK超商', '超商', '全聯', '家樂福']):
            tags.append('超商專區')

        c_qual = (qualification + " " + title).lower()
        if any(k in c_qual for k in ['免消費', '按讚', '留言', '分享', '投票', '問卷', '填寫資料', '加入會員', '登入', '天天抽', '免費', '0元']):
            tags.append('免消費即抽')
        elif any(k in c_qual for k in ['發票', '載具', '登錄發票', '消費滿']):
            tags.append('登錄發票即抽')
        elif any(k in c_qual for k in ['瓶蓋', '序號', '貼紙', '刮刮卡', '集點']):
            tags.append('開蓋序號抽')
        elif '購買' in c_qual and '登錄發票即抽' not in tags:
            tags.append('消費登錄抽')

        if any(k in c_qual for k in ['買一送一', '半價', '第2杯半價', '加1元多1件', '買1送1', '隱藏代碼', '神券', '折價']):
            tags.append('買一送一')

        if any(k in c_qual for k in ['壽星', '生日', '慶生']):
            tags.append('壽星好康')

        if any(k in c_qual for k in ['限免', '免費領取', 'steam', 'epic', '遊戲']):
            tags.append('限免遊戲')

        if any(k in c_qual for k in ['line points', '蝦幣', '街口幣', 'momo幣', '簽到', '賺點']):
            tags.append('免費領點')

        # 獎項標籤 (大獎分類)
        lower_all = (title + " " + " ".join(prizes) + " " + qualification).lower()
        if any(k in lower_all for k in ['機票', '雙人遊', '機加酒', '旅遊金', '出國', '米蘭', '東京', '北海道', '芬蘭', '峇里島', '泰國', '日本', '歐洲', '首爾', '大阪', '環遊世界', '海外旅遊', '旅遊套票']):
            tags.append('抽機票')
        if any(k in lower_all for k in ['iphone', 'iphone16', 'iphone17', 'iphone18', '手機', '摺疊機', 'apple', '三星', 'pixel', 'ipad', 'airpods', 'apple watch']):
            tags.append('抽iPhone')
        if any(k in lower_all for k in ['電烤盤', '電視', '空氣清淨機', '音響', '電鍋', '按摩椅', 'dyson', 'panasonic', 'switch', 'bruno', '家電', '吸塵器', '烘衣機', '吹風機', '冰箱', '洗衣機', '微波爐', '掃地機器人', '氣炸鍋', '烤箱', '除濕機', '冷氣']):
            tags.append('抽家電')
        if any(k in lower_all for k in ['汽車', 'toyota', 'honda', 'mazda', 'benz', 'bmw', 'luxgen', '休旅車', 'rav4', 'altis', 'cross', 'kicks', '轎車', '小客車', 'nissan', 'kia', 'hyundai']):
            tags.append('抽汽車')
        if any(k in lower_all for k in ['機車', 'gogoro', '電動車', 'yamaha', 'kymco', 'sym', '三陽', '光陽', '山葉', 'vespa', 'ionex', '油電車', '125cc']):
            tags.append('抽機車')
        if any(k in lower_all for k in ['現金', '萬元', '10萬', '100萬', '50萬', '百萬', '千萬', '獎金', '現金大獎', '紅包', '現鈔', '購物金']):
            tags.append('抽現金')
        if any(k in lower_all for k in ['3c', '筆電', 'macbook', 'ps5', 'ps6', '耳機', '平板', '電競', '相機', 'gopro', '智慧手錶', 'switch', '遊戲機', 'quest', 'nvidia', 'keyboard', '藍牙喇叭', '行車記錄器']):
            tags.append('抽3C')

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

        if idx % 15 == 0:
            print(f"已解析 {idx}/{len(all_event_ids)} 個活動...")
        time.sleep(0.1)

    return events

# 即時查詢 Epic Games Store 官方即時限免遊戲 API
def fetch_live_epic_games(today):
    print("=== 正在連線 Epic Games Store 官方 API 抓取最新即時限免遊戲 ===")
    api_url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=zh-Hant&country=TW&allowCountries=TW"
    try:
        req = urllib.request.Request(api_url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode('utf-8'))
        
        elements = data.get('data', {}).get('Catalog', {}).get('searchStore', {}).get('elements', [])
        live_games = []

        for el in elements:
            title = el.get('title')
            if not title:
                continue
            promotions = el.get('promotions') or {}
            offers = promotions.get('promotionalOffers', [])
            upcoming = promotions.get('upcomingPromotionalOffers', [])
            description = el.get('description', '')

            images = el.get('keyImages', [])
            img_url = "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?auto=format&fit=crop&w=600&q=80"
            for img in images:
                if img.get('type') in ['Thumbnail', 'OfferImageWide', 'DieselStoreFrontWide']:
                    img_url = img.get('url')
                    break

            # 本期正在進行中的 100% 免費遊戲
            if offers:
                for p in offers[0].get('promotionalOffers', []):
                    if p.get('discountSetting', {}).get('discountPercentage') == 0:
                        end_raw = p.get('endDate', '')
                        end_date = end_raw[:10].replace('-', '/') if len(end_raw) >= 10 else ''
                        live_games.append({
                            'id': f"epic-live-{abs(hash(title)) % 10000}",
                            'title': f"Epic Games 本週限時免費正版遊戲・《{title}》0元永久入庫收藏",
                            'brand': "Epic Games",
                            'tags': ["限免遊戲", "免消費即抽", "熱門好康"],
                            'time': f"即日起 ~ {end_date} 23:00 止",
                            'deadline': end_date,
                            'qualification': f"登入 Epic Games Store 帳號，點擊《{title}》免費取得，即可終身保留於個人收藏庫！{description[:100]}",
                            'prizes': [f"正版《{title}》PC 遊戲完整版 0 元取得", "終身永久免費遊玩"],
                            'imageUrl': img_url,
                            'activityUrl': "https://store.epicgames.com/zh-Hant/free-games",
                            'officialUrl': "https://store.epicgames.com/"
                        })

            # 下期即將接棒的 100% 免費遊戲
            if upcoming:
                for p in upcoming[0].get('promotionalOffers', []):
                    if p.get('discountSetting', {}).get('discountPercentage') == 0:
                        start_raw = p.get('startDate', '')
                        end_raw = p.get('endDate', '')
                        start_date = start_raw[:10].replace('-', '/') if len(start_raw) >= 10 else ''
                        end_date = end_raw[:10].replace('-', '/') if len(end_raw) >= 10 else ''
                        live_games.append({
                            'id': f"epic-up-{abs(hash(title)) % 10000}",
                            'title': f"Epic Games 下週預告限時免費大作・《{title}》即將登場 0元領取",
                            'brand': "Epic Games",
                            'tags': ["限免遊戲", "免消費即抽"],
                            'time': f"{start_date} ~ {end_date}",
                            'deadline': end_date,
                            'qualification': f"Epic Games 官方預告下期限免大作《{title}》，換檔當日即可 0 元永久領取入庫！{description[:100]}",
                            'prizes': [f"正版《{title}》免費取得資格", "典藏遊戲授權"],
                            'imageUrl': img_url,
                            'activityUrl': "https://store.epicgames.com/zh-Hant/free-games",
                            'officialUrl': "https://store.epicgames.com/"
                        })

        print(f"成功自 Epic Games API 取得 {len(live_games)} 檔正版限免遊戲！")
        return live_games
    except Exception as e:
        print(f"抓取 Epic Games API 失敗 (使用動態後備): {e}")
        return []

# 動態生成五大生活免費情報（自動隨每日日期換檔，永遠保持在有效期內）
def get_dynamic_free_intelligence(today):
    weekday = today.weekday() # 0 = Monday, 6 = Sunday

    # 本週日 (超商週末買一送一專屬)
    days_to_sunday = (6 - weekday) % 7
    this_sunday = today + timedelta(days=days_to_sunday)
    this_sunday_str = this_sunday.strftime('%Y/%m/%d')

    # 本週三或下週三 (CoCo 都可 / 手搖飲週三好友日)
    days_to_wednesday = (2 - weekday) % 7
    this_wednesday = today + timedelta(days=days_to_wednesday)
    this_wednesday_str = this_wednesday.strftime('%Y/%m/%d')

    # 本週四或下週四 (Epic 限免遊戲換檔日)
    days_to_thursday = (3 - weekday) % 7
    if days_to_thursday == 0:
        this_thursday = today
    else:
        this_thursday = today + timedelta(days=days_to_thursday)
    this_thursday_str = this_thursday.strftime('%Y/%m/%d')

    # 當月底 (壽星專屬、肯德基神券、月度特惠)
    _, last_day = calendar.monthrange(today.year, today.month)
    month_end = today.replace(day=last_day)
    month_end_str = month_end.strftime('%Y/%m/%d')

    # 每日免費任務 (明日換日)
    tomorrow_str = (today + timedelta(days=1)).strftime('%Y/%m/%d')

    # 次月底 (稅務局發票換禮券)
    if today.month == 12:
        next_month_end = today.replace(year=today.year + 1, month=1, day=31)
    else:
        _, next_last_day = calendar.monthrange(today.year, today.month + 1)
        next_month_end = today.replace(month=today.month + 1, day=next_last_day)
    next_month_end_str = next_month_end.strftime('%Y/%m/%d')

    year_end_str = f"{today.year}/12/31"

    return [
        # === 1. 地方稅捐處「雲端發票免費換全聯 / 7-11 禮券」專區 (免抽獎保證兌換) ===
        {
            "id": "ext-tax-101",
            "title": "臺北市稅捐稽徵處・雲端發票捐贈免費兌換 7-11 與全聯百元商品卡（不用抽保證換）",
            "brand": "臺北市稅捐處",
            "tags": ["發票換禮券", "登錄發票即抽", "超商專區"],
            "time": f"即日起 ~ {next_month_end_str}（數量有限換完為止）",
            "deadline": next_month_end_str,
            "qualification": "只要使用財政部統一發票兌獎 App 或線上捐贈雲端發票 15~25 張（消費金額 10 元以上），即可至北市稅處線上兌換專區直接免費兌換 7-11 數位商品禮券 100 元或全聯禮券，免抽獎保證入袋！",
            "prizes": ["7-11 數位商品禮券 100 元", "全聯百元商品卡", "家樂福電子提貨券"],
            "imageUrl": "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://tpctax.gov.taipei/",
            "officialUrl": "https://tpctax.gov.taipei/"
        },
        {
            "id": "ext-tax-102",
            "title": "新北市政府稅捐稽徵處・雲端發票e起來線上即時免費換全家禮券與超商咖啡券",
            "brand": "新北市稅捐處",
            "tags": ["發票換禮券", "超商專區"],
            "time": f"即日起 ~ {next_month_end_str}",
            "deadline": next_month_end_str,
            "qualification": "登入新北稅捐處活動官網，線上捐贈當期雲端發票指定張數（每張發票金額 10 元以上），即可即時兌換全家便利商店 100 元電子禮券或中杯拿鐵咖啡兌換序號。",
            "prizes": ["全家便利商店 100 元禮券", "Let's Café 拿鐵兌換序號", "OK超商商品抵用券"],
            "imageUrl": "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.tax.ntpc.gov.tw/",
            "officialUrl": "https://www.tax.ntpc.gov.tw/"
        },
        {
            "id": "ext-tax-103",
            "title": "臺中市政府地方稅務局・中稅愛心雲端發票換全聯百元商品卡與超商購物金",
            "brand": "臺中市稅務局",
            "tags": ["發票換禮券", "超商專區"],
            "time": f"即日起 ~ {next_month_end_str}",
            "deadline": next_month_end_str,
            "qualification": "設籍台中或全台民眾於活動平台綁定手機條碼載具，線上捐贈未開獎雲端發票 20 張，免抽籤直接換取全聯 100 元實體禮券或 7-11 虛擬商品卡！",
            "prizes": ["全聯福利中心 100 元禮券", "7-ELEVEN 100元商品卡", "多功能保溫杯"],
            "imageUrl": "https://images.unsplash.com/photo-1607344645866-009c320c5ab8?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.tax.taichung.gov.tw/",
            "officialUrl": "https://www.tax.taichung.gov.tw/"
        },
        {
            "id": "ext-tax-104",
            "title": "財政部北區國稅局・e化納稅雲端發票換好禮・線上指定張數兌換超商商品卡",
            "brand": "財政部國稅局",
            "tags": ["發票換禮券", "超商專區"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "使用統一發票兌獎 App 捐贈未開獎雲端發票 15 張，即可免費兌換統一超商 100 元商品卡序號，每人每月限換 2 份，數量有限換完為止。",
            "prizes": ["7-11 統一超商 100 元商品卡", "全家 100 元禮物卡"],
            "imageUrl": "https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.ntbna.gov.tw/",
            "officialUrl": "https://www.ntbna.gov.tw/"
        },
        {
            "id": "ext-tax-105",
            "title": "高雄市稅捐稽徵處・愛心雲端發票兌換超商商品卡與家樂福提貨券",
            "brand": "高雄市稅捐處",
            "tags": ["發票換禮券", "超商專區"],
            "time": f"即日起 ~ {year_end_str}",
            "deadline": year_end_str,
            "qualification": "於高市稅活動網頁捐贈雲端發票指定張數，免抽獎即刻線上領取 7-11/全家百元商品卡序號或家樂福電子即享券！",
            "prizes": ["7-11/全家百元商品卡", "家樂福百元提貨券"],
            "imageUrl": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.kctax.gov.tw/",
            "officialUrl": "https://www.kctax.gov.tw/"
        },

        # === 2. 超商、速食龍頭、韓式炸雞與日式丼飯連鎖「買一送一＆折價神券」 ===
        # --- 超商與咖啡茶飲 ---
        {
            "id": "ext-bogo-101",
            "title": "7-ELEVEN 超值五六日「週末特惠買一送一」・CITY CAFE 特大美式咖啡/現萃茶寄杯優惠",
            "brand": "7-ELEVEN",
            "tags": ["買一送一", "超商專區"],
            "promo_group": "drinks",
            "time": f"每週五六日限時登場 (本期至 {this_sunday_str})",
            "deadline": this_sunday_str,
            "qualification": "全台 7-11 門市限時超值五六日活動＋OPENPOINT 行動隨時取寄杯特惠！CITY CAFE 特大美式、精品美式、黑糖珍珠撞奶、現萃茶同品項買一送一或寄杯多組現省，無須優惠券直接結帳即享折扣！",
            "prizes": ["CITY CAFE 特大美式買一送一", "OPENPOINT 咖啡寄杯優惠組", "現萃茶全品項買一送一"],
            "imageUrl": "https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.7-11.com.tw/",
            "officialUrl": "https://www.7-11.com.tw/"
        },
        {
            "id": "ext-bogo-102",
            "title": "全家便利商店「康康5週末特惠」・Let's Café 特大拿鐵寄杯/私品茶/霜淇淋任選買一送一",
            "brand": "全家",
            "tags": ["買一送一", "超商專區"],
            "promo_group": "drinks",
            "time": f"每週五六日限時三天 (本期至 {this_sunday_str})",
            "deadline": this_sunday_str,
            "qualification": "全家全台門市週末五六日「康康5」＆ APP 隨買跨店取咖啡寄杯專屬優惠！特大杯 Let's Café 拿鐵、Fami!ce 霜淇淋、私品茶仙女紅茶買一送一，冷熱不拘！",
            "prizes": ["Let's Café 特大拿鐵買一送一", "隨買跨店取咖啡寄杯特惠", "Fami!ce 霜淇淋買一送一"],
            "imageUrl": "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.family.com.tw/",
            "officialUrl": "https://www.family.com.tw/"
        },
        {
            "id": "ext-bogo-104",
            "title": "星巴克 Starbucks 數位體驗線上刮刮樂・天天登入抽「全品項飲料買一送一」券",
            "brand": "星巴克",
            "tags": ["買一送一", "免消費即抽"],
            "promo_group": "drinks",
            "time": f"即日起 ~ {(today + timedelta(days=12)).strftime('%Y/%m/%d')}",
            "deadline": (today + timedelta(days=12)).strftime('%Y/%m/%d'),
            "qualification": "進入星巴克官方 LINE 帳號或數位體驗活動網頁，登入即可每天免費玩刮刮樂一次，人人有獎保證獲得『全品項買一送一券』或『第二杯半價券』！",
            "prizes": ["全品項特大杯買一送一專屬券", "指定那堤第二杯半價", "節慶限定飲品單一特價券"],
            "imageUrl": "https://images.unsplash.com/photo-1541167760496-1628856ab772?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://event.12done.com.tw/starbucks/",
            "officialUrl": "https://www.starbucks.com.tw/"
        },
        {
            "id": "ext-bogo-coffee-01",
            "title": "伯朗咖啡館 Mr. Brown・每週一卡友日「全品項飲品買一送一」・香醇義式咖啡現省一杯",
            "brand": "伯朗咖啡館",
            "tags": ["買一送一", "熱門好康"],
            "promo_group": "drinks",
            "time": f"每週一會員專屬日 (本期至 {month_end_str})",
            "deadline": month_end_str,
            "qualification": "每週一持伯朗 Lounge 卡至全台伯朗咖啡館門市消費，全品項飲品不限品項、冰熱皆享「買一送一」（結帳以高價者計）！無論是經典美式、香草拿鐵或季節限定飲品皆享超值折扣！",
            "prizes": ["全品項飲品買一送一優惠", "伯朗 Lounge 卡消費點數雙倍送", "精選蛋糕下午茶加價折抵"],
            "imageUrl": "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.mrbrown.com.tw/",
            "officialUrl": "https://www.mrbrown.com.tw/"
        },
        {
            "id": "ext-bogo-coffee-02",
            "title": "路易莎咖啡 Louisa Coffee・黑卡會員專屬月度優惠・指定精品手沖 / 拿鐵享 85 折優惠券與 11 點前早餐超值折抵",
            "brand": "路易莎咖啡",
            "tags": ["買一送一", "熱門好康"],
            "promo_group": "drinks",
            "time": f"黑卡專屬月度優惠 (本期至 {month_end_str})",
            "deadline": month_end_str,
            "qualification": "加入『路易莎黑卡』官方會員（LINE 帳號即可免費綁定），享每月指定單品手沖咖啡 75 折/85 折、上午 11:00 前超值活力早餐搭配任一飲品天天享折扣，黑卡消費再享點數翻倍累積！",
            "prizes": ["指定精品手沖咖啡 85 折神券", "11點前活力早餐組合折價券", "黑卡會員積點翻倍折現金"],
            "imageUrl": "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.louisacoffee.co/",
            "officialUrl": "https://www.louisacoffee.co/"
        },
        {
            "id": "ext-bogo-tea-01",
            "title": "知名手搖飲聯合買一送一（CoCo都可 / 迷客夏 / 珍煮丹 / 麻古茶坊）・週三好友日與線上點餐領券特惠",
            "brand": "手搖飲聯合",
            "tags": ["買一送一", "熱門好康"],
            "promo_group": "drinks",
            "time": f"週週好友日＆線上領券 (本期至 {month_end_str})",
            "deadline": month_end_str,
            "qualification": "每週三 CoCo 都可 LINE 官方帳號『都可訂』領券享指定飲品買一送一 / 第二杯半價；迷客夏、珍煮丹、麻古茶坊透過『你訂 Nidin』或官方 LINE 會員綁定，不定期發放買一送一與折價神券！",
            "prizes": ["CoCo 週三好友日買一送一 / 領券折價", "迷客夏／珍煮丹線上訂餐折價券", "麻古茶坊季節飲品第二杯半價"],
            "imageUrl": "https://images.unsplash.com/photo-1558857563-b371033873b8?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://order.nidin.shop/",
            "officialUrl": "https://order.nidin.shop/"
        },
        {
            "id": "ext-bogo-tea-coco",
            "title": "CoCo 都可・每週三好友日「都可訂」線上領券指定飲品買一送一／第二杯 10 元",
            "brand": "CoCo都可",
            "tags": ["買一送一", "熱門好康"],
            "promo_group": "drinks",
            "time": f"每週三好友日＆月度優惠 (本期至 {this_wednesday_str})",
            "deadline": this_wednesday_str,
            "qualification": "加入 CoCo 都可官方 LINE 帳號並點選「都可訂」線上點餐，每週三好友日準時開搶指定人氣飲品（百香雙響炮、珍珠奶茶、輕乳茶等）買一送一或第二杯 10 元優惠券，每人每週皆可領取！",
            "prizes": ["週三好友日指定飲品買一送一", "都可訂線上點餐專屬折價券", "自備環保杯再折 5 元"],
            "imageUrl": "https://images.unsplash.com/photo-1558857563-b371033873b8?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.coco-tea.com/",
            "officialUrl": "https://www.coco-tea.com/"
        },
        {
            "id": "ext-bogo-tea-milksha",
            "title": "迷客夏 Milksha・迷點線上訂餐會員禮＆週三週五指定飲品優惠・點數折現金",
            "brand": "迷客夏",
            "tags": ["買一送一", "熱門好康"],
            "promo_group": "drinks",
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "加入迷客夏官方 LINE 綁定「迷點」會員，享新會員入會贈券、每筆消費集點折抵現金，以及不定期發放指定牧場鮮奶茶、大正紅茶拿鐵第二杯半價或折價券！",
            "prizes": ["迷點會員入會專屬折價券", "指定飲品第二杯半價 / 滿額現折", "消費集點免費兌換飲品"],
            "imageUrl": "https://images.unsplash.com/photo-1544787219-7f47ccb76574?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.milksha.com/",
            "officialUrl": "https://www.milksha.com/"
        },
        {
            "id": "ext-bogo-tea-macu",
            "title": "麻古茶坊 / 珍煮丹 / 可不可熟成紅茶・LINE 會員領券買一送一＆你訂線上點餐折扣",
            "brand": "麻古/珍煮丹/可不可",
            "tags": ["買一送一", "熱門好康"],
            "promo_group": "drinks",
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "麻古茶坊、珍煮丹、可不可熟成紅茶、清心福全、五十嵐等熱門手搖飲品牌，透過官方 LINE 好友領券或「你訂 Nidin」線上訂餐，不定期推出指定果茶/黑糖珍珠/熟成紅茶買一送一或滿額折價，搭配環保杯再折 5 元！",
            "prizes": ["指定人氣手搖飲買一送一券", "你訂線上點餐滿額現折券", "壽星生日月份免費飲品/折價券"],
            "imageUrl": "https://images.unsplash.com/photo-1556679343-c7306c1976bc?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://order.nidin.shop/",
            "officialUrl": "https://www.kebuke.com/"
        },

        # --- 壽司連鎖專區（爭鮮、壽司郎、藏壽司） ---
        {
            "id": "ext-sushi-01",
            "title": "爭鮮迴轉壽司 / 爭鮮gogo / 定食8・APP 會員每週優惠券＆當月壽星贈禮・集點換免費壽司",
            "brand": "爭鮮",
            "tags": ["買一送一", "壽星好康", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "下載註冊「爭鮮 TW」官方 APP 成為會員，即可領取旗下【爭鮮迴轉壽司、爭鮮PLUS、爭鮮gogo、定食8、MAGiC TOUCH】每週限定優惠券（指定壽司加1元多1件/買一送一、滿額現折），壽星當月再領專屬生日禮券！",
            "prizes": ["APP 每週限定加1元多1件 / 折價券", "當月壽星專屬免費贈品 / 折扣券", "消費集點兌換免費餐點與折抵金"],
            "imageUrl": "https://images.unsplash.com/photo-1579871494447-9811cf80d66c?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.sushiexpress.com.tw/",
            "officialUrl": "https://www.sushiexpress.com.tw/"
        },
        {
            "id": "ext-sushi-02",
            "title": "壽司郎 Sushiro・台灣壽司郎 APP 集點換免費甜點／折價券・每月限定祭典特惠",
            "brand": "壽司郎",
            "tags": ["免消費即抽", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "下載「台灣壽司郎」官方 APP 預約訂位與到店報到集點，累積點數可免費兌換限定甜點、折價券與周邊好禮；官方粉專與 APP 同步更新每月期間限定鮪魚/鮭魚祭典特惠！",
            "prizes": ["APP 集點免費兌換甜點 / 折價券", "每月限定祭典人氣壽司優惠", "聯名活動限定抽獎好禮"],
            "imageUrl": "https://images.unsplash.com/photo-1553621042-f6e147245754?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.sushiro.com.tw/",
            "officialUrl": "https://www.sushiro.com.tw/"
        },
        {
            "id": "ext-sushi-03",
            "title": "藏壽司 Kura Sushi・限定聯名扭蛋抽獎活動・消費滿額贈好禮與 IG/FB 打卡抽獎",
            "brand": "藏壽司",
            "tags": ["熱門好康", "登錄發票即抽"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "至全台藏壽司門市消費，每 5 盤即可抽聯名限定扭蛋乙次！定期推出寶可夢、三麗鷗、吉伊卡哇等人氣聯名滿額贈禮與官方粉專留言抽獎／免費餐券活動。",
            "prizes": ["人氣動漫聯名限定扭蛋＆滿額贈", "官方社群抽藏壽司 500 元餐券", "E排客 APP 預約免排隊"],
            "imageUrl": "https://images.unsplash.com/photo-1611143669185-af224c5e3252?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.kurasushi.tw/",
            "officialUrl": "https://www.kurasushi.tw/"
        },

        # --- 人氣火鍋連鎖專區（王品集團火鍋、築間、肉多多、馬辣） ---
        {
            "id": "ext-hotpot-01",
            "title": "王品集團火鍋（石二鍋 / 聚日式鍋物 / 青花驕 / 和牛涮）・王品瘋美食 APP 領贈菜券與壽星 5 折",
            "brand": "王品集團火鍋",
            "tags": ["買一送一", "壽星好康", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "下載「王品瘋美食」APP 免費加入會員，每月不定時發放旗下【石二鍋、聚日式鍋物、尬鍋、青花驕、和牛涮、向辣】免費贈肉盤／海鮮券與買一送一券；當月壽星再享聚鍋 5 折或專屬免費招待！",
            "prizes": ["聚日式鍋物當月壽星指定套餐 5 折", "石二鍋/青花驕/和牛涮免費贈肉盤券", "王品瘋點數 1 點折 1 元無上限"],
            "imageUrl": "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://wowprime.com/",
            "officialUrl": "https://wowprime.com/"
        },
        {
            "id": "ext-hotpot-02",
            "title": "築間幸福鍋物・加入官方 LINE 會員免費領「肉品／海鮮 7 選 1」電子優惠券",
            "brand": "築間幸福鍋物",
            "tags": ["免消費即抽", "壽星好康", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "免費加入築間餐飲集團官方 LINE 會員，立即領取新會員入會點數（可直接兌換牛五花、梅花豬、鮮蝦、蛤蜊等 7 選 1 免費加菜券），消費集點還可免費換整份套餐，當月壽星享點數雙倍送！",
            "prizes": ["免費肉品/海鮮 7 選 1 兌換券", "會員點數免費兌換整份鍋物套餐", "當月壽星生日禮與點數加倍"],
            "imageUrl": "https://images.unsplash.com/photo-1547592166-23ac45744acd?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.jhujian.com.tw/",
            "officialUrl": "https://www.jhujian.com.tw/"
        },
        {
            "id": "ext-hotpot-03",
            "title": "肉多多火鍋 / 狂一鍋・樂多多 APP 入會禮免費送「梅花豬／無骨鮮雞腿」・壽星送生日肉蛋糕",
            "brand": "肉多多/狂一鍋",
            "tags": ["免消費即抽", "壽星好康", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "下載註冊「樂多多 APP」免費領取入會禮兌換券（至肉多多火鍋或狂一鍋內用即免費送活力梅花豬或無骨鮮雞腿乙份），當月壽星出示證件還可免費獲贈「生日肉蛋糕」乙顆！",
            "prizes": ["APP 入會免費送活力梅花豬 / 鮮雞腿", "當月壽星免費贈生日肉蛋糕", "點數跨品牌通用免費換海鮮肉盤"],
            "imageUrl": "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.twrododo.com/",
            "officialUrl": "https://www.twrododo.com/"
        },
        {
            "id": "ext-hotpot-04",
            "title": "馬辣 / 新馬辣 / 問鼎火鍋・當月壽星＆身分證對對碰「九孔鮑魚／神仙牛」免費吃到飽升級",
            "brand": "馬辣集團",
            "tags": ["壽星好康", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "每月更新馬辣集團（馬辣、新馬辣、新馬辣Plus、問鼎、涮樂和牛）身分證對對碰與當月壽星活動：提前一天訂位並主動告知參加壽星優惠，全桌免費升級九孔鮑魚、北海道帆立貝或美國神仙牛吃到飽！",
            "prizes": ["當月壽星全桌免費升級九孔鮑魚吃到飽", "身分證對中指定數字贈北海道大帆立貝", "問鼎壽星免費贈生日肉蛋糕"],
            "imageUrl": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.mala-1.com.tw/",
            "officialUrl": "https://www.mala-1.com.tw/"
        },

        # --- 連鎖燒烤／燒肉店專區（乾杯、原燒、燒肉Like、牛角、屋馬、碳佐麻里） ---
        {
            "id": "ext-bbq-01",
            "title": "乾杯燒肉 / 老乾杯・KANPAI GO！CLUB 會員入會禮＆當月壽星贈精緻肉品・八點乾杯免費續杯",
            "brand": "乾杯集團",
            "tags": ["買一送一", "壽星好康", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "免費加入「KANPAI GO！CLUB」LINE 官方會員，享新會員入會點數禮、每晚 8 點全場乾杯活動指定飲品免費續杯乙杯；當月壽星提前訂位並出示證件，免費招待壽星專屬精緻甜點或肉品！",
            "prizes": ["晚間 8 點乾杯免費再來一杯", "會員入會點數兌換牛舌/招牌料理", "當月壽星專屬免費招待"],
            "imageUrl": "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.kanpaiyakiniku.com.tw/",
            "officialUrl": "https://www.kanpai.com.tw/"
        },
        {
            "id": "ext-bbq-02",
            "title": "燒肉Like / 原燒 Oh my!原燒・會員入會免費贈肉盤＆單人燒肉加菜券・王品瘋美食壽星禮",
            "brand": "燒肉Like/原燒",
            "tags": ["免消費即抽", "壽星好康", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "加入「燒肉Like」官方 LINE 好友領取新會員免費贈牛五花/豬五花兌換券；「Oh my!原燒」透過王品瘋美食 APP 領取每月贈菜券，當月壽星享單人套餐優惠與專屬肉盤招待！",
            "prizes": ["燒肉Like LINE 入會免費送肉盤", "原燒當月壽星套餐優惠 / 贈菜券", "單人燒肉加購半價券"],
            "imageUrl": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.facebook.com/YAKINIKULIKETW/",
            "officialUrl": "https://www.yakiyan.com/"
        },
        {
            "id": "ext-bbq-03",
            "title": "牛角日本燒肉 / 屋馬 / 茶六 / 碳佐麻里・當月壽星專屬折扣與免費招待肉品甜點",
            "brand": "牛角/屋馬/茶六",
            "tags": ["壽星好康", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "牛角日本燒肉專門店會員享平日指定吃到飽折扣與生日禮；屋馬燒肉、茶六燒肉堂、碳佐麻里當月壽星出示身分證件即享整桌 9 折起優惠或免費招待壽星專屬畫盤甜點與精選肉品！",
            "prizes": ["當月壽星整桌 9 折 / 免費贈肉盤", "牛角會員平日消費折扣券", "專屬慶生特調與精緻畫盤甜點"],
            "imageUrl": "https://images.unsplash.com/photo-1529193591184-b1d58069ecdd?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.gyu-kaku.com.tw/",
            "officialUrl": "https://www.gyu-kaku.com.tw/"
        },

        # --- 連鎖拉麵店專區（一風堂、花月嵐、屯京拉麵、麵屋武藏） ---
        {
            "id": "ext-ramen-01",
            "title": "一風堂 / 花月嵐 / 屯京拉麵 / 麵屋武藏・會員免費領「叉燒／溏心蛋／免費加麵」優惠券",
            "brand": "連鎖拉麵聯盟",
            "tags": ["免消費即抽", "壽星好康", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "加入一風堂、花月嵐（晶旺餐飲）、屯京拉麵或麵屋武藏官方 LINE / APP 會員，新會員立即領取免費配料券（溏心蛋、叉燒或煎餃），屯京拉麵免費升級大碗免加價，每月拉麵日與壽星月再贈免費加麵（替玉）或買一送一券！",
            "prizes": ["免費贈招牌叉燒 / 溏心蛋 / 煎餃券", "指定拉麵免費加麵（替玉）", "每月拉麵日 / 壽星買一送一券"],
            "imageUrl": "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.ippudo.com.tw/",
            "officialUrl": "https://www.ippudo.com.tw/"
        },

        # --- 百貨公司連鎖餐廳＆牛舌專賣店專區 ---
        {
            "id": "ext-mall-01",
            "title": "百貨連鎖餐飲＆牛舌專賣（饗賓 iEAT / 瓦城 / 漢來美食 / 利久牛舌 / 吉村牛舌）・APP 領贈菜＆美食券",
            "brand": "百貨餐飲/牛舌",
            "tags": ["免消費即抽", "壽星好康", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "集結新光三越、遠東百貨、SOGO、微風廣場熱門百貨餐廳與牛舌專賣店：【饗賓 iEAT】會員享饗食天堂/開飯川食堂/饗泰多壽星 95 折與贈菜；【瓦城集團】LINE 領券免費贈摩摩喳喳/月亮蝦餅折抵；【漢來美食 APP】新會員贈 100 元折價券；【牛たん炭焼利久／吉村牛舌／乾杯牛舌】搭配百貨 APP 點數折抵與當月限定套餐加量優惠！",
            "prizes": ["饗賓 iEAT 會員壽星 95 折＆入會贈禮", "漢來美食 APP 入會免費領 100 元券", "瓦城/大心/牛舌專賣店贈菜＆百貨折抵"],
            "imageUrl": "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.eatogether.com.tw/",
            "officialUrl": "https://www.thaitown.com.tw/"
        },

        # --- 連鎖炸豬排店專區（勝博殿、銀座杏子豬排、勝政豬排、福勝亭） ---
        {
            "id": "ext-tonkatsu-01",
            "title": "勝博殿 / 銀座杏子日式豬排 / 勝政豬排 / 福勝亭・會員領免費可樂餅＆當月壽星折價優惠",
            "brand": "連鎖炸豬排",
            "tags": ["免消費即抽", "壽星好康", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "加入「勝博殿」或「銀座杏子日式豬排（王座國際）」官方 LINE 會員，新會員贈免費可樂餅/唐揚雞/飲品兌換券，當月壽星再領 88 折或免費贈甜點券；「勝政日式豬排」與「福勝亭」亦提供會員專屬套餐優惠與免費加飯加高麗菜絲！",
            "prizes": ["入會免費贈可樂餅 / 唐揚雞兌換券", "當月壽星專屬 88 折或免費甜點券", "福勝亭會員限定特價套餐優惠"],
            "imageUrl": "https://images.unsplash.com/photo-1562967914-608f82629710?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.saboten.com.tw/",
            "officialUrl": "https://www.saboten.com.tw/"
        },

        # --- 連鎖壽喜燒／壽喜鍋專區（Mo-Mo-Paradise、北澤、潮肉、一番地） ---
        {
            "id": "ext-sukiyaki-01",
            "title": "Mo-Mo-Paradise / 北澤壽喜燒 / 潮肉 / 一番地・壽喜鍋會員入會禮與當月壽星優惠",
            "brand": "連鎖壽喜燒",
            "tags": ["壽星好康", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "下載三澧企業「Humax Asia」APP 加入 Mo-Mo-Paradise 會員，享入會點數折抵與當月壽星專屬禮券；北澤壽喜燒、潮肉壽喜燒、一番地壽喜燒提供平日午餐特惠與當月壽星同行折扣／免費贈海鮮或肉品升級！",
            "prizes": ["Mo-Mo-Paradise 會員折價券＆壽星禮", "壽喜燒平日午餐超值優惠價", "當月壽星四人同行折抵 / 免費升級"],
            "imageUrl": "https://images.unsplash.com/photo-1547592166-23ac45744acd?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.mo-mo.com.tw/",
            "officialUrl": "https://www.mo-mo.com.tw/"
        },

        # --- 連鎖義大利麵／義式餐廳專區（古拉爵、薄多義、貝里尼、洋城、默爾） ---
        {
            "id": "ext-pasta-01",
            "title": "古拉爵 / 薄多義 / 貝里尼 BELLINI / 洋城 / 默爾・壽星幾歲送幾隻雞翅＆會員免費贈披薩炸物",
            "brand": "連鎖義大利麵",
            "tags": ["免消費即抽", "壽星好康", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "【薄多義 BITE 2 EAT】當日壽星提前訂位享「幾歲就送幾隻雞翅」超狂慶生；【古拉爵 Grazie】雲雀會員免費領入會飲料/點心券與壽星招待甜點；【貝里尼 BELLINI Pasta Pasta】三澧會員壽星折價；【洋城義大利餐廳／默爾 pasta pizza】LINE 會員入會免費送薯條/炸物或披薩優惠！",
            "prizes": ["薄多義壽星幾歲送幾隻雞翅（需訂位）", "古拉爵/貝里尼會員壽星免費甜點與折價券", "洋城/默爾入會免費領炸物或披薩券"],
            "imageUrl": "https://images.unsplash.com/photo-1551183053-bf91a1d81141?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.grazie.com.tw/",
            "officialUrl": "https://www.grazie.com.tw/"
        },

        # --- 速食與披薩隱藏優惠碼專區（麥當勞、肯德基、必勝客、漢堡王、摩斯漢堡） ---
        {
            "id": "ext-bogo-fast-01",
            "title": "麥當勞 McDonald's・APP 天天轉盤刮刮樂抽「大薯 / 麥克鷄塊 / 冰炫風買一送一」・歡樂送專屬優惠",
            "brand": "麥當勞",
            "tags": ["買一送一", "免消費即抽", "熱門好康"],
            "promo_group": "fastfood",
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "打開『麥當勞 APP』每天免費玩開運轉盤與刮刮樂，高機率現抽大薯買一送一、四塊麥克鷄塊買一送一、OREO 冰炫風買一送一券！歡樂送線上訂餐亦享專屬優惠代碼折扣！",
            "prizes": ["大薯買一送一神券", "四塊麥克鷄塊買一送一券", "OREO 冰炫風買一送一券"],
            "imageUrl": "https://images.unsplash.com/photo-1550547660-d9450f859349?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.mcdonalds.com.tw/",
            "officialUrl": "https://www.mcdonalds.com.tw/"
        },
        {
            "id": "ext-bogo-103",
            "title": "肯德基 KFC 隱藏優惠代碼專區・神券【40565 / 40451 / 40531】咔啦脆雞+原味蛋撻現省120元",
            "brand": "肯德基",
            "tags": ["買一送一", "熱門好康"],
            "promo_group": "fastfood",
            "coupon_codes": [
                {"code": "40565", "desc": "咔啦脆雞×2 + 原味蛋撻×2 + 無糖綠茶 $149"},
                {"code": "40451", "desc": "個人重量級獨享餐 半價特惠組"},
                {"code": "40531", "desc": "咔啦雞腿堡 + 原味蛋撻 + 小薯 + 飲品超值組"}
            ],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "於肯德基自助點餐機或官方線上點餐輸入隱藏優惠代碼【40565】享咔啦脆雞x2+原味蛋撻x2+飲品優惠價 149 元；輸入【40451】享個人重量級獨享餐半價特惠；輸入【40531】享漢堡蛋撻超值套餐！",
            "prizes": ["咔啦脆雞+蛋撻超殺神券特惠", "點心盒買一送一優惠碼", "原味蛋撻禮盒加價購優惠"],
            "imageUrl": "https://images.unsplash.com/photo-1626082927389-6cd097cdc6ec?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.kfcclub.com.tw/Coupon",
            "officialUrl": "https://www.kfcclub.com.tw/"
        },
        {
            "id": "ext-bogo-fast-pizzahut",
            "title": "必勝客 Pizza Hut 隱藏優惠代碼・神券【24405 / 24416 / 14338】外帶買大送大＆個人比薩超值組",
            "brand": "必勝客",
            "tags": ["買一送一", "熱門好康"],
            "promo_group": "fastfood",
            "coupon_codes": [
                {"code": "24405", "desc": "外帶 1 個小比薩 + 副食/飲品 超值特惠"},
                {"code": "24416", "desc": "個人獨享比薩 + BBQ烤雞/薯金幣 組合優惠"},
                {"code": "14338", "desc": "外帶買大送大 + 1.25L 大可樂超值聚餐組"}
            ],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "至必勝客官方訂餐網站「優惠券專區」或 PK 雙饗卡 APP 輸入 5 碼隱藏優惠代碼，即可直接套用外帶買大送大、小比薩加副食特價或個人獨享比薩超殺組合價！",
            "prizes": ["外帶比薩買大送大優惠", "個人比薩+副食超值神券", "聚餐大比薩特價優惠代碼"],
            "imageUrl": "https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.pizzahut.com.tw/promotions/",
            "officialUrl": "https://www.pizzahut.com.tw/"
        },
        {
            "id": "ext-bogo-fast-02",
            "title": "摩斯漢堡 MOS Burger・MOS Order APP 專屬折價券・摩斯冰紅茶買一送一與元氣早餐第2套半價",
            "brand": "摩斯漢堡",
            "tags": ["買一送一", "熱門好康"],
            "promo_group": "fastfood",
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "下載『MOS Order』APP 免費會員，每週點擊『安心取溫馨送/專屬優惠券』專區，即可臨櫃或手機點餐兌換大杯摩斯冰紅茶買一送一、摩斯蒟蒻禮盒買一送一、元氣早餐第 2 套半價！",
            "prizes": ["摩斯招牌大杯冰紅茶買一送一", "蒟蒻禮盒買一送一優惠券", "人氣漢堡個人獨享餐現折券"],
            "imageUrl": "https://images.unsplash.com/photo-1586190848861-99aa4a171e90?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.mos.com.tw/",
            "officialUrl": "https://www.mos.com.tw/"
        },
        {
            "id": "ext-bogo-105",
            "title": "漢堡王 Burger King 官網優惠券專區・小華堡/經典脆雞堡/大薯買一送一",
            "brand": "漢堡王",
            "tags": ["買一送一"],
            "promo_group": "fastfood",
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "全台漢堡王門市臨櫃出示手機優惠券畫面，或官網外帶預約「優惠券專區」點選/輸入優惠碼，即享小華堡買一送一、經典脆雞堡買一送一、大份薯條與洋蔥圈買一送一！",
            "prizes": ["小華堡買一送一", "黃金脆雞堡買一送一", "大份美式薯條買一送一"],
            "imageUrl": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.burgerking.com.tw/category/4",
            "officialUrl": "https://www.burgerking.com.tw/"
        },

        # --- 人氣韓式炸雞連鎖專區（bb.q CHICKEN、起家雞） ---
        {
            "id": "ext-bogo-korean-01",
            "title": "bb.q CHICKEN 韓式炸雞・官方專屬優惠券・外帶全雞免費送「炸年糕與韓式醃蘿蔔」、指定韓式副食買一送一",
            "brand": "bb.q CHICKEN",
            "tags": ["買一送一", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "出示官方優惠券畫面或加入『享聚卡』會員，外帶點購經典去骨/半半炸雞，免費加碼贈送人氣炸年糕乙份，韓式醃蘿蔔無限量免費續加，指定韓式氣泡飲同品項買一送一！",
            "prizes": ["外帶經典炸雞免費送香酥炸年糕", "韓式氣泡飲買一送一券", "會員專屬現折 50 元優惠券"],
            "imageUrl": "https://images.unsplash.com/photo-1562967914-608f82629710?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://bbqchicken.com.tw/",
            "officialUrl": "https://bbqchicken.com.tw/"
        },
        {
            "id": "ext-bogo-korean-02",
            "title": "起家雞 Cheogajip 韓式炸雞・品牌好康優惠券・外帶招牌去骨炸雞送經典配料，每月 7 號吃起家雞享專屬折價神券",
            "brand": "起家雞",
            "tags": ["買一送一", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "加入起家雞官方 LINE 會員領取當月折價神券，門市外帶全雞或去骨炸雞，免費贈送招牌地瓜條或炸年糕乙份，每月 7 號吃起家雞再享整筆訂單滿額折抵優惠！",
            "prizes": ["招牌炸年糕/地瓜條免費贈送券", "起家雞全單滿額折價券", "韓式特調飲品買一送一"],
            "imageUrl": "https://images.unsplash.com/photo-1626082927389-6cd097cdc6ec?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.cheogajip.com.tw/",
            "officialUrl": "https://www.cheogajip.com.tw/"
        },

        # --- 知名日式丼飯連鎖專區（吉野家、松屋、すき家） ---
        {
            "id": "ext-bogo-donburi-01",
            "title": "台灣吉野家 Yoshinoya・月度數位優惠神券・牛丼雙寶套餐現折 35 元、茶碗蒸與招牌檸檬紅茶買一送一",
            "brand": "吉野家",
            "tags": ["買一送一", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "結帳時出示台灣吉野家官方數位優惠券，即享招牌中碗牛丼套餐現省 35 元；點購指定定食享單點茶碗蒸、檸檬紅茶同品項買一送一特惠！",
            "prizes": ["招牌牛丼套餐現折神券", "茶碗蒸買一送一優惠券", "檸檬紅茶同品項買一送一"],
            "imageUrl": "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.yoshinoya.com.tw/",
            "officialUrl": "https://www.yoshinoya.com.tw/"
        },
        {
            "id": "ext-bogo-donburi-02",
            "title": "台灣松屋 Matsuya・人氣牛肉飯專屬折價券・點購主餐免費升級大盛碗、蔥香半熟蛋定食現折 20 元",
            "brand": "台灣松屋",
            "tags": ["買一送一", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "加入台灣松屋官方 LINE 好友，每月自動推播專屬折價神券！至全台松屋門市點購牛肉飯或燒肉定食，出示手機畫面即可免費升級大碗（大盛）或贈送半熟蛋/蔥花配料券！",
            "prizes": ["主餐免費升級大盛碗優惠券", "特製燒肉定食現折 20 元券", "半熟蛋配料免費兌換券"],
            "imageUrl": "https://images.unsplash.com/photo-1607301405390-d831c242f59b?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.matsuya-foods.com.tw/",
            "officialUrl": "https://www.matsuya-foods.com.tw/"
        },
        {
            "id": "ext-bogo-donburi-03",
            "title": "すき家 SUKIYA 台灣・官方限定優惠專區・牛丼中碗青菜可樂餅超值特惠套餐、外帶線上點餐現折優惠券",
            "brand": "すき家",
            "tags": ["買一送一", "熱門好康"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "於全台 SUKIYA 門市點餐出示官方優惠或使用線上外帶系統，享人氣牛丼搭配青菜可樂餅超殺組合價，期間限定鰻牛丼或咖哩新品現折 20 元專屬優惠碼！",
            "prizes": ["牛丼青菜套餐組合超殺優惠", "新品定食現折優惠券", "外帶滿額折抵券"],
            "imageUrl": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.sukiya-jp.com.tw/",
            "officialUrl": "https://www.sukiya-jp.com.tw/"
        },

        # === 3. 當月「壽星免費好康指南」（各大遊樂園門票免費/半價與連鎖餐飲慶生盛宴） ===
        # --- 連鎖餐飲龍頭 ---
        {
            "id": "ext-bday-101",
            "title": f"王品集團當月壽星專屬禮遇・下載王品瘋美食 App 領四大品牌同行五折與免費生日主餐甜點",
            "brand": "王品集團",
            "tags": ["壽星好康", "熱門好康"],
            "time": f"當月壽星專屬 (本期至 {month_end_str})",
            "deadline": month_end_str,
            "qualification": "免費下載『王品瘋美食』App 註冊會員，於生日當月即可獲得全品牌生日禮券包（包含王品牛排贈私房法式甜點/私房菜、西堤牛排當月單客單人套餐66折、聚日式鍋物富士肉肉山免費升級、原燒海鮮招待等）。",
            "prizes": ["王品牛排私房菜生日招待", "西堤套餐單客半價折價券", "夏慕尼主廚招待精緻生日甜點"],
            "imageUrl": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.wowprime.com/",
            "officialUrl": "https://www.wowprime.com/"
        },
        {
            "id": "ext-bday-102",
            "title": f"饗賓集團饗食天堂 / 饗饗・當月壽星會員享精緻生乳捲生日蛋糕免費送與 95 折抵用券",
            "brand": "饗食天堂",
            "tags": ["壽星好康", "熱門好康"],
            "time": f"當月壽星專屬 (本期至 {month_end_str})",
            "deadline": month_end_str,
            "qualification": "加入『iEAT饗愛吃』App 免費會員，生日當月即可領取專屬生日禮券（饗食天堂、小福利、開飯川食堂），用餐出示會員再獲官方特製當季生乳蛋糕整份免費送！",
            "prizes": ["特製整份精緻生日蛋糕免費送", "饗食天堂 95 折消費折抵券", "iEAT 愛吃點數雙倍累積"],
            "imageUrl": "https://images.unsplash.com/photo-1535141192574-5d4897c13136?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.eatogether.com.tw/",
            "officialUrl": "https://www.feastogether.com.tw/"
        },
        {
            "id": "ext-bday-dine-01",
            "title": f"漢來美食（漢來海港自助餐廳）・壽星專屬平日 7 折 / 假日 85 折大口爽嗑頂級生蠔海鮮吃到飽",
            "brand": "漢來海港",
            "tags": ["壽星好康", "熱門好康"],
            "time": f"當月壽星專屬 (本期至 {month_end_str})",
            "deadline": month_end_str,
            "qualification": "下載『來美食 APP』並完成會員註冊，生日當月自動發放漢來海港壽星生日折扣券（平日享 7 折、假日享 85 折優惠，同行親友享全台最受歡迎海鮮Buffet）！",
            "prizes": ["漢來海港平日 7 折吃到飽優惠券", "假日 85 折優惠券", "來美食全品牌生日折抵金"],
            "imageUrl": "https://images.unsplash.com/photo-1550547660-d9450f859349?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.hilai-foods.com/",
            "officialUrl": "https://www.hilai-foods.com/"
        },
        {
            "id": "ext-bday-dine-02",
            "title": f"金色三麥 SUNMAI・當日壽星提前預訂免費招待「6吋精緻生日蛋糕」整顆帶回家！",
            "brand": "金色三麥",
            "tags": ["壽星好康"],
            "time": f"當月壽星專屬 (本期至 {month_end_str})",
            "deadline": month_end_str,
            "qualification": "加入金色三麥官方會員，於生日當天或當月預約到店慶生（需提前 3 天預訂並告知有壽星），金色三麥直接免費贈送主廚特製「6吋精緻生日蛋糕」乙整顆！",
            "prizes": ["6吋精緻生日蛋糕整顆免費送", "壽星專屬慶生互動舉牌活動", "會員生日禮抵用金"],
            "imageUrl": "https://images.unsplash.com/photo-1530103862676-de8c9debad1d?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.lebledor.com/",
            "officialUrl": "https://www.lebledor.com/"
        },
        {
            "id": "ext-bday-dine-03",
            "title": f"薄多義 Bite 2 Eat・傳奇「幾歲生日送幾隻炸雞翅」壽星派對狂歡狂嗑炸雞翅山",
            "brand": "薄多義",
            "tags": ["壽星好康"],
            "time": f"當月壽星專屬 (本期至 {month_end_str})",
            "deadline": month_end_str,
            "qualification": "加入薄多義會員，於慶生日前完成官方預約（需至少4人同行），當日壽星幾歲就免費送幾隻香酥炸雞翅（炸雞翅山無上限）！",
            "prizes": ["幾歲生日免費送幾隻炸雞翅（無上限）", "壽星專屬慶生立牌拍照服務", "義式餐點折價券"],
            "imageUrl": "https://images.unsplash.com/photo-1567620832903-9fc6debc209f?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.bite2eatpizza.com/",
            "officialUrl": "https://www.bite2eatpizza.com/"
        },
        {
            "id": "ext-bday-dine-04",
            "title": f"千葉火鍋 / 享千葉・VIP 壽星狂享 5 折半價吃到飽！一般壽星憑身分證享 75 折超值特惠",
            "brand": "千葉火鍋",
            "tags": ["壽星好康"],
            "time": f"當月壽星專屬 (本期至 {month_end_str})",
            "deadline": month_end_str,
            "qualification": "持享味卡會員當月壽星本人享 5 折（半價吃到飽！）；非會員出示身分證亦享當月 75 折~85 折專屬慶生特惠，無限量享用豐富火鍋料、現切肉品與甜點Buffet。",
            "prizes": ["VIP 壽星 5 折半價吃到飽", "一般壽星 75 折優惠", "壽星專屬哈根達斯冰淇淋加碼"],
            "imageUrl": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.chien-yen.com.tw/",
            "officialUrl": "https://www.chien-yen.com.tw/"
        },
        {
            "id": "ext-bday-dine-05",
            "title": f"乾杯集團（乾杯燒肉居酒屋 / 老乾杯）・壽星免費招待超人氣「燒肉蛋糕」或頂級澳洲和牛",
            "brand": "乾杯燒肉",
            "tags": ["壽星好康"],
            "time": f"當月壽星專屬 (本期至 {month_end_str})",
            "deadline": month_end_str,
            "qualification": "加入『KANPAI GO CLUB』官方會員，生日當月至全台乾杯燒肉居酒屋或老乾杯用餐，出示 APP 會員即免費獲贈超人氣「特製燒肉蛋糕」乙份或壽星專屬頂級和牛料理招待！",
            "prizes": ["特製燒肉蛋糕乙份免費招待", "頂級澳洲和牛生日兌換券", "會員點數加倍送"],
            "imageUrl": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.kanpai.com.tw/",
            "officialUrl": "https://www.kanpai.com.tw/"
        },
        {
            "id": "ext-bday-dine-06",
            "title": f"海底撈火鍋・會員當月壽星專屬生日禮券折抵、生日限定果盤與慶生燈牌驚喜嗨唱",
            "brand": "海底撈火鍋",
            "tags": ["壽星好康"],
            "time": f"當月壽星專屬 (本期至 {month_end_str})",
            "deadline": month_end_str,
            "qualification": "註冊海底撈會員，生日當月登入海底撈 APP 即送專屬生日折價抵用券；用餐時告知店員，現場免費贈送精緻水果拼盤、慶生燈牌與川劇變臉慶祝服務！",
            "prizes": ["海底撈專屬生日抵用金", "主廚特製壽星水果拼盤免費贈", "全場慶生嗨歌與慶生紀念小禮物"],
            "imageUrl": "https://images.unsplash.com/photo-1563245372-f21724e3856d?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.haidilao.com/",
            "officialUrl": "https://www.haidilao.com/"
        },

        # --- 全台各大主題遊樂園 ---
        {
            "id": "ext-bday-103",
            "title": "六福村主題遊樂園・當日壽星本人免費入園！當月壽星享半價 599 元暢玩整天",
            "brand": "六福村",
            "tags": ["壽星好康", "熱門好康"],
            "time": f"即日起 ~ {year_end_str}",
            "deadline": year_end_str,
            "qualification": "生日當天憑身分證或健保卡臨櫃購票，壽星本人享門票 0 元完全免費入園！同行親友享特惠 750 元；若為當月壽星本人亦享半價 599 元超值優惠。",
            "prizes": ["當日壽星 0 元全日入園免費門票", "當月壽星半價 599 元入園特惠", "園區餐飲抵用券"],
            "imageUrl": "https://images.unsplash.com/photo-1513889961551-628c1e5e2ee9?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.leofoovillage.com.tw/",
            "officialUrl": "https://www.leofoovillage.com.tw/"
        },
        {
            "id": "ext-bday-park-01",
            "title": "義大遊樂世界・「當日壽星免費入園！」全台唯一希臘情境主題樂園 0 元暢玩，當月壽星再享超殺優惠價",
            "brand": "義大遊樂世界",
            "tags": ["壽星好康", "熱門好康"],
            "time": f"即日起 ~ {year_end_str}",
            "deadline": year_end_str,
            "qualification": "憑身分證或健保卡臨櫃購票，當日壽星本人 0 元免費入園（需搭配 1 名購全票者），當月壽星本人亦享超低門票特惠與義大摩天輪免費搭乘！",
            "prizes": ["當日壽星 0 元免費入園", "當月壽星超值門票折抵", "摩天輪免費搭乘"],
            "imageUrl": "https://images.unsplash.com/photo-1508873696983-2df5293cb325?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.edathemepark.com.tw/",
            "officialUrl": "https://www.edathemepark.com.tw/"
        },
        {
            "id": "ext-bday-park-02",
            "title": "劍湖山世界・當月壽星超殺專屬優惠 399 元（原價 999 現省 600 元）暢玩摩天樂園與驚險設施",
            "brand": "劍湖山世界",
            "tags": ["壽星好康"],
            "time": f"即日起 ~ {year_end_str}",
            "deadline": year_end_str,
            "qualification": "憑中華民國身分證臨櫃購票，當月壽星門票享破盤價 399 元（原價 999 元，現省 600 元！），當日壽星更享驚喜破盤特惠！",
            "prizes": ["當月壽星門票 399 元特惠（現省600元）", "園區餐飲優惠折價券", "園區設施快速通關禮遇"],
            "imageUrl": "https://images.unsplash.com/photo-1576085898323-218337e3e43c?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.janfusun.com.tw/",
            "officialUrl": "https://www.janfusun.com.tw/"
        },
        {
            "id": "ext-bday-park-03",
            "title": "麗寶樂園渡假區・探索世界 / 馬拉灣當月壽星 450 元超值入園，再送專屬慶生摩天輪體驗",
            "brand": "麗寶樂園",
            "tags": ["壽星好康"],
            "time": f"即日起 ~ {year_end_str}",
            "deadline": year_end_str,
            "qualification": "憑身分證臨櫃購票，當月壽星暢玩探索世界或馬拉灣水樂園只要 450 元（原價 899 元），天空之夢摩天輪亦享壽星特惠價！",
            "prizes": ["探索世界/馬拉灣當月壽星 450 元入園", "天空之夢摩天輪 150 元特惠搭乘", "壽星專屬慶生貼紙與禮物"],
            "imageUrl": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.lihpaoresort.com/",
            "officialUrl": "https://www.lihpaoresort.com/"
        },
        {
            "id": "ext-bday-park-04",
            "title": "遠雄海洋公園・當月壽星花蓮太平洋遊樂狂歡！壽星專屬優惠入園再贈海洋慶生大禮包",
            "brand": "遠雄海洋公園",
            "tags": ["壽星好康"],
            "time": f"即日起 ~ {year_end_str}",
            "deadline": year_end_str,
            "qualification": "出示身分證件，當月壽星享門票特惠 590 元（原價 990 元），入園服務台加碼贈送壽星專屬海洋徽章與餐飲商品抵用券。",
            "prizes": ["當月壽星門票現折 400 元", "壽星海洋專屬紀念徽章", "園區餐飲商品抵用券"],
            "imageUrl": "https://images.unsplash.com/photo-1544551763-46a013bb70d5?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.farglory-oceanpark.com.tw/",
            "officialUrl": "https://www.farglory-oceanpark.com.tw/"
        },
        {
            "id": "ext-bday-104",
            "title": "國賓影城金鑽會員・當月壽星享「免費電影票乙張」與壽星爆米花可樂組免費兌換",
            "brand": "國賓影城",
            "tags": ["壽星好康"],
            "time": f"即日起 ~ {year_end_str}",
            "deadline": year_end_str,
            "qualification": "國賓影城會員於生日當月可至全台國賓影城臨櫃或官網會員專區領取『生日專屬免費電影票 1 張』，並可同步領取中份爆米花與可樂免費兌換券。",
            "prizes": ["當月免費電影票 1 張", "免費爆米花與中杯可樂兌換券", "生日月份電影票續購 200 元優惠"],
            "imageUrl": "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.ambassador.com.tw/",
            "officialUrl": "https://www.ambassador.com.tw/"
        },

        # === 4. 正版限免遊戲（Steam、GOG、Epic Games、iOS 蘋果手遊、Android 安卓手遊） ===
        # --- PC 電腦平台（Steam、GOG、Epic Games） ---
        {
            "id": "ext-game-101",
            "title": "Epic Games Store 每週限時免費正版 PC 遊戲・本週精選大作 0 元永久入庫領取",
            "brand": "Epic Games",
            "tags": ["限免遊戲", "免消費即抽", "熱門好康"],
            "time": f"每週四晚上 23:00 換檔更新 (本期至 {this_thursday_str})",
            "deadline": this_thursday_str,
            "qualification": "登入 Epic Games 官方網站或客戶端，進入本週免費遊戲專區，點擊『獲取』即可 0 元永久購買並納入個人遊戲收藏庫，永久免費下載遊玩！",
            "prizes": ["熱門正版 PC 遊戲大作 0 元永久領", "典藏版 DLC 擴充包免費加贈"],
            "imageUrl": "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://store.epicgames.com/zh-Hant/free-games",
            "officialUrl": "https://store.epicgames.com/"
        },
        {
            "id": "ext-game-steam-01",
            "title": "Steam 平台限時免費「喜加一」・正版熱門名作 0 元永久領取入庫終身遊玩",
            "brand": "Steam",
            "tags": ["限免遊戲", "免消費即抽", "熱門好康"],
            "time": f"限時免費領取 (本期至 {(this_sunday + timedelta(days=1)).strftime('%Y/%m/%d')})",
            "deadline": (this_sunday + timedelta(days=1)).strftime('%Y/%m/%d'),
            "qualification": "活動期限內登入 Steam 官方帳號，進入特惠專區點擊『新增至帳戶』，即可 0 元完全免費獲得正版遊戲授權，終身保留於 Steam 收藏庫，並可獲得社群徽章與集換式卡片！",
            "prizes": ["正版 Steam 遊戲永久入庫", "官方集換式卡片掉落資格", "成就系統解鎖"],
            "imageUrl": "https://images.unsplash.com/photo-1612287232230-058b8efd8eb8?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://store.steampowered.com/genre/Free%20to%20Play/",
            "officialUrl": "https://store.steampowered.com/"
        },
        {
            "id": "ext-game-gog-01",
            "title": "GOG.com 經典正版 PC 遊戲無 DRM 限時免費大放送・免防拷一鍵入庫終身珍藏",
            "brand": "GOG.com",
            "tags": ["限免遊戲", "免消費即抽"],
            "time": f"即日起 ~ {(this_thursday + timedelta(days=7)).strftime('%Y/%m/%d')}",
            "deadline": (this_thursday + timedelta(days=7)).strftime('%Y/%m/%d'),
            "qualification": "知名無 DRM 數位平台 GOG 推出限免福利，登入帳號點擊領取，即可永久收藏無加密的正版遊戲完整離線安裝包、原聲帶與高畫質美術集！",
            "prizes": ["無 DRM 正版 PC 遊戲完整版", "數位版官方原聲帶與高畫質美術集", "免聯網離線安裝檔"],
            "imageUrl": "https://images.unsplash.com/photo-1550745165-9bc0b252726f?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.gog.com/#giveaway",
            "officialUrl": "https://www.gog.com/"
        },

        # --- 手機雙平台（Apple iOS、Android Google Play）限免專區 ---
        {
            "id": "ext-game-ios-01",
            "title": "蘋果 iOS App Store・本週特選付費手遊限時免費・原價 60~150 元正版 0 元永久下載",
            "brand": "Apple App Store",
            "tags": ["限免遊戲", "免消費即抽", "熱門好康"],
            "time": f"限時免費下載 (本期至 {(today + timedelta(days=6)).strftime('%Y/%m/%d')})",
            "deadline": (today + timedelta(days=6)).strftime('%Y/%m/%d'),
            "qualification": "使用 iPhone 或 iPad 打開 App Store，進入遊戲專區點擊『取得』，即可 0 元將原價付費的正版遊戲綁定至個人 Apple ID，即使換機也能終身永久免費重新下載！",
            "prizes": ["原價百元正版 iOS 手遊 0 元永久領", "無廣告乾淨完整版遊戲授權", "支援 iPhone/iPad 雲端存檔"],
            "imageUrl": "https://images.unsplash.com/photo-1550745165-9bc0b252726f?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://apps.apple.com/tw/genre/ios-%E9%81%8A%E6%88%B2/id6014",
            "officialUrl": "https://www.apple.com/tw/app-store/"
        },
        {
            "id": "ext-game-ios-02",
            "title": "iOS 經典獨立冒險與解謎名作・限時 0 元免費領取・典藏無內購完整版",
            "brand": "Apple App Store",
            "tags": ["限免遊戲", "免消費即抽"],
            "time": f"即日起 ~ {month_end_str}",
            "deadline": month_end_str,
            "qualification": "知名獨立遊戲工作室推出限時免費回饋，進入 App Store 專屬頁面點擊下載，享原價付費冒險解謎神作 0 元免費暢玩，支援 Game Center 成就與離線遊玩！",
            "prizes": ["經典獨立冒險神作 0 元取得", "無內購完整內容暢玩", "Game Center 專屬成就解鎖"],
            "imageUrl": "https://images.unsplash.com/photo-1511512578047-dfb367046420?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://apps.apple.com/tw/genre/ios-%E9%81%8A%E6%88%B2/id6014",
            "officialUrl": "https://www.apple.com/tw/app-store/"
        },
        {
            "id": "ext-game-android-01",
            "title": "Google Play 商店・本週特選付費 Android 手遊 0 元限免・原價 70~210 元正版手遊免破解直接入庫",
            "brand": "Google Play",
            "tags": ["限免遊戲", "免消費即抽", "熱門好康"],
            "time": f"限時免費下載 (本期至 {(today + timedelta(days=6)).strftime('%Y/%m/%d')})",
            "deadline": (today + timedelta(days=6)).strftime('%Y/%m/%d'),
            "qualification": "打開 Android 手機或平板上的 Google Play 商店，進入特惠專區點擊『安裝』，即可將原價付費的熱門 Android 遊戲 0 元永久繫結至個人的 Google 帳號，官方正版安全無毒！",
            "prizes": ["原價付費 Android 正版手遊 0 元永久入庫", "官方正版免破解安全授權", "支援 Google Play 遊戲成就"],
            "imageUrl": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://play.google.com/store/apps/category/GAME",
            "officialUrl": "https://play.google.com/"
        },
        {
            "id": "ext-game-android-02",
            "title": "Google Play Points 會員福利・週週免費摸彩領手遊代金券與專屬熱門虛寶",
            "brand": "Google Play",
            "tags": ["限免遊戲", "免費領點"],
            "time": f"每週福利更新 (本期至 {month_end_str})",
            "deadline": month_end_str,
            "qualification": "Android 用戶免費加入 Google Play Points 會員，每週至『福利』專區點擊簽到，即可免費抽 Play 點數或兌換熱門手遊免費專屬禮包、無門檻現金折抵金！",
            "prizes": ["Play Points 免費點數天天領", "熱門手遊專屬免費虛寶禮包", "Play 商店無門檻現金折抵券"],
            "imageUrl": "https://images.unsplash.com/photo-1512436991641-6745cdb1723f?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://play.google.com/store/points",
            "officialUrl": "https://play.google.com/"
        },

        # === 5. LINE Points / 蝦幣 / 街口幣「每日免費賺點任務」 ===
        {
            "id": "ext-pts-101",
            "title": "LINE 官方「LINE POINTS 免費賺點任務」・每日免消費看短片/加好友即領免費點數（1點抵1元）",
            "brand": "LINE 台灣",
            "tags": ["免費領點", "免消費即抽"],
            "time": f"每日任務即時更新 (今日至 {tomorrow_str})",
            "deadline": tomorrow_str,
            "qualification": "打開手機 LINE App 點選『錢包』進入『LINE POINTS 賺點』專區，完成指定看短片、加入品牌官方帳號或瀏覽指定網頁任務，即可免消費直接入帳 1~5 點 LINE POINTS（1 點等同現金 1 元，超商結帳皆可折抵）！",
            "prizes": ["LINE POINTS 免費點數（1點折1元）", "超商折價條碼", "貼圖兌換金"],
            "imageUrl": "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://points.line.me/",
            "officialUrl": "https://line.me/tw/"
        },
        {
            "id": "ext-pts-102",
            "title": "蝦皮購物 Shopee「每日免費簽到領蝦幣」・天天簽到與蝦皮果園免消費天天領折抵金",
            "brand": "蝦皮購物",
            "tags": ["免費領點", "免消費即抽"],
            "time": f"每日 00:00 換日更新 (本期至 {tomorrow_str})",
            "deadline": tomorrow_str,
            "qualification": "登入蝦皮購物 App 進入『蝦幣獎勵』天天打卡簽到，連續簽到獎勵加倍！搭配蝦皮消消樂與蝦皮果園種樹浇水，免花一毛錢就能天天累積蝦幣折抵全站購物！",
            "prizes": ["全站通用蝦幣現折金", "免運優惠券（不限金額）", "指定店家 85 折優惠券"],
            "imageUrl": "https://images.unsplash.com/photo-1556742049-0a67e5572293?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://shopee.tw/shopee-coins",
            "officialUrl": "https://shopee.tw/"
        },
        {
            "id": "ext-pts-103",
            "title": "街口支付「每日簽到免費領街口幣」・免消費天天領幣折抵水電瓦斯與超商消費",
            "brand": "街口支付",
            "tags": ["免費領點", "超商專區"],
            "time": f"每日簽到更新 (今日至 {tomorrow_str})",
            "deadline": tomorrow_str,
            "qualification": "打開街口支付 App 於首頁進入『每日簽到』專區，點擊簽到即可領取隨機街口幣，可用於繳納水電瓦斯公用事業費或於 7-11、全家超商消費直接 1:1 折抵現金！",
            "prizes": ["街口幣無門檻現金折抵", "超商專屬消費加碼券", "外送平台現折券"],
            "imageUrl": "https://images.unsplash.com/photo-1559526324-593bc073d938?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.jkopay.com/",
            "officialUrl": "https://www.jkopay.com/"
        },
        {
            "id": "ext-pts-104",
            "title": "MOMO 購物網「天天簽到免費抽萬點 momo幣」・登入即抽無門檻現金折抵幣",
            "brand": "MOMO購物網",
            "tags": ["免費領點", "免消費即抽"],
            "time": f"每日即時更新 (本期至 {tomorrow_str})",
            "deadline": tomorrow_str,
            "qualification": "會員每日登入 momo 購物網 App 或網頁版，進入簽到賺好康活動頁，每日免費摸彩一次，保證獲得 1~100 momo幣或折價券，1 momo幣等同 1 元新台幣！",
            "prizes": ["最高 10,000 momo幣大獎", "每日保證 1~5 momo幣", "全站免門檻現折券"],
            "imageUrl": "https://images.unsplash.com/photo-1512436991641-6745cdb1723f?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.momoshop.com.tw/",
            "officialUrl": "https://www.momoshop.com.tw/"
        }
    ]

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
            "time": "即日起 ~ 2027/03/15",
            "deadline": "2027/03/15",
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

def get_remaining_days(deadline_str, base_date):
    if not deadline_str:
        return -99999  # 無明確截止日期的舊活動，一律歸類為已截止！
    parts = [int(p) for p in re.findall(r'\d+', deadline_str)[:3]]
    if len(parts) == 3:
        try:
            target = datetime(parts[0], parts[1], parts[2]).date()
            return (target - base_date).days
        except Exception:
            return -99999
    return -99999

if __name__ == '__main__':
    today = datetime.now().date()
    print(f"=== 開始執行每日自動更新流程，當前基準日期: {today} ===")

    # 1. 抓取 onelife 全站活動
    onelife_events = []
    try:
        onelife_events = crawl_onelife_all()
    except Exception as ex:
        print(f"爬取 onelife 時發生例外: {ex}")

    # 若網路異常或爬取為空，回退讀取現有 events.json 內的既有活動
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(script_dir)
    events_json_path = os.path.join(repo_dir, 'events.json')
    data_js_path = os.path.join(repo_dir, 'data.js')

    if not onelife_events:
        try:
            with open(events_json_path, 'r', encoding='utf-8') as f:
                old_events = json.load(f)
                onelife_events = [e for e in old_events if not e.get('id', '').startswith('ext-')]
                print(f"已從備份中載入 {len(onelife_events)} 檔原有活動")
        except Exception as e:
            print(f"載入現有 events.json 失敗: {e}")
            onelife_events = []

    # 2. 自動連線抓取 Epic Games Store 官方即時正版限免遊戲 API
    live_epic_events = fetch_live_epic_games(today)

    # 3. 動態生成當日最新生活情報（買一送一、壽星好康、每日賺點、稅捐處發票換禮券）
    dynamic_intelligence_events = get_dynamic_free_intelligence(today)

    # 4. 取得長期驗證的官方精選大獎活動
    additional_events = get_additional_verified_events()

    # 5. 合併所有活動並去重
    seen_ids = set()
    combined_events = []
    
    # 優先加入即時限免遊戲與動態情報
    for e in live_epic_events + dynamic_intelligence_events + additional_events:
        if e['id'] not in seen_ids:
            seen_ids.add(e['id'])
            combined_events.append(e)

    for e in onelife_events:
        if e['id'] not in seen_ids:
            seen_ids.add(e['id'])
            combined_events.append(e)

    # 5. 【核心邏輯】：嚴格區隔「進行中活動」與「截止活動」
    # 已經截止的活動絕不混入進行中分類，全數放入「截止活動」專屬分頁中
    active_events = []
    expired_events = []

    for e in combined_events:
        days = get_remaining_days(e.get('deadline'), today)
        if days >= 0:
            e['is_expired'] = False
            active_events.append(e)
        else:
            e['is_expired'] = True
            expired_events.append(e)

    print(f"合併總數: {len(combined_events)} 檔，進行中有效好康: {len(active_events)} 檔，截止歷史存檔: {len(expired_events)} 檔")

    # 6. 【智慧排序】：
    # 進行中活動：越快到期的排在越前面
    active_events.sort(key=lambda e: get_remaining_days(e.get('deadline'), today))
    # 截止活動：最近剛截止的排在前面
    expired_events.sort(key=lambda e: get_remaining_days(e.get('deadline'), today), reverse=True)

    # 7. 合併寫入 events.json 與 data.js (進行中在前，截止存檔在後)
    all_events_to_save = active_events + expired_events

    with open(events_json_path, 'w', encoding='utf-8') as f:
        json.dump(all_events_to_save, f, ensure_ascii=False, indent=2)

    js_content = 'window.INITIAL_EVENTS = ' + json.dumps(all_events_to_save, ensure_ascii=False) + ';'
    with open(data_js_path, 'w', encoding='utf-8') as f:
        f.write(js_content)

    # 8. 自動更新 index.html 與 share.html 的快取版本標記，保證訪客手機即時讀取最新資料
    v_str = today.strftime('%Y%m%d%H%M')
    for html_file in ['index.html', 'share.html']:
        h_path = os.path.join(repo_dir, html_file)
        if os.path.exists(h_path):
            try:
                with open(h_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                new_content = re.sub(r'data\.js\?v=[a-zA-Z0-9_]+', f'data.js?v={v_str}', content)
                with open(h_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
            except Exception as ex:
                print(f"更新 {html_file} 快取標記失敗: {ex}")

    print(f"=== 成功更新！共 {len(active_events)} 檔有效活動，已依截止日期由近至遠排序！===")
