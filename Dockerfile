# 使用 Python 3.10 作為基底映像
FROM python:3.10-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴 (包含 Chrome 所需的套件)
# 這裡會安裝 wget, gnupg, unzip 以及 Chrome 依賴庫
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    xvfb \
    libxi6 \
    libgconf-2-4 \
    libnss3 \
    libxss1 \
    libasound2 \
    fonts-liberation \
    libappindicator3-1 \
    libnspr4 \
    libgbm1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安裝 Google Chrome Stable
# 注意: undetected-chromedriver 通常會自動下載對應的 driver，但需要系統有 Chrome 瀏覽器
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# 複製 requirements.txt 並安裝 Python 套件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有程式碼
COPY . .

# 設定環境變數 (可由 Zeabur 儀表板覆蓋)
# ENV BOT_TOKEN=your_token
# ENV CHAT_ID=your_chat_id

# 啟動指令
# 使用 python -u (unbuffered) 確保日誌即時輸出
CMD ["python", "-u", "crawler_bot.py"]
