# LuckyGo 台灣抽獎情報站 (現代卡片流版)

本專案仿造並全面升級 `onelife.tw`，具備**現代卡片流 UI**、**真實廠商官方抽獎活動**，並提供**一鍵直達官方登錄頁**功能。

---

## 專案亮點與特色

1. **真實廠商活動，拒絕虛構**：
   - 資料來源為台灣各大品牌與超商真實舉辦之活動。
   - 包含：全家便利商店、7-11/佳格、可口可樂、明治、Panasonic、台中購物節、GODIVA 等。
2. **六大真實熱門標籤**：
   - 🎁 **免消費即抽**：無須購物，線上集章、心理測驗、IG Reels 上傳、FB 互動即享抽獎。
   - ✈️ **抽機票**：日本來回機票、北海道泰國機加酒、米蘭機票等旅遊大獎。
   - 📱 **抽iPhone**：iPhone 18、iPhone 摺疊機、各項 Apple 旗艦手機。
   - 📺 **抽家電**：BRUNO 寶可夢電烤盤、Switch2、Dyson 空氣清淨機、Tokuyo 按摩椅等。
   - 🧾 **登錄發票即抽**：購買指定品牌商品登錄發票序號。
   - 🏪 **超商專區**：全家、7-11 等便利商店專屬獨家活動。
3. **極速體驗與現代 UI**：
   - 毛玻璃導航欄與響應式卡片瀑布流。
   - 剩餘天數自動計算與即將截止警示（< 3天紅字高亮）。
   - 點擊「前往抽獎 ↗」按鈕直接新分頁開啟原廠活動登錄頁。
   - 即時關鍵字模糊搜尋（支援大獎、品牌、規則搜尋）。
4. **0 元部署架構**：
   - 純前端（HTML5 + CSS + JavaScript），支援 GitHub Pages、Vercel 或 Cloudflare Pages 免費託管。
   - 支援免伺服器直接以瀏覽器雙擊 `index.html` 開啟。

---

## 檔案結構

```text
lucky-draw-tw/
├── index.html          # 現代卡片流前端頁面 (自適應手機與桌面)
├── data.js             # 真實活動預載資料庫 (保證本地雙擊預覽不被 CORS 阻擋)
├── events.json         # 結構化活動資料檔
├── README.md           # 專案說明文件
└── scripts/
    └── crawler.py      # 真實活動爬蟲腳本 (支援 GitHub Actions 定時排程)
```

---

## 如何預覽

- **方式一（最快）**：直接以瀏覽器開啟 [index.html](file:///Users/sheldonair/.gemini/antigravity/scratch/lucky-draw-tw/index.html)。
- **方式二（本地伺服器）**：
  ```bash
  cd /Users/sheldonair/.gemini/antigravity/scratch/lucky-draw-tw
  python3 -m http.server 8080
  # 瀏覽器開啟 http://localhost:8080
  ```

---

## 日後如何自動排程抓取與免費發布？

1. **資料抓取**：
   在 GitHub 倉庫中建立 `.github/workflows/update.yml`，設定每日定時執行 `python scripts/crawler.py`。
2. **自動更新**：
   腳本抓取最新活動後自動 commit 並 push 回倉庫。
3. **免費託管**：
   連結至 **Cloudflare Pages** 或 **GitHub Pages**，每次倉庫更新時自動重新構建，實現 100% 免費、無人值守運作。

---

## 商務合作與廣告贊助

- 聯絡信箱：`sheldonchuang@gmail.com`
- 合作項目：活動推廣置頂、品牌廣告贊助、超商活動特輯合作。
