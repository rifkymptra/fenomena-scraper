import json
import re
import requests
import trafilatura
from bs4 import BeautifulSoup
from datetime import datetime

from utils import summarize, keyword

# Dictionary untuk mengubah teks bulan menjadi angka
MONTH = {
    "Januari": "01", "Februari": "02", "Maret": "03", "April": "04",
    "Mei": "05", "Juni": "06", "Juli": "07", "Agustus": "08",
    "September": "09", "Oktober": "10", "November": "11", "Desember": "12"
}

def parse_date_antara(html_text):
    """Mengekstrak tanggal manual dari HTML mentah Antara Jabar."""
    # Mencari pola seperti: 1 Oktober 2025
    pattern = r"(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+(\d{4})"
    m = re.search(pattern, html_text)
    if m:
        hari, bulan, tahun = m.groups()
        return f"{tahun}-{MONTH[bulan]}-{int(hari):02d}"
    return ""

def scrape():
    hasil = []
    visited = set()
    page = 1
    stop_scraping = False

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/138.0 Safari/537.36"
        )
    }

    while not stop_scraping:
        print(f"Mengambil Antara Jabar halaman {page}...")
        
        if page == 1:
            url_tag = "https://jabar.antaranews.com/tag/garut"
        else:
            url_tag = f"https://jabar.antaranews.com/tag/garut/{page}"

        try:
            r = requests.get(url_tag, headers=HEADERS, timeout=30)
            
            if r.status_code != 200:
                print(f"Berhenti: Halaman tidak ditemukan atau error (Status: {r.status_code}).")
                break
                
            soup = BeautifulSoup(r.text, "html.parser")
            
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/berita/" in href and href not in visited:
                    if href.startswith("/"):
                        href = f"https://jabar.antaranews.com{href}"
                    links.append(href)
                    visited.add(href)
            
            links = list(set(links))
            
            if not links:
                print("Tidak ada tautan berita baru di halaman ini. Selesai.")
                break

            for url in links:
                downloaded = trafilatura.fetch_url(url)
                if downloaded is None:
                    continue

                # --- MENGAMBIL TANGGAL SECARA MANUAL ---
                tanggal_str = parse_date_antara(downloaded)

                extracted = trafilatura.extract(
                    downloaded,
                    output_format="json",
                    with_metadata=True
                )

                if extracted is None:
                    continue

                art_data = json.loads(extracted)
                text = art_data.get("text", "")
                
                # Jika Regex gagal, baru gunakan bawaan trafilatura
                if not tanggal_str:
                    tanggal_str = art_data.get("date", "") 
                
                kw = keyword(text)
                if not kw:
                    continue 

                # --- PENGECEKAN BATAS WAKTU ---
                if tanggal_str:
                    try:
                        date_obj = datetime.strptime(tanggal_str, "%Y-%m-%d")
                        if date_obj < datetime(2026, 7, 15):
                            stop_scraping = True
                            print(f"\nBatas waktu tercapai pada artikel tgl {tanggal_str}. Berhenti memproses.")
                            break 
                    except ValueError:
                        pass

                hasil.append({
                    "tanggal": tanggal_str,
                    "url": url,
                    "judul_berita": art_data.get("title", ""),
                    "isi_berita": text,
                    "ringkasan": summarize(text),
                    "keyword_ekonomi": kw,
                    "sumber": "Antara Jabar"
                })
                print(f"✓ Dapat [{tanggal_str}]: {art_data.get('title', url)[:50]}...")

        except Exception as e:
            print(f"Gagal memproses halaman {page}: {e}")
            break

        if stop_scraping:
            break

        page += 1

    return hasil