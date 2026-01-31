import os
import sys
import time
import re
import random
import json
import requests
import google.generativeai as genai
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- 設定 ---
NOTE_EMAIL = os.environ.get("NOTE_EMAIL")
NOTE_PASSWORD = os.environ.get("NOTE_PASSWORD")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# 記事生成の設定
def generate_article_by_gemini():
    if not GEMINI_API_KEY:
        return "テストタイトル", "Gemini APIキーが設定されていません。"
    
    genai.configure(api_key=GEMINI_API_KEY)
    # モデル名は安定版の 'gemini-1.5-flash' を推奨
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    topic = random.choice(["AIの未来", "Pythonプログラミング", "時短術", "読書の習慣"])
    prompt = f"note.comに投稿するブログ記事を書いてください。テーマは「{topic}」で、1行目はタイトル、2行目以降はMarkdown形式の本文にしてください。"
    
    try:
        response = model.generate_content(prompt)
        lines = response.text.strip().split('\n')
        title = lines[0].replace('#', '').strip()
        body = '\n'.join(lines[1:]).strip()
        return title, body
    except Exception as e:
        print(f"Geminiエラー: {e}")
        return "自動生成記事", "本文の生成に失敗しました。"

def get_authenticated_session():
    """undetected-chromedriverを使用してセッションを取得する"""
    options = uc.ChromeOptions()
    # ユーザーデータを保存することで、次回からログインをスキップできる可能性が高まる
    options.add_argument(f"--user-data-dir={os.path.join(os.getcwd(), 'chrome_profile')}")
    
    # noteはHeadlessを検知しやすいため、初回や安定動作のためには通常モード推奨
    # options.add_argument('--headless') 
    
    driver = uc.Chrome(options=options)
    wait = WebDriverWait(driver, 20)
    
    try:
        driver.get('https://note.com/')
        time.sleep(3)

        # ログイン済みかチェック（投稿ボタンがあるか等）
        is_logged_in = len(driver.find_elements(By.CSS_SELECTOR, 'a[href*="/notes/new"]')) > 0
        
        if not is_logged_in:
            print("ログインが必要です。ページに移動します...")
            driver.get('https://note.com/login')
            
            # メールアドレス入力
            email_field = wait.until(EC.presence_of_element_located((By.ID, 'email')))
            email_field.send_keys(NOTE_EMAIL)
            
            # パスワード入力
            password_field = driver.find_element(By.ID, 'password')
            password_field.send_keys(NOTE_PASSWORD)
            
            print("!!! 重要 !!!")
            print("ReCAPTCHAが表示されている場合は、ブラウザを操作して手動で解決してください。")
            print("ログインボタンを押した後、トップページが表示されるまで待機してください。")
            
            # ログインボタンをクリック（手動で押してもOK）
            # login_btn = driver.find_element(By.CSS_SELECTOR, 'button[data-type="primaryNext"]')
            # login_btn.click()

            # ログイン完了まで最大5分待機（手動操作を考慮）
            wait_login = WebDriverWait(driver, 300)
            wait_login.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/notes/new"]')))
            print("ログイン成功を確認しました。")

        # Cookie取得
        cookies = driver.get_cookies()
        session_cookies = {c['name']: c['value'] for c in cookies}
        
        # XSRF-TOKENの取得
        xsrf_token = session_cookies.get('XSRF-TOKEN', '')
        
        driver.quit()
        return session_cookies, xsrf_token

    except Exception as e:
        print(f"ブラウザ操作エラー: {e}")
        driver.quit()
        return None, None

def markdown_to_html(markdown_text):
    """note APIが受け付ける簡易的なHTML変換"""
    html = markdown_text
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    paragraphs = html.split('\n\n')
    formatted = [f'<p>{p.strip()}</p>' for p in paragraphs if p.strip()]
    return '\n'.join(formatted)

def post_to_note(cookies, xsrf_token, title, html_body):
    """requestsを使用して記事を投稿する"""
    url = "https://note.com/api/v5/text_notes"
    
    headers = {
        'X-Xsrf-Token': xsrf_token,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Content-Type': 'application/json',
        'Referer': 'https://note.com/notes/new',
        'Origin': 'https://note.com',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    payload = {
        "body": html_body,
        "name": title,
        "status": "draft", # 最初は必ず下書きでテスト
        "template_key": None
    }
    
    response = requests.post(url, headers=headers, cookies=cookies, json=payload)
    
    if response.status_code == 200 or response.status_code == 201:
        data = response.json()
        print("投稿成功（下書き保存）")
        return data['data']['key']
    else:
        print(f"APIエラー: {response.status_code}")
        print(response.text)
        return None

if __name__ == "__main__":
    # 1. 記事生成
    print("Geminiで記事を生成中...")
    title, body = generate_article_by_gemini()
    html_body = markdown_to_html(body)
    
    # 2. セッション取得
    print("noteのセッションを取得中...")
    cookies, token = get_authenticated_session()
    
    if cookies and token:
        # 3. 投稿
        key = post_to_note(cookies, token, title, html_body)
        if key:
            print(f"完了！確認URL: https://note.com/n/n{key}")
    else:
        print("セッションの取得に失敗しました。")
