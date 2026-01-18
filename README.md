# 自動爬蟲佈署指南 (Zeabur / Docker)

本目錄 (`my_crawler2.0`) 包含了佈署至 Zeabur 所需的所有檔案。

## 檔案結構
*   `crawler_bot.py`: 主要爬蟲程式 (已開啟 Headless 模式)。
*   `requirements.txt`: Python 依賴套件列表。
*   `config.yaml`: 設定檔 (選用，目前帳密已內建於程式碼中)。
*   `Dockerfile`: 定義如何建立包含 Chrome 與 Python 環境的容器。

## 佈署步驟 (Zeabur)

1.  **建立專案**:
    *   登入 Zeabur Dashboard。
    *   建立一個新專案 (Project)。

2.  **上傳程式碼**:
    *   您可以將此資料夾推送到 GitHub，然後在 Zeabur 連動 GitHub Repo。
    *   或者使用 Zeabur CLI 直接上傳。

3.  **設定環境變數 (Environment Variables)**:
    *   在 Zeabur 服務的設定頁面中，確認以下變數是否需要設定 (若程式碼中已寫死則可忽略):
        *   `BOT_TOKEN`: 您的 Telegram Bot Token (若未寫死)
        *   `CHAT_ID`: 您的 Telegram Chat ID (若未寫死)
        *   `TZ`: 設定時區，建議設為 `Asia/Taipei` 以確保排程時間正確。

4.  **重要檢查**:
    *   **時區**: 請務必設定 `TZ` 為 `Asia/Taipei`，否則排程 (20:35, 21:36) 會依照 UTC 時間執行 (+8小時誤差)。

## 關於 Dockerfile
此 Dockerfile 已經預先安裝了 `google-chrome-stable`，這是 `undetected-chromedriver` 運作所需的基礎。

## 故障排除
*   如果日誌出現 `DevToolsActivePort file doesn't exist` 或 Crash，通常是記憶體不足 (OOM)。請在 Zeabur 調整服務的 Memory 限制 (建議至少 1GB)。
*   如果出現 `RuntimeError: Event loop is closed`，請確認程式碼是否已包含最新的 Bot 修復 (本版本已包含)。

祝佈署順利！
