import os
import logging
import yaml
import time
import asyncio
from datetime import datetime, timedelta, timedelta
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.error import TelegramError
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 設定日誌
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 讀取 Config
def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

CONFIG = load_config()

# 環境變數
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
# 使用者要求的正式帳號密碼 (直接指定以避免環境變數干擾)
USERNAME = "ak049"
PASSWORD = "fgh111"



def get_driver():
    """設定並回傳 Chrome Driver (使用 undetected-chromedriver)"""
    options = uc.ChromeOptions()
    # 使用 headless=new 模式，更難被偵測
    # [Docker 環境必要設定] 啟用無頭模式
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080") # 建議加上解析度以免元素被隱藏
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # [新增] 禁用「儲存密碼」提示與自動填入
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False
    }
    options.add_experimental_option("prefs", prefs)
    
    # undetected-chromedriver 會自動處理驅動程式下載與 patched binary
    try:
        driver = uc.Chrome(options=options)
    except Exception as e:
        logger.error(f"初始化 Driver 失敗: {e}")
        # 如果是版本不符，通常 uc 會自動重試，或是需要手動指定 version_main
        # 這裡嘗試使用 use_subprocess=True (有時候能解決權限問題)
        driver = uc.Chrome(options=options, use_subprocess=True)
        
    return driver

def login_and_fetch_data():
    """使用 Selenium 模擬真人登入 -> 搜尋 -> 抓資料"""
    driver = get_driver()
    selectors = CONFIG.get("selectors", {})
    
    try:
        logger.info("🚀 啟動瀏覽器...")
        
        # 1. 前往登入頁
        login_url = CONFIG.get("login_url")
        driver.get(login_url)
        logger.info(f"前往登入頁: {login_url}")
        
        # 等待欄位出現 (延長至 30 秒)
        wait = WebDriverWait(driver, 30)
        
        try:
            # 2. 輸入帳密
            logger.info(f"正在尋找帳號欄位: {selectors['login_user']}")
            user_field = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selectors['login_user'])))
            pass_field = driver.find_element(By.CSS_SELECTOR, selectors['login_pass'])
            
            # 使用 JavaScript 強制寫入值並觸發 input 事件
            # 這是對抗 React/Vue 等前端框架無法監聽到 Selenium 輸入的常見解法
            driver.execute_script("""
                arguments[0].value = arguments[1];
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
            """, user_field, USERNAME)
            time.sleep(0.5)
            
            driver.execute_script("""
                arguments[0].value = arguments[1];
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
            """, pass_field, PASSWORD)
            time.sleep(0.5)
            
            logger.info("輸入帳密完成")
            
            # 3. 點擊登入
            login_btn = driver.find_element(By.CSS_SELECTOR, selectors['login_btn'])
            time.sleep(1) 
            driver.execute_script("arguments[0].click();", login_btn)
            logger.info("點擊登入按鈕")
            
            # 4. 等待登入後跳轉
            time.sleep(10)
            logger.info(f"等待後目前網址: {driver.current_url}")
            driver.save_screenshot("after_login_attempt.png")
            
            # [新增] 儲存含有公告的頁面原始碼
            with open("debug_popup.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.info("已儲存頁面原始碼至 'debug_popup.html'")

            # [重要] 頁面是 frameset 結構
            # 1. 先處理中間的公告 (如果有) - 位於 mainFrame
            try:
                logger.info("切換至 mainFrame 處理公告...")
                driver.switch_to.default_content()
                wait.until(EC.frame_to_be_available_and_switch_to_it("mainFrame"))
                
                # ... (原有的關閉公告邏輯) ...
                try:
                    from selenium.webdriver.common.action_chains import ActionChains
                    from selenium.webdriver.common.keys import Keys
                    
                    # 確保焦點
                    try:
                        # 僅使用極短等待檢查 Body
                        body = WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                        body.click()
                    except: pass
                    
                    # 按 ESC
                    try:
                        actions = ActionChains(driver)
                        actions.send_keys(Keys.ESCAPE).perform()
                    except: pass
                    
                    # 點擊關閉按鈕 (快速檢查)
                    close_btns = driver.find_elements(By.XPATH, "//*[contains(text(), '×') or contains(text(), 'X') or contains(text(), '關閉') or contains(@class, 'close')]")
                    for btn in close_btns:
                        if btn.is_displayed():
                            btn.click()
                            # time.sleep(1) # 優化: 移除等待，點了就走
                except Exception as e:
                    logger.warning(f"公告處理略過: {e}")
                    
            except:
                logger.warning("無法切換至 mainFrame (公告處理)")

            # 2. 切換去選單 (gmenu) 點擊 "各類報表" -> "總累計表" (假設目標是這個)
            try:
                logger.info("切換至 gmenu 點擊選單...")
                driver.switch_to.default_content()
                wait.until(EC.frame_to_be_available_and_switch_to_it("gmenu"))
                
                # 點擊「各類報表」
                report_menu = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '各類報表')]")))
                report_menu.click()
                # time.sleep(1) # 優化: 移除固定等待，依賴後續的 frame 切換等待
                
                # 點擊「總累計表」 (或根據需求調整)
                # 這裡假設點了「各類報表」後會展開或跳轉，若需要點子選單請補充
                # sub_menu = driver.find_element(...)
                # sub_menu.click()
                
                logger.info("已點擊 各類報表")
                
            except Exception as e:
                logger.error(f"選單操作失敗: {e}")
                
            # 3. 切換回 mainFrame 準備搜尋/點擊確定
            logger.info("切換回 mainFrame...")
            driver.switch_to.default_content()
            wait.until(EC.frame_to_be_available_and_switch_to_it("mainFrame"))
            # time.sleep(2) # 優化: 移除固定等待，改為直接等待按鈕出現
            
            # 點擊 "確定" 按鈕 (搜尋報表)
            try:
                # 嘗試尋找 "確定" 或 "搜尋" 按鈕
                confirm_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(@value, '確定') or contains(text(), '確定') or contains(@id, 'btn')]")))
                confirm_btn.click()
                logger.info("已點擊 '確定' 按鈕")
                time.sleep(3) # 等待報表載入
            except Exception as e:
                logger.warning(f"沒找到 '確定' 按鈕: {e}")
            
            # 儲存報表頁面以供分析 (尋找目標數值)
            with open("debug_report.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.info("已儲存報表頁面至 'debug_report.html'")
            
            # [新增] 截圖功能: 抓取「佔成輸贏」欄位的截圖 (周圍)
            try:
                logger.info("正在準備截圖...")
                # 嘗試找到「佔成輸贏」的具體欄位
                # 先找總計行
                total_row = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'tr[data-bind="with: Total"]')))
                
                # 再找該行內的目標欄位 (data-bind 中包含 SubtotalTotDutyWinLose)
                # 使用 xpath 從 total_row 往下找比較穩，但 selenium element 不好接 xpath
                # 這裡直接用 CSS selector 找該 row 下的 td/span
                
                # 策略: 找到包含目標 data-bind 的 span 或 td
                target_elem = total_row.find_element(By.XPATH, ".//*[contains(@data-bind, 'SubtotalTotDutyWinLose')]")
                
                # 嘗試抓取該元素的"父級 td" (如果是 span) 或 本身 (如果是 td)，這樣截圖範圍會包含 padding 比較好看
                if target_elem.tag_name == 'span':
                    target_elem = target_elem.find_element(By.XPATH, "./..") # 抓 parent td
                
                # 滾動到該元素 (置中)
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", target_elem)
                time.sleep(0.5) # 稍微等待滾動動畫
                
                # 檢查元素大小，避免 0x0 導致報錯
                size = target_elem.size
                if size['width'] == 0 or size['height'] == 0:
                    logger.warning("目標元素大小為 0，嘗試截取整個總計行")
                    target_elem = total_row
                    
                # 再次檢查
                if target_elem.size['width'] > 0 and target_elem.size['height'] > 0:
                    target_elem.screenshot("result_screenshot.png")
                    logger.info("✅ 已儲存「佔成輸贏」欄位截圖至 'result_screenshot.png'")
                else:
                    raise Exception("元素大小仍為 0")
                
            except Exception as e:
                logger.warning(f"局部截圖失敗: {e}")
                # 如果找不到總計行，嘗試截全螢幕當備案
                driver.save_screenshot("result_screenshot.png")
                logger.info("⚠️ 已改為全螢幕截圖")

            # 暫時結束，等待下一步指示
            return driver.page_source
        
        except Exception as e:
            logger.error(f"操作流程中斷: {e}")
            raise e
            
    except Exception as e:
        logger.error(f"瀏覽器操作失敗: {e}")
        # 截圖方便除錯
        driver.save_screenshot("error_screenshot.png")
        raise
    finally:
        driver.quit()
        logger.info("瀏覽器已關閉")

def parse_html(html):
    soup = BeautifulSoup(html, "html.parser")
    results = {}
    
    try:
        # 1. 抓取日期範圍
        start_date = soup.find("span", attrs={"data-bind": lambda x: x and "html: StartDate" in x})
        end_date = soup.find("span", attrs={"data-bind": lambda x: x and "html: EndDate" in x})
        
        if start_date: results["start_date"] = start_date.get_text(strip=True)
        if end_date: results["end_date"] = end_date.get_text(strip=True)
        
        # 2. 抓取總計行的「佔成輸贏」
        # 邏輯：找到 data-bind="with: Total" 的列，再找 data-bind 包含 "html: SubtotalTotDutyWinLose" 的儲存格
        total_row = soup.find("tr", attrs={"data-bind": "with: Total"})
        if total_row:
            # 有兩種可能: SubtotalTotDutyWinLose 或 SubtotalTotDutyWinLose2 (視 HasZouFei 而定)
            # 我們嘗試抓取兩個，看哪個有值或顯示
            duty_cell = total_row.find("span", attrs={"data-bind": lambda x: x and ("html: SubtotalTotDutyWinLose" in x or "html: SubtotalTotDutyWinLose2" in x)})
            
            # 備援：如果 span 沒找到，找 td
            if not duty_cell:
                duty_cell = total_row.find("td", attrs={"data-bind": lambda x: x and ("html: SubtotalTotDutyWinLose" in x or "html: SubtotalTotDutyWinLose2" in x)})

            if duty_cell:
                results["duty_win_lose"] = duty_cell.get_text(strip=True)
            else:
                logger.warning("找不到總計列中的 '佔成輸贏' (SubtotalTotDutyWinLose) 欄位")
        else:
            logger.warning("找不到總計列 (with: Total)")

    except Exception as e:
        logger.error(f"解析 HTML 發生錯誤: {e}")
        
    return results


def format_message(data):
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # 構建訊息內容
    message = f"📊 **自動抓取報告** ({current_time})\n\n"
    
    if data.get("start_date"):
        message += f"📅 日期: {data['start_date']}"
        if data.get("end_date") and data['start_date'] != data['end_date']:
            message += f" ~ {data['end_date']}"
        message += "\n"
        
    if data.get("duty_win_lose"):
        message += f"💰 **佔成輸贏: {data['duty_win_lose']}**\n"
    else:
        message += "⚠️ 未抓取到佔成輸贏數據\n"
        
    message += f"\n狀態: 執行完成 ✅"
    return message

async def send_to_telegram(message, photo_path=None):
    try:
        # [修復] 在函式內初始化 Bot，避免 asyncio loop 關閉後 client 失效的問題
        bot_instance = Bot(token=BOT_TOKEN)
        
        # 先傳照片 (如果有)
        if photo_path and os.path.exists(photo_path):
            try:
                with open(photo_path, 'rb') as photo:
                    # 傳送照片並附帶文字說明 (caption)
                    # Telegram caption 限制 1024 字，我們的 message 很短所以沒問題
                    await bot_instance.send_photo(chat_id=CHAT_ID, photo=photo, caption=message, parse_mode="Markdown")
                logger.info("✅ 照片與訊息已發送至 Telegram")
                return # 發送成功直接結束
            except Exception as e:
                logger.error(f"❌ 照片發送失敗，嘗試僅發送文字: {e}")
        
        # 如果沒照片或照片發送失敗，則發送純文字
        await bot_instance.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown")
        logger.info("✅ 文字訊息已發送至 Telegram")
        
    except Exception as e:
        # 這裡改抓 Exception，讓任何錯誤(包含 RuntimeError)都能被記錄
        logger.error(f"❌ 發送失敗: {e}")
        # 【重要】如果發送失敗，我們將錯誤往上拋，好讓 job() retry 機制生效
        # 或者是: 如果我們認為 Telegram 失敗不需要重跑爬蟲，就不要 raise
        # 但用戶希望直到成功，所以如果 Telegram 沒發出去，應該不算成功？
        # 為了安全起見，這裡 raise 讓它可以重試 (假設是網路問題)
        raise e

def job():
    logger.info("⏰ 排程任務開始")
    
    while True:
        try:
            html = login_and_fetch_data()
            
            # 如果 html 為 None 或空，視為失敗 (login_and_fetch_data 通常會 raise，但以防萬一)
            if not html:
                raise Exception("未取得有效頁面內容")

            data = parse_html(html)
            msg = format_message(data)
            
            # 檢查是否有截圖
            photo_path = "result_screenshot.png"
            if not os.path.exists(photo_path):
                photo_path = None
                
            asyncio.run(send_to_telegram(msg, photo_path))
            
            logger.info("✅ 任務執行成功，結束本次排程")
            break # 成功後跳出迴圈
            
        except Exception as e:
            retry_wait = 60 # 重試等待秒數
            logger.error(f"❌ 任務失敗: {e}")
            logger.info(f"🔄 帳號可能被搶登或網路異常，{retry_wait} 秒後自動重試直到成功...")
            time.sleep(retry_wait)

if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="Asia/Taipei")
    
    # 設定排程時間: 20:35 與 21:36
    scheduler.add_job(job, CronTrigger(hour=20, minute=35), id="job_2035")
    scheduler.add_job(job, CronTrigger(hour=21, minute=36), id="job_2136")
    
    logger.info("🚀 Selenium 機器人啟動中...")
    logger.info(f"📅 排程設定: 20:35, 21:36")
    logger.info(f"👤 使用帳號: {USERNAME}")
    
    # [新增] 啟動時立刻執行一次測試
    logger.info("⚡ 正在執行啟動測試 (Test Run)...")
    try:
        # 這裡我們只跑一次 job，但 job 內部有無限重試機制
        # 為了避免測試卡死，我們可以給測試一個額外的邏輯，或者信任用戶「直到成功」的要求
        # 考慮到用戶現在就要看結果，直接跑 job() 是正確的
        job()
        
        # [新增] 依經要求: 一分鐘後再執行一次測試
        # 注意: 這裡是在 job() 跑完後才加排程，所以是 "跑完後" 的一分鐘(或現在+1分鐘)
        # 由於 job() 有可能會跑比較久，為了確保是 "現在的1分鐘後"，我們應該先算出時間
        # 但 job() 是直接呼叫的，會 blocking。所以等第一次跑完，我們再加一個 "未來時間" 的 job
        # 假設第一次跑花了 30秒，那這裡加 "now + 1min" 會變成 "start + 1.5min" 執行第二次
        # 這樣符合 "等下發一次(第一次)，一分鐘後在發一次(第二次)"
        run_time_1min = datetime.now() + timedelta(minutes=1)
        scheduler.add_job(job, 'date', run_date=run_time_1min)
        logger.info(f"📅 已加排程: 1分鐘後 ({run_time_1min.strftime('%H:%M:%S')}) 再次執行")
    except KeyboardInterrupt:
        logger.info("使用者強制停止")
    
    try:
        logger.info("⏳ 等待排程觸發 (按 Ctrl+C 停止)...")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass