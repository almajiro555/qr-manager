import streamlit as st
import pandas as pd
import qrcode
import os
import urllib.request
from pathlib import Path
from datetime import datetime
import io
from PIL import Image, ImageDraw, ImageFont

# PDF生成用ライブラリ
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

# --- 初期設定 ---
DB_CSV = Path("devices.csv")
QR_DIR = Path("qr_codes")
PDF_DIR = Path("pdfs")
QR_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)

# --- 日本語フォントの設定（クラウド対応） ---
try:
    # 現場で圧倒的に読みやすい「BIZ UDゴシック」を自動ダウンロード
    cloud_font_path = "BIZUDGothic-Regular.ttf"
    if not os.path.exists(cloud_font_path):
        font_url = "https://github.com/googlefonts/morisawa-biz-ud-gothic/raw/main/fonts/ttf/BIZUDGothic-Regular.ttf"
        urllib.request.urlretrieve(font_url, cloud_font_path)
    
    pdfmetrics.registerFont(TTFont("BIZUDGothic", cloud_font_path))
    FONT_NAME = "BIZUDGothic"
except:
    try:
        # ローカル環境（パソコン）のフォールバック
        win_font_path = "C:/Windows/Fonts/meiryo.ttc"
        pdfmetrics.registerFont(TTFont("Meiryo", win_font_path))
        FONT_NAME = "Meiryo"
    except:
        FONT_NAME = "Helvetica"

# --- ユーティリティ関数 ---
def safe_filename(name):
    """ファイル名に使えない文字をアンダースコアに置換"""
    keepcharacters = (' ', '.', '_', '-')
    return "".join(c for c in name if c.isalnum() or c in keepcharacters).rstrip()

# --- PDF生成関数 ---
def create_pdf(data, output_path):
    c = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4
    
    # 1. ヘッダー帯（黄色）
    bg_c = (1.0, 0.84, 0.0) # #FFD700 (Gold/Yellow)
    txt_c = (0.2, 0.2, 0.2)
    c.setFillColorRGB(*bg_c)
    c.rect(0, height - 100, width, 100, stroke=0, fill=1)
    
    # 2. 右上の管理番号
    c.setFillColorRGB(*txt_c)
    c.setFont(FONT_NAME, 12)
    c.drawRightString(width - 40, height - 30, f"管理番号: {data['id']}")
    
    # 3. 機器名（タイトル）
    c.setFont(FONT_NAME, 28)
    c.drawString(40, height - 70, data['name'])
    
    # 4. 使用電源の帯（オレンジ）
    p_y = height - 130
    c.setFillColorRGB(0.95, 0.61, 0.13) # オレンジ
    c.rect(40, p_y, width - 80, 24, stroke=0, fill=1)
    
    c.setFillColorRGB(*txt_c)
    c.setFont(FONT_NAME, 14)
    # 絵文字を廃止し、確実に表示される四角マークに変更
    c.drawString(45, p_y + 7, f"■ 使用電源: AC {data['power']}")

    # ==========================================
    # --- 新しい画像レイアウト（5枚配置） ---
    # ==========================================
    
    # 画像を描画するための共通ヘルパー関数（枠線やNone表示も自動対応）
    def draw_image_box(c, img_file, title, x, y, w, h):
        c.setFillColorRGB(0, 0, 0)
        c.setFont(FONT_NAME, 12)
        c.drawString(x, y + h + 5, title) # タイトルを画像の上に配置
        
        if img_file is not None:
            try:
                img = ImageReader(img_file)
                # アスペクト比を維持して中央に描画
                c.drawImage(img, x, y, width=w, height=h, preserveAspectRatio=True, anchor='c')
            except Exception as e:
                c.rect(x, y, w, h) # エラー時は枠だけ
        else:
            # 画像がない場合は点線の枠と「None」を表示
            c.setDash(3, 3)
            c.rect(x, y, w, h)
            c.setDash()
            c.setFont(FONT_NAME, 10)
            c.drawCentredString(x + w/2, y + h/2, f"None ({title}なし)")

    # 1. 機器外観（上段・左）大きく配置
    draw_image_box(c, data.get('img_exterior'), "機器外観", 40, 360, 250, 300)

    # 2. コンセント位置（上段・右の上半分）縮小して配置
    draw_image_box(c, data.get('img_outlet'), "コンセント位置", 305, 520, 250, 140)

    # 3. 資産管理ラベル（上段・右の下半分）縮小して配置
    draw_image_box(c, data.get('img_label'), "資産管理ラベル", 305, 360, 250, 140)

    # 4. LOTO手順書 1ページ目（下段・左）
    draw_image_box(c, data.get('img_loto1'), "LOTO手順書（1ページ目）", 40, 40, 250, 280)

    # 5. LOTO手順書 2ページ目（下段・右）
    draw_image_box(c, data.get('img_loto2'), "LOTO手順書（2ページ目）", 305, 40, 250, 280)

    c.save()

# --- 印刷用ラベル生成関数 ---
def create_label_image(data):
    """
    縦2.5cm×横4cmの実寸大ラベル画像を生成
    解像度300dpiで設計
    """
    w_px, h_px = 472, 295
    label_img = Image.new('RGB', (w_px, h_px), 'white')
    draw = ImageDraw.Draw(label_img)
    
    font_path = "BIZUDGothic-Regular.ttf"
    try:
        font_lg = ImageFont.truetype(font_path, 20)
        font_sm = ImageFont.truetype(font_path, 12)
        font_xs = ImageFont.truetype(font_path, 8)
    except:
        font_lg = font_sm = font_xs = ImageFont.load_default()
    
    # 1. 工場のマークをカラフルに復元（画像として配置）
    try:
        factory_icon_url = "https://raw.githubusercontent.com/googlefonts/morisawa-biz-ud-gothic/main/docs/biz_font_specimen/sample_ud_gothic.png"
        if not os.path.exists("factory_icon.png"):
            urllib.request.urlretrieve(factory_icon_url, "factory_icon.png")
        icon_img = Image.open("factory_icon.png")
        icon_img = icon_img.resize((30, 30))
        label_img.paste(icon_img, (10, 10))
    except:
        draw.text((10, 10), "🏭", fill="black", font=font_lg)
    
    # 2. タイトル
    draw.text((45, 10), "機器情報・LOTO確認ラベル", fill="black", font=font_lg)
    
    # 3. QRコードを配置
    if 'img_qr' in data:
        qr_pil_img = data['img_qr'].convert('RGB')
        qr_pil_img = qr_pil_img.resize((140, 140))
        label_img.paste(qr_pil_img, (10, 50))
    
    # 4. 詳細テキスト
    x_text = 160
    y_text = 50
    line_height = 20
    draw.text((x_text, y_text), f"機器名称: {data['name']}", fill="black", font=font_sm)
    draw.text((x_text, y_text + line_height), f"使用電源: AC {data['power']}", fill="black", font=font_sm)
    
    # 5. 区切り線
    y_line = y_text + line_height * 2 + 5
    draw.line((x_text, y_line, w_px - 10, y_line), fill="gray", width=1)
    
    # 6. 極短の案内文
    draw.text((x_text, y_line + 10), "📱詳細スキャン (LOTO･外観･ｺﾝｾﾝﾄ)", fill="black", font=font_xs)
    
    return label_img

# --- メインアプリ ---
def main():
    query_params = st.query_params
    is_redirect_mode = "id" in query_params
    
    if is_redirect_mode:
        st.set_page_config(page_title="PDFを開く", layout="centered")
        target_id = query_params["id"]
        
        if DB_CSV.exists():
            df = pd.read_csv(DB_CSV)
            match = df[df["ID"] == target_id]
            if not match.empty:
                target_url = match.iloc[-1]["URL"]
                
                link_html = f"""
                <div style="text-align: center; margin-top: 60px;">
                    <p style="font-size: 20px; font-weight: bold; color: #333;">✅ 資料の準備ができました</p>
                    <a href="{target_url}" target="_blank" style="
                        display: inline-block;
                        margin-top: 15px;
                        padding: 20px 40px;
                        background-color: #28a745;
                        color: white;
                        font-size: 22px;
                        font-weight: bold;
                        text-decoration: none;
                        border-radius: 8px;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
                    ">
                        📄 ここをタップしてPDFを開く
                    </a>
                </div>
                """
                st.markdown(link_html, unsafe_allow_html=True)
            else:
                st.error(f"エラー: 管理番号 '{target_id}' は見つかりませんでした。")
        else:
            st.error("エラー: データベースが見つかりません。")
            
    else:
        st.set_page_config(page_title="設備QR＆PDF管理システム", layout="wide")
        st.title("🏭 設備QR＆PDF管理システム")
        
        st.info("※ この画面はPCでのPDF作成・台帳登録用です。")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.header("1. 基本情報入力")
            did = st.text_input("管理番号 (例: 2699)")
            name = st.text_input("設備名称 (例: 5t金型反転機)")
            power = st.selectbox("使用電源", ["100V", "200V"], index=None, placeholder="選択してください")
            
        with col2:
            st.header("2. 画像アップロード")
            img_exterior = st.file_uploader("機器外観", type=["png", "jpg", "jpeg"])
            img_outlet = st.file_uploader("コンセント位置", type=["png", "jpg", "jpeg"])
            img_label = st.file_uploader("資産管理ラベル", type=["png", "jpg", "jpeg"])
            img_loto1 = st.file_uploader("LOTO手順書（1ページ目）", type=["png", "jpg", "jpeg"])
            img_loto2 = st.file_uploader("LOTO手順書（2ページ目）", type=["png", "jpg", "jpeg"])
            
        st.markdown("---")
        st.header("3. PDF生成・保存")
        if st.button("PDFを生成してダウンロード", type="primary"):
            if did and name:
                data = {
                    "id": did,
                    "name": name,
                    "power": power,
                    "img_exterior": img_exterior,
                    "img_outlet": img_outlet,
                    "img_label": img_label,
                    "img_loto1": img_loto1,
                    "img_loto2": img_loto2
                }
                
                safe_id = safe_filename(did)
                pdf_path = PDF_DIR / f"{safe_id}.pdf"
                
                # PDF生成実行
                create_pdf(data, pdf_path)
                
                # 生成確認後にダウンロードボタンを表示
                if pdf_path.exists():
                    st.success(f"{pdf_path.name} の生成が完了しました！")
                    with open(pdf_path, "rb") as pdf_file:
                        st.download_button(
                            label="📥 PDFをダウンロード",
                            data=pdf_file,
                            file_name=pdf_path.name,
                            mime="application/pdf"
                        )
                else:
                    st.error("エラー：PDFの保存に失敗しました。")
            else:
                st.error("管理番号と設備名称は必須です。")

        st.markdown("---")
        st.header("4. 自動転送QRコード生成")
        long_url = st.text_input("パソコンでPDFを開いた時の【上部アドレスバーの長いURL】（GitHub等のURL）を貼り付け")
        if st.button("QRコードを生成して台帳更新", type="secondary"):
            if long_url and did:
                safe_id = safe_filename(did)
                qr_path = QR_DIR / f"{safe_id}_qr.png"
                
                clean_base_url = "https://equipment-qr-manager.streamlit.app"
                dynamic_url = f"{clean_base_url}/?id={did}"
                
                img_qr = qrcode.make(dynamic_url)
                img_qr.save(qr_path)
                st.success("自動転送用のQRコードを生成しました！")
                
                df = pd.read_csv(DB_CSV) if DB_CSV.exists() else pd.DataFrame(columns=["ID", "Name", "Power", "URL", "Updated"])
                new_data = {"ID": did, "Name": name, "Power": power, "URL": long_url, "Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                df.to_csv(DB_CSV, index=False)
                st.info("台帳(devices.csv)に最終目的地を記録しました。")
                
                # --- 追加：印刷用ラベルの生成と表示 ---
                st.markdown("---")
                st.subheader("🏷️ コンセント・タグ用ラベルのダウンロード")
                
                label_data = {
                    "name": name,
                    "power": power,
                    "img_qr": img_qr
                }
                label_img = create_label_image(label_data)
                
                buf = io.BytesIO()
                label_img.save(buf, format="PNG")
                byte_im = buf.getvalue()
                
                st.image(label_img, caption="2.5cm × 4cm 印刷用ラベル", width=300)
                
                st.download_button(
                    label="📥 ラベル画像(PNG)をダウンロード",
                    data=byte_im,
                    file_name=f"{safe_id}_label.png",
                    mime="image/png"
                )
            else:
                st.error("「管理番号」と「URL」の両方を入力してください。")

if __name__ == "__main__":
    main()










