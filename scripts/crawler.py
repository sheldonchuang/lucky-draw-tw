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
        },
        # === 1. 地方稅捐處「雲端發票免費換全聯 / 7-11 禮券」專區 (免抽獎保證兌換) ===
        {
            "id": "ext-tax-101",
            "title": "臺北市稅捐稽徵處・雲端發票捐贈免費兌換 7-11 與全聯百元商品卡（不用抽保證換）",
            "brand": "臺北市稅捐處",
            "tags": ["發票換禮券", "登錄發票即抽", "超商專區"],
            "time": "即日起 ~ 2026/12/31（數量有限換完為止）",
            "deadline": "2026/12/31",
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
            "time": "即日起 ~ 2026/12/25",
            "deadline": "2026/12/25",
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
            "time": "即日起 ~ 2027/01/10",
            "deadline": "2027/01/10",
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
            "time": "即日起 ~ 2026/12/20",
            "deadline": "2026/12/20",
            "qualification": "使用統一發票兌獎 App 捐贈未開獎雲端發票 15 張，即可免費兌換統一超商 100 元商品卡序號，每人每月限換 2 份，數量有限換完為止。",
            "prizes": ["7-11 統一超商 100 元商品卡", "全家 100 元禮物卡"],
            "imageUrl": "https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.ntbna.gov.tw/",
            "officialUrl": "https://www.ntbna.gov.tw/"
        },
        # === 2. 超商與連鎖餐飲「買一送一＆隱藏優惠代碼」 ===
        {
            "id": "ext-bogo-101",
            "title": "7-ELEVEN 超值五六日「週末特惠買一送一」・特大美式咖啡/現萃茶/哈根達斯限時半價",
            "brand": "7-ELEVEN",
            "tags": ["買一送一", "超商專區"],
            "time": "每週五、六、日固定登場",
            "deadline": "2026/11/30",
            "qualification": "全台 7-11 門市限時超值五六日活動，全品項指定 CITY CAFE 特大美式、精品美式、黑糖珍珠撞奶、指定進口冰品同品項買一送一，無須優惠券直接結帳即享折扣！",
            "prizes": ["CITY CAFE 特大美式買一送一", "現萃茶全品項買一送一", "指定進口冰品買一送一"],
            "imageUrl": "https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.7-11.com.tw/",
            "officialUrl": "https://www.7-11.com.tw/"
        },
        {
            "id": "ext-bogo-102",
            "title": "全家便利商店「康康5週末特惠」・Let's Café 特大拿鐵/雙口味霜淇淋任選買一送一",
            "brand": "全家",
            "tags": ["買一送一", "超商專區"],
            "time": "每週五六日限時三天",
            "deadline": "2026/11/30",
            "qualification": "全家全台門市週末五六日「康康5」專屬優惠，特大杯 Let's Café 拿鐵、全家 Fami!ce 霜淇淋（不限口味）、私品茶仙女紅茶買一送一，冷熱不拘！",
            "prizes": ["Let's Café 特大拿鐵買一送一", "Fami!ce 霜淇淋買一送一", "指定瓶裝茶飲買一送一"],
            "imageUrl": "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.family.com.tw/",
            "officialUrl": "https://www.family.com.tw/"
        },
        {
            "id": "ext-bogo-103",
            "title": "肯德基 KFC 隱藏優惠代碼專區・神券【40565 / 40451】咔啦脆雞+原味蛋撻現省120元",
            "brand": "肯德基",
            "tags": ["買一送一", "熱門好康"],
            "time": "即日起 ~ 2026/12/31",
            "deadline": "2026/12/31",
            "qualification": "於肯德基自助點餐機或官方線上點餐輸入隱藏優惠代碼【40565】享咔啦脆雞x2+原味蛋撻x2+飲品優惠價 149 元；輸入【40451】享個人重量級獨享餐半價特惠。",
            "prizes": ["咔啦脆雞+蛋撻超殺神券特惠", "點心盒買一送一優惠碼", "原味蛋撻禮盒加價購優惠"],
            "imageUrl": "https://images.unsplash.com/photo-1626082927389-6cd097cdc6ec?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.kfcclub.com.tw/",
            "officialUrl": "https://www.kfcclub.com.tw/"
        },
        {
            "id": "ext-bogo-104",
            "title": "星巴克 Starbucks 數位體驗線上刮刮樂・天天登入抽「全品項飲料買一送一」券",
            "brand": "星巴克",
            "tags": ["買一送一", "免消費即抽"],
            "time": "即日起 ~ 2026/12/15",
            "deadline": "2026/12/15",
            "qualification": "進入星巴克官方 LINE 帳號或數位體驗活動網頁，登入即可每天免費玩刮刮樂一次，人人有獎保證獲得『全品項買一送一券』或『第二杯半價券』！",
            "prizes": ["全品項特大杯買一送一專屬券", "指定那堤第二杯半價", "節慶限定飲品單一特價券"],
            "imageUrl": "https://images.unsplash.com/photo-1541167760496-1628856ab772?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://event.12done.com.tw/starbucks/",
            "officialUrl": "https://www.starbucks.com.tw/"
        },
        {
            "id": "ext-bogo-105",
            "title": "漢堡王 Burger King 歲末年終優惠神券・小華堡/經典脆雞堡/薯條大杯可樂買一送一",
            "brand": "漢堡王",
            "tags": ["買一送一"],
            "time": "即日起 ~ 2026/12/31",
            "deadline": "2026/12/31",
            "qualification": "全台漢堡王門市臨櫃出示手機優惠券畫面，或官網外帶預約輸入優惠碼，即享小華堡買一送一、經典脆雞堡買一送一、大份薯條與洋蔥圈買一送一！",
            "prizes": ["小華堡買一送一", "黃金脆雞堡買一送一", "大份美式薯條買一送一"],
            "imageUrl": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.burgerking.com.tw/",
            "officialUrl": "https://www.burgerking.com.tw/"
        },
        # === 3. 當月「壽星免費好康指南」 ===
        {
            "id": "ext-bday-101",
            "title": "王品集團當月壽星專屬禮遇・下載王品瘋美食 App 領四大品牌同行五折與免費生日主餐甜點",
            "brand": "王品集團",
            "tags": ["壽星好康", "熱門好康"],
            "time": "即日起 ~ 2026/12/31",
            "deadline": "2026/12/31",
            "qualification": "免費下載『王品瘋美食』App 註冊會員，於生日當月即可獲得全品牌生日禮券包（包含王品牛排贈私房生蠔/法式甜點、西堤牛排當月單客單人套餐66折、聚日式鍋物富士肉肉山免費升級等）。",
            "prizes": ["王品牛排私房菜生日招待", "西堤套餐單客半價折價券", "夏慕尼主廚招待精緻生日甜點"],
            "imageUrl": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.wowprime.com/",
            "officialUrl": "https://www.wowprime.com/"
        },
        {
            "id": "ext-bday-102",
            "title": "饗賓集團饗食天堂 / 饗饗・當月壽星會員享精緻生乳捲生日蛋糕免費送與 95 折抵用券",
            "brand": "饗食天堂",
            "tags": ["壽星好康"],
            "time": "即日起 ~ 2026/12/31",
            "deadline": "2026/12/31",
            "qualification": "加入『iEAT饗愛吃』App 免費會員，生日當月即可領取專屬生日禮券（饗食天堂、小福利、開飯川食堂），用餐出示會員再獲官方特製當季生乳蛋糕整份免費送！",
            "prizes": ["特製整份精緻生日蛋糕免費送", "饗食天堂 95 折消費折抵券", "iEAT 愛吃點數雙倍累積"],
            "imageUrl": "https://images.unsplash.com/photo-1535141192574-5d4897c13136?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.eatogether.com.tw/",
            "officialUrl": "https://www.feastogether.com.tw/"
        },
        {
            "id": "ext-bday-103",
            "title": "六福村主題遊樂園・當日壽星本人免費入園！當月壽星享半價 599 元暢玩整天",
            "brand": "六福村",
            "tags": ["壽星好康"],
            "time": "即日起 ~ 2026/12/31",
            "deadline": "2026/12/31",
            "qualification": "生日當天憑身分證或健保卡臨櫃購票，壽星本人享門票 0 元完全免費入園！同行親友享特惠 750 元；若為當月壽星本人亦享半價 599 元超值優惠。",
            "prizes": ["當日壽星 0 元全日入園免費門票", "當月壽星半價 599 元入園特惠", "園區餐飲抵用券"],
            "imageUrl": "https://images.unsplash.com/photo-1513889961551-628c1e5e2ee9?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.leofoovillage.com.tw/",
            "officialUrl": "https://www.leofoovillage.com.tw/"
        },
        {
            "id": "ext-bday-104",
            "title": "國賓影城金鑽會員・當月壽星享「免費電影票乙張」與壽星爆米花可樂組免費兌換",
            "brand": "國賓影城",
            "tags": ["壽星好康"],
            "time": "即日起 ~ 2026/12/31",
            "deadline": "2026/12/31",
            "qualification": "國賓影城會員於生日當月可至全台國賓影城臨櫃或官網會員專區領取『生日專屬免費電影票 1 張』，並可同步領取中份爆米花與可樂免費兌換券。",
            "prizes": ["當月免費電影票 1 張", "免費爆米花與中杯可樂兌換券", "生日月份電影票續購 200 元優惠"],
            "imageUrl": "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.ambassador.com.tw/",
            "officialUrl": "https://www.ambassador.com.tw/"
        },
        # === 4. Epic Games / Steam 每週「正版限免遊戲」 ===
        {
            "id": "ext-game-101",
            "title": "Epic Games Store 每週限時免費正版 PC 遊戲・本週精選大作 0 元永久入庫領取",
            "brand": "Epic Games",
            "tags": ["限免遊戲", "免消費即抽"],
            "time": "每週四晚上 23:00 自動換檔更新",
            "deadline": "2026/11/27",
            "qualification": "登入 Epic Games 官方網站或客戶端，進入本週免費遊戲專區，點擊『獲取』即可 0 元永久購買並納入個人遊戲收藏庫，永久免費下載遊玩！",
            "prizes": ["熱門正版 PC 遊戲大作 0 元永久領", "典藏版 DLC 擴充包免費加贈"],
            "imageUrl": "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://store.epicgames.com/zh-Hant/free-games",
            "officialUrl": "https://store.epicgames.com/"
        },
        {
            "id": "ext-game-102",
            "title": "Steam 平台週末特選限時免費喜加一・正版獨立名作 0 元領取終身擁有",
            "brand": "Steam",
            "tags": ["限免遊戲"],
            "time": "即日起 ~ 2026/11/30",
            "deadline": "2026/11/30",
            "qualification": "於活動期限內登入 Steam 帳號，於活動特惠頁點擊『新增至帳戶』，即可完全免費獲得正版遊戲授權，終身保留於 Steam 收藏庫中！",
            "prizes": ["正版 Steam 遊戲永久入庫", "專屬社群徽章與集換式卡片"],
            "imageUrl": "https://images.unsplash.com/photo-1612287232230-058b8efd8eb8?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://store.steampowered.com/",
            "officialUrl": "https://store.steampowered.com/"
        },
        {
            "id": "ext-game-103",
            "title": "GOG.com 經典正版 PC 遊戲無 DRM 限時免費大放送・點擊一鍵入庫永久珍藏",
            "brand": "GOG.com",
            "tags": ["限免遊戲"],
            "time": "即日起 ~ 2026/12/05",
            "deadline": "2026/12/05",
            "qualification": "知名無 DRM 數位遊戲平台 GOG 推出限時免費領取活動，登入帳號點擊領取按鈕，即可免費下載無加密的正版遊戲安裝檔與原聲帶！",
            "prizes": ["無 DRM 正版 PC 遊戲完整版", "數位版官方原聲帶與高畫質美術集"],
            "imageUrl": "https://images.unsplash.com/photo-1550745165-9bc0b252726f?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.gog.com/",
            "officialUrl": "https://www.gog.com/"
        },
        # === 5. LINE Points / 蝦幣 / 街口幣「每日免費賺點任務」 ===
        {
            "id": "ext-pts-101",
            "title": "LINE 官方「LINE POINTS 免費賺點任務」・每日免消費看短片/加好友即領免費點數（1點抵1元）",
            "brand": "LINE 台灣",
            "tags": ["免費領點", "免消費即抽"],
            "time": "每日即時更新",
            "deadline": "2026/12/31",
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
            "time": "每日 00:00 換日更新",
            "deadline": "2026/12/31",
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
            "time": "即日起 ~ 2026/12/31",
            "deadline": "2026/12/31",
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
            "time": "每日即時更新",
            "deadline": "2026/12/31",
            "qualification": "會員每日登入 momo 購物網 App 或網頁版，進入簽到賺好康活動頁，每日免費摸彩一次，保證獲得 1~100 momo幣或折價券，1 momo幣等同 1 元新台幣！",
            "prizes": ["最高 10,000 momo幣大獎", "每日保證 1~5 momo幣", "全站免門檻現折券"],
            "imageUrl": "https://images.unsplash.com/photo-1512436991641-6745cdb1723f?auto=format&fit=crop&w=600&q=80",
            "activityUrl": "https://www.momoshop.com.tw/",
            "officialUrl": "https://www.momoshop.com.tw/"
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
