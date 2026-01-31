# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import random
import re
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

# Geminiの設定
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- 1. Geminiで記事を作成する関数 ---
def generate_article_by_gemini():
    """Geminiを使って記事のタイトルと本文を生成する"""
    topics = ["最新のテクノロジートレンド", "効率的なプログラミング学習法", "AIツールの活用術", "リモートワークのコツ", "日々の生活ハック"]
    topic = random.choice(topics)
    
    model = genai.GenerativeModel('gemini-3-flash-preview')
    
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
        
        # タイトルと本文の分離処理
        title = content[0].replace('#', '').strip()
        body = '\n'.join(content[1:]).strip()
        
        print(f"Gemini記事生成完了: {title}")
        return title, body
    except Exception as e:
        print(f"Gemini生成エラー: {e}")
        return "テスト記事", "これはテスト投稿です。"

# --- 2. noteログイン & Cookie取得 ---
def get_note_cookies(email, password):
    """noteにログインしてCookieを取得"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-gpu')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        print("ログインページへアクセス...")
        driver.get('https://note.com/login')
        
        # メールアドレス入力
        email_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )
        email_input.send_keys(email)
        
        # パスワード入力
        password_input = driver.find_element(By.NAME, "password")
        password_input.send_keys(password)
        
        # ログインボタンクリック
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_button.click()
        
        print("ログイン処理待機中...")
        time.sleep(10)
        
        cookies = driver.get_cookies()
        cookie_dict = {}
        for cookie in cookies:
            cookie_dict[cookie['name']] = cookie['value']
        
        return cookie_dict
        
    finally:
        driver.quit()

# --- 3. Markdown HTML変換 ---
def markdown_to_html(markdown_text):
    """簡易的なMarkdown→HTML変換"""
    html = markdown_text
    # 見出しの変換
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    # リストの変換
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    # 強調の変換
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    # コードブロックの変換
    html = re.sub(r'```(.+?)```', r'<pre><code>\1</code></pre>', html, flags=re.DOTALL)
    
    # 段落処理
    paragraphs = html.split('\n\n')
    formatted_paragraphs = []
    for p in paragraphs:
        if not p.startswith('<'):
            formatted_paragraphs.append(f'<p>{p}</p>')
        else:
            formatted_paragraphs.append(p)
            
    return '\n'.join(formatted_paragraphs)

# --- 4. 記事作成API ---
def create_article(cookies, title, html_content):
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    data = {
        'body': html_content,
        'name': title,
        'template_key': None,
    }
    
    try:
        response = requests.post('https://note.com/api/v1/text_notes', cookies=cookies, headers=headers, json=data)
        if response.status_code == 200:
            res_json = response.json()
            return res_json['data']['id'], res_json['data']['key']
        else:
            print(f"作成失敗 ステータス: {response.status_code}")
            print(response.text)
            return None, None
    except Exception as e:
        print(f"作成リクエストエラー: {e}")
        return None, None

# --- 5. 記事公開/下書き保存API ---
def publish_article(cookies, article_id, title, html_content):
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    
    data = {
        'body': html_content,
        'name': title,
        'status': 'draft',  # テストのため最初はdraft（下書き）推奨
        't': [],
    }
    
    try:
        response = requests.put(
            f'https://note.com/api/v1/text_notes/{article_id}',
            cookies=cookies,
            headers=headers,
            json=data
        )
        return response.status_code == 200
    except Exception as e:
        print(f"公開リクエストエラー: {e}")
        return False

# --- メイン処理 ---
if __name__ == "__main__":
    print("--- 自動投稿処理開始 ---")
    
    # 環境変数のチェック
    if not all([NOTE_EMAIL, NOTE_PASSWORD, GEMINI_API_KEY]):
        print("エラー: 必要な環境変数(NOTE_EMAIL, NOTE_PASSWORD, GEMINI_API_KEY)が設定されていません。")
        sys.exit(1)

    try:
        # 1. 記事生成
        print("1. 記事を生成中...")
        title, markdown_body = generate_article_by_gemini()
        html_body = markdown_to_html(markdown_body)
        
        # 2. ログイン
        print("2. noteにログイン中...")
        cookies = get_note_cookies(NOTE_EMAIL, NOTE_PASSWORD)
        
        # 3. 記事枠作成
        print("3. 記事枠を作成中...")
        article_id, article_key = create_article(cookies, title, html_body)
        
        if article_id:
            # 4. 記事保存
            print(f"4. 記事を保存中... ID: {article_id}")
            if publish_article(cookies, article_id, title, html_body):
                print(f"✅ 投稿成功！ URL: https://note.com/any/n/{article_key}")
            else:
                print("❌ 保存処理に失敗しました")
                sys.exit(1)
        else:
            print("❌ 記事作成(枠)に失敗しました")
            sys.exit(1)
            
    except Exception as e:
        print(f"予期せぬエラー発生: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
