# -*- coding: utf-8 -*-
import os
import sys
import time
import re
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

# --- 設定 ---
NOTE_EMAIL = os.environ.get("NOTE_EMAIL")
NOTE_PASSWORD = os.environ.get("NOTE_PASSWORD")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Geminiの設定 (最新モデル名に修正)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def generate_article_by_gemini():
    """Geminiを使って記事のタイトルと本文を生成する"""
    topics = ["最新のテクノロジートレンド", "効率的なプログラミング学習法", "AIツールの活用術", "リモートワークのコツ", "日々の生活ハック"]
    topic = random.choice(topics)
    
    # モデル名を最新のものに修正
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    note.comに投稿するためのブログ記事を書いてください。
    テーマ: {topic}
    
    出力形式:
    1行目: タイトル
    2行目以降: Markdown形式の本文（見出しやリストを活用して読みやすく）
    
    本文は「はじめに」「メインコンテンツ」「まとめ」の構成にしてください。
    """
    
    try:
        response = model.generate_content(prompt)
        content = response.text.strip().split('\n')
        
        title = content[0].replace('#', '').strip()
        body = '\n'.join(content[1:]).strip()
        
        print(f"Gemini記事生成完了: {title}")
        return title, body
    except Exception as e:
        print(f"Gemini生成エラー: {e}")
        return "テスト記事 " + time.strftime("%Y-%m-%d"), "これは自動生成されたテスト投稿です。"

def get_note_session_info(email, password):
    """Seleniumでログインし、APIに必要なCookieとXSRFトークンを取得"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1280,1024')
    # ユーザーエージェントを設定してボット検知を回避
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 30)
    
    try:
        print("ログインページへアクセス中...")
        driver.get('https://note.com/login')
        
        # メールアドレス入力（複数のセレクタで試行）
        email_field = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, 'input[id="email"], input[name="email"]'
        )))
        email_field.send_keys(email)
        
        # パスワード入力
        password_field = driver.find_element(By.CSS_SELECTOR, 'input[type="password"], input[name="password"]')
        password_field.send_keys(password)
        
        # ログインボタンクリック
        login_button = driver.find_element(By.XPATH, "//button[contains(., 'ログイン') or @type='submit']")
        login_button.click()
        
        print("ログイン完了を待機中...")
        # ログイン後のページ遷移を確認
        wait.until(EC.url_contains('note.com'))
        time.sleep(5) # 遷移後の読み込みを念のため待機

        cookies = driver.get_cookies()
        
        # Requests用に整形
        session_cookies = {c['name']: c['value'] for c in cookies}
        # noteのAPIには X-XSRF-TOKEN が必要な場合があるため取得
        xsrf_token = session_cookies.get('XSRF-TOKEN', '')
        
        print("ログイン成功・セッション情報取得完了")
        return session_cookies, xsrf_token
        
    except Exception as e:
        print(f"Seleniumエラー詳細: {e}")
        # 失敗時のスクリーンショット保存（デバッグ用）
        driver.save_screenshot("error_screenshot.png")
        raise
    finally:
        driver.quit()

def markdown_to_html(markdown_text):
    """noteのAPI形式に合わせた簡易HTML変換"""
    html = markdown_text
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    
    paragraphs = html.split('\n\n')
    formatted = [f'<p>{p.strip()}</p>' if not p.strip().startswith('<') else p.strip() for p in paragraphs if p.strip()]
    return '\n'.join(formatted)

def post_to_note(cookies, xsrf_token, title, html_content):
    """APIを使用して記事を作成・保存する"""
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'X-Xsrf-Token': xsrf_token,
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    # 1. 新規作成（枠の確保）
    create_url = 'https://note.com/api/v1/text_notes'
    payload = {
        'body': html_content,
        'name': title,
        'status': 'draft', # まずは下書きとして保存
        'template_key': None,
    }
    
    try:
        res = requests.post(create_url, cookies=cookies, headers=headers, json=payload)
        res.raise_for_status()
        data = res.json()['data']
        note_id = data['id']
        note_key = data['key']
        
        print(f"記事作成成功(下書き): ID {note_id}")
        
        # 公開したい場合はここで status を 'publish' に更新する処理を追加可能
        # 今回は安全のため下書き保存まで
        return note_key
    except Exception as e:
        print(f"APIエラー: {e}")
        if 'res' in locals(): print(res.text)
        return None

if __name__ == "__main__":
    if not all([NOTE_EMAIL, NOTE_PASSWORD, GEMINI_API_KEY]):
        print("環境変数が不足しています。")
        sys.exit(1)

    try:
        # 1. 記事生成
        title, markdown_body = generate_article_by_gemini()
        html_body = markdown_to_html(markdown_body)
        
        # 2. Seleniumでセッション取得
        cookies, xsrf_token = get_note_session_info(NOTE_EMAIL, NOTE_PASSWORD)
        
        # 3. APIで投稿
        note_key = post_to_note(cookies, xsrf_token, title, html_body)
        
        if note_key:
            print(f"\n✨ 成功！下書き保存されました。")
            print(f"確認URL: https://note.com/n/{note_key}")
        else:
            print("投稿に失敗しました。")
            sys.exit(1)
            
    except Exception as e:
        print(f"実行エラー: {e}")
        sys.exit(1)
