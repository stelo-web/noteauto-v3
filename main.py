import os
import time
import json
import random
import requests
import google.generativeai as genai
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re

# --- 設定 ---
NOTE_EMAIL = os.environ.get("NOTE_EMAIL")
NOTE_PASSWORD = os.environ.get("NOTE_PASSWORD")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Geminiの設定
genai.configure(api_key=GEMINI_API_KEY)

# --- 1. Geminiで記事を作成する関数 ---
def generate_article_by_gemini():
    """Geminiを使って記事のタイトルと本文を生成する"""
    topics = ["最新のテクノロジートレンド", "効率的なプログラミング学習法", "AIツールの活用術", "リモートワークのコツ", "日々の生活ハック"]
    topic = random.choice(topics)
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    note.comに投稿するためのブログ記事を書いてください。
    テーマ: {topic}
    
    出力形式:
    1行目: タイトル
    2行目以降: Markdown形式の本文（見出しやリストを活用して読みやすく）
    
    本文は「はじめに」「メインコンテンツ」「まとめ」の構成にしてください。
    """
    
    response = model.generate_content(prompt)
    content = response.text.strip().split('\n')
    
    title = content[0].replace('#', '').strip()
    body = '\n'.join(content[1:]).strip()
    
    print(f"Gemini記事生成完了: {title}")
    return title, body

# --- 2. noteログイン & Cookie取得 (資料より改修) ---
def get_note_cookies(email, password):
    """noteにログインしてCookieを取得（GitHub Actions用ヘッドレス対応）"""
    options = Options()
    options.add_argument('--headless')  # ヘッドレスモード有効化
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        driver.get('https://note.com/login')
        
        # [span_1](start_span)メールアドレス入力[span_1](end_span)
        email_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )
        email_input.send_keys(email)
        
        # [span_2](start_span)パスワード入力[span_2](end_span)
        password_input = driver.find_element(By.NAME, "password")
        password_input.send_keys(password)
        
        # [span_3](start_span)ログインボタンクリック[span_3](end_span)
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()
        
        [span_4](start_span)time.sleep(10) [span_4](end_span)
        
        cookies = driver.get_cookies()
        cookie_dict = {}
        for cookie in cookies:
            [span_5](start_span)cookie_dict[cookie['name']] = cookie['value'] #[span_5](end_span)
        
        return cookie_dict
        
    finally:
        driver.quit()

# --- 3. Markdown HTML変換 (資料そのまま) ---
def markdown_to_html(markdown_text):
    """簡易的なMarkdown→HTML変換"""
    html = markdown_text
    [span_6](start_span)html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE) #[span_6](end_span)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    [span_7](start_span)html = re.sub(r'```(.+?)```', r'<pre><code>\1</code></pre>', html, flags=re.DOTALL) #[span_7](end_span)
    paragraphs = html.split('\n\n')
    html = '\n'.join([f'<p>{p}</p>' if not p.startswith('<') else p for p in paragraphs])
    return html

# --- 4. 記事作成API (資料より) ---
def create_article(cookies, title, html_content):
    headers = {
        'Content-Type': 'application/json',
        [span_8](start_span)'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', #[span_8](end_span)
    }
    data = {
        'body': html_content,
        'name': title,
        'template_key': None,
    }
    response = requests.post('https://note.com/api/v1/text_notes', cookies=cookies, headers=headers, json=data)
    if response.status_code == 200:
        [span_9](start_span)return response.json()['data']['id'], response.json()['data']['key'] #[span_9](end_span)
    return None, None

# --- 5. 記事公開/下書き保存API (資料より改修) ---
def publish_article(cookies, article_id, title, html_content):
    headers = {
        'Content-Type': 'application/json',
        [span_10](start_span)'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', #[span_10](end_span)
    }
    
    # 即時公開する場合は status を 'public' に設定
    # 安全のため、最初は 'draft' (下書き) を推奨します。即公開なら 'public' に書き換えてください。
    data = {
        'body': html_content,
        'name': title,
        [span_11](start_span)'status': 'public',  # 即公開設定[span_11](end_span)
        't': [], # タグ（必要であれば）
    }
    
    response = requests.put(
        f'https://note.com/api/v1/text_notes/{article_id}',
        cookies=cookies,
        headers=headers,
        [span_12](start_span)json=data #[span_12](end_span)
    )
    return response.status_code == 200

# --- メイン処理 ---
if __name__ == "__main__":
    print("--- 自動投稿処理開始 ---")
    try:
        # 1. 記事生成
        title, markdown_body = generate_article_by_gemini()
        html_body = markdown_to_html(markdown_body)
        
        # 2. ログイン
        print("ログイン中...")
        cookies = get_note_cookies(NOTE_EMAIL, NOTE_PASSWORD)
        
        # 3. 記事枠作成
        print("記事枠作成中...")
        article_id, article_key = create_article(cookies, title, html_body)
        
        if article_id:
            # 4. 記事公開（または下書き保存）
            print(f"記事公開処理中... ID: {article_id}")
            if publish_article(cookies, article_id, title, html_body):
                print(f"✅ 投稿成功！ URL: https://note.com/any/n/{article_key}")
            else:
                print("❌ 公開処理に失敗しました")
        else:
            print("❌ 記事作成に失敗しました")
            
    except Exception as e:
        print(f"エラー発生: {e}")
        exit(1)
