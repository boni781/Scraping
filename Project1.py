from flask import Flask, request, render_template, jsonify
import requests
from bs4 import BeautifulSoup
import fitz  
import io
import openai  
import re
import json


app = Flask(__name__)

@app.route('/manual')
def manual():
    return render_template('manual.html')

# ✅ Set API KEY OpenAI 
openai.api_key = "AIzaSyDSztNuC-oP6ke6ZBJKbFHQ6pnp9531MkM"  # Ganti dengan OpenAI API key kamu

# =======================
# 🔍 Ambil semua link halaman item dari halaman daftar
# =======================
def get_item_page_links(url):
    try:
        print(f"[🔍] Mengambil item links dari: {url}")
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        item_links = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Gabungkan dengan URL asal jika relatif
            full_url = requests.compat.urljoin(url, href)

            # Cek apakah URL mengandung /angka/ dan tidak mengandung file ekstensi (.pdf, .jpg, dsb)
            if re.search(r"/\d{3,6}/$", full_url) and not re.search(r"\.(pdf|jpg|png|docx?|zip)$", full_url, re.IGNORECASE):
                item_links.add(full_url)

        print(f"[✅] Ditemukan {len(item_links)} item links.")
        return list(item_links)
    except Exception as e:
        print(f"[❌] Gagal mengambil item links: {e}")
        return []

# =======================
# 📄 Ambil semua link PDF dari halaman item
# =======================
def get_pdfs_from_item_page(item_url):
    try:
        print(f"[📄] Mencari PDF di: {item_url}")
        response = requests.get(item_url, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        pdf_links = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Hanya ambil link PDF yang bukan thumbnail/lightbox
            if (
                re.search(r"\.pdf(\?|$)", href, re.IGNORECASE) and
                "haslightboxThumbnailVersion" not in href and
                "lightbox" not in href
            ):
                full_url = requests.compat.urljoin(item_url, href)
                pdf_links.append(full_url)

        print(f"[✅] Ditemukan {len(pdf_links)} PDF links (difilter).")
        return list(set(pdf_links))
    except Exception as e:
        print(f"[❌] Gagal mengambil PDF: {e}")
        return []


# =======================
# 📖 Baca isi PDF dari URL
# =======================
def read_pdf_from_url(pdf_url):
    try:
        print(f"[📖] Membaca PDF: {pdf_url}")
        response = requests.get(pdf_url, timeout=10)
        with fitz.open(stream=io.BytesIO(response.content), filetype="pdf") as doc:
            text = ""
            for page in doc:
                text += page.get_text()
        print(f"[✅] PDF terbaca, panjang teks: {len(text)} karakter.")
        return text
    except Exception as e:
        print(f"[❌] Gagal membaca PDF: {e}")
        return ""

# =======================
# 🌐 Form Utama: Input URL, Keyword, Start Index, Limit (VERSI FINAL)
# =======================
@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    display_url = "" 
    keyword = ""
    start_index = 0
    limit = 3
    errors = []
    mode = "list"

    if request.method == "POST":
        url_input = request.form.get("url", "")
        selected_jurusan_name = request.form.get("jurusan", "")
        
        keyword = request.form.get("keyword", "").lower()
        mode = request.form.get("scrape_mode", "list")
        
        try:
            start_index = int(request.form.get("start_index", 0))
            limit = int(request.form.get("limit", 3))
        except ValueError:
            errors.append("Start index dan limit harus berupa angka.")
            start_index = 0
            limit = 3

        target_url = ""
        if url_input:
            target_url = url_input
            display_url = url_input
        elif selected_jurusan_name:
            display_url = selected_jurusan_name
            
            # --- [BLOK INI DIPERBAIKI TOTAL UNTUK MENGATASI ERROR] ---
            try:
                with open("jurusan_upn.json", encoding="utf-8") as f:
                    # Asumsi: jurusan_data adalah DICTIONARY, bukan list
                    # Contoh: { "Nama Jurusan": "URL_Jurusan", ... }
                    jurusan_data = json.load(f)

                # Langsung ambil URL menggunakan nama jurusan sebagai KEY.
                # .get() lebih aman karena akan mengembalikan None jika key tidak ada,
                # tidak seperti [key] yang akan menyebabkan error.
                target_url = jurusan_data.get(selected_jurusan_name)

                if not target_url:
                    # Ini terjadi jika nama jurusan yang dipilih tidak ada di file JSON
                    errors.append(f"URL untuk jurusan '{selected_jurusan_name}' tidak ditemukan di data JSON.")

            except json.JSONDecodeError:
                # Error jika file JSON rusak/tidak valid formatnya
                errors.append("Format file jurusan_upn.json tidak valid. Harap periksa kembali isinya.")
            except Exception as e:
                # Menangkap error lain yang mungkin terjadi
                errors.append(f"Gagal memproses file jurusan_upn.json: {e}")
            # --- [AKHIR DARI BLOK PERBAIKAN] ---
        
        if not target_url or not keyword:
            if not keyword:
                errors.append("Kata kunci tidak boleh kosong.")
            if not target_url and not errors:
                 errors.append("URL atau Jurusan harus diisi.")
        else:
            # Sisa kode scraping di bawah ini tidak perlu diubah
            if mode == "detail":
                pdf_links = get_pdfs_from_item_page(target_url)
                if not pdf_links:
                    errors.append(f"Tidak ada PDF pada halaman: {target_url}")
                # ... sisa logika detail mode Anda
                # (pastikan dilanjutkan di sini)

            else: # mode == "list"
                item_pages = get_item_page_links(target_url)
                if not item_pages:
                    errors.append(f"Tidak dapat mengambil daftar item dari URL: {target_url}")
                
                item_pages = item_pages[start_index : start_index + limit]

                for item_url in item_pages:
                    pdf_links = get_pdfs_from_item_page(item_url)
                    if not pdf_links:
                        # errors.append(f"Tidak ada PDF pada: {item_url}")
                        continue

                    valid_pdfs = []
                    for pdf_url in pdf_links:
                        text = read_pdf_from_url(pdf_url)
                        if not text:
                            # errors.append(f"Gagal membaca: {pdf_url}")
                            continue

                        count = text.lower().count(keyword)
                        if count > 0:
                            valid_pdfs.append({"pdf_url": pdf_url, "count": count})

                    if valid_pdfs:
                        results.append({"item_page": item_url, "pdfs": valid_pdfs})

    return render_template("Project1.html", results=results, url=display_url, keyword=keyword,
                           start_index=start_index, limit=limit, errors=errors, scrape_mode=mode)
# =======================
# 🤖 Endpoint baru untuk saran keyword dari AI (real-time)
# =======================
@app.route("/suggest", methods=["POST"])
def suggest_keyword():
    partial = request.json.get("partial", "")
    if not partial.strip():
        return jsonify({"suggestions": []})

    # Prompt untuk AI
    prompt = f"Beri beberapa saran kata kunci yang relevan dengan '{partial}' dalam konteks teknik kimia."

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.7
        )
        suggestion_text = response.choices[0].message.content.strip()
        suggestions = [s.strip("•- ") for s in suggestion_text.split("\n") if s.strip()]
        return jsonify({"suggestions": suggestions})
    except Exception as e:
        print("OpenAI error:", e)
        return jsonify({"suggestions": [], "error": str(e)})
    
    # =======================
    #  memangil json ke html dropdown   
    # =======================
    

@app.route('/data-jurusan')
def data_jurusan():
    try:
        with open("jurusan_upn.json", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)})



if __name__ == "__main__":
    app.run(debug=True)
