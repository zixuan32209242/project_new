# 台灣補助整合平台 · 補助快篩網

依你的年齡、縣市、興趣，自動篩選並整理台灣各項補助，附懶人包、日曆提醒、消費地圖與一日遊行程規劃。

## 專案結構
```
project/
├── app.py               # Flask 後端（登入、篩選、領取、API）
├── init_db.py           # 一鍵建立資料庫 + 塞入補助/店家資料
├── subsidies.db         # 執行 init_db.py 後自動產生
├── requirements.txt     # 套件清單
└── templates/
    ├── login.html       # Google 登入頁
    └── index.html       # 主程式（4 大分頁 SPA）
```

## 怎麼跑起來
```powershell
# 1. 安裝套件
pip install -r requirements.txt

# 2. 建立資料庫（第一次或改資料時執行）
python init_db.py

# 3. 啟動
python app.py
# 開瀏覽器 → http://127.0.0.1:5001
```

> Google 登入需在 Google Cloud Console 把「授權的重新導向 URI」設成
> `http://127.0.0.1:5001/login/callback`。

## 六大功能對照
1. **補助快篩** — 依地區／興趣／年齡篩選（文化幣、運動幣、客家幣、農遊券、原民幣、300 億租屋補貼、產業新尖兵）。
2. **懶人包** — 每張券點開有白話重點、怎麼領、加碼優惠。
3. **日曆提醒** — 開放/截止日 + 一鍵加入 Google 日曆或下載 .ics。
4. **特色化推薦** — 首頁「你可能會喜歡」依你的條件加權排序。
5. **消費地圖** — Leaflet 地圖顯示可用店家，可「定位我」找最近的。
6. **行程規劃** — 依你券包裡的券，自動排一日遊路線並畫在地圖上。

## ⚠️ 兩個重要提醒
- **安全**：`app.py` 裡的 Google client secret 已外流過，請到 Google Cloud Console
  重新產生一組，並改用環境變數（`GOOGLE_CLIENT_SECRET`），不要寫死在程式碼、也不要上傳 GitHub。
- **資料時效**：補助金額、日期為 2026 年整理，實際請以各官方網站為準；
  農遊券、原民幣為示範/歷史方案，店家座標亦為示範用途。
