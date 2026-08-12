import json
import re
import time
import requests
import trafilatura
from bs4 import BeautifulSoup
from datetime import datetime

from utils import summarize, keyword

# Menambahkan format singkatan bulan khas Detikcom
MONTH = {
    "Januari": "01", "Februari": "02", "Maret": "03", "April": "04",
    "Mei": "05", "Juni": "06", "Juli": "07", "Agustus": "08",
    "September": "09", "Oktober": "10", "November": "11", "Desember": "12",
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "Jun": "06", "Jul": "07", "Agu": "08", "Sep": "09", 
    "Okt": "10", "Nov": "11", "Des": "12"
}

def parse_date_detik(html_text):
    """Mengekstrak tanggal dari HTML Detik dengan antisipasi singkatan bulan."""
    pattern = r"(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|Jan|Feb|Mar|Apr|Jun|Jul|Agu|Sep|Okt|Nov|Des)\s+(\d{4})"
    m = re.search(pattern, html_text)
    if m:
        hari, bulan, tahun = m.groups()
        return f"{tahun}-{MONTH[bulan]}-{int(hari):02d}"
    return ""

def scrape(daftar_keyword, url_existing):
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
        print(f"Mengambil Detik halaman {page}...")
        
        # Paginasi sesuai parameter yang kamu temukan
        url_tag = f"https://www.detik.com/tag/garut/?sortby=time&page={page}"

        try:
            r = requests.get(url_tag, headers=HEADERS, timeout=30)
            
            if r.status_code != 200:
                print(f"Berhenti: Status {r.status_code}")
                break
                
            soup = BeautifulSoup(r.text, "html.parser")
            
            links = []
            
            # Detik biasanya membungkus daftar berita dalam tag <article>
            for article in soup.find_all("article"):
                a_tag = article.find("a", href=True)
                if a_tag:
                    href = a_tag["href"]
                    # Pastikan hanya mengambil link internal detik
                    if href not in visited and "detik.com" in href:
                        links.append(href)
                        visited.add(href)
            
            # Fallback jika struktur <article> tidak ada, cari ciri khas URL Detik (-d-123456)
            if not links:
                for a in soup.find_all("a", href=True):
                    href = a["href"]

                    if href in url_existing:
                        continue
                    if href not in visited and "-d-" in href and "/tag/" not in href:
                        links.append(href)
                        visited.add(href)

            links = list(set(links))
            
            if not links:
                print("Tidak ada tautan berita baru di halaman ini. Selesai.")
                break

            artikel_lama_di_halaman_ini = 0
            artikel_ekonomi_didapat = 0

            for url in links:
                # Jeda 1 detik agar tidak diblokir server Detik
                time.sleep(1) 

                downloaded = trafilatura.fetch_url(url)
                if downloaded is None:
                    continue

                tanggal_str = parse_date_detik(downloaded)

                extracted = trafilatura.extract(
                    downloaded,
                    output_format="json",
                    with_metadata=True
                )

                if extracted is None:
                    continue

                art_data = json.loads(extracted)
                text = art_data.get("text", "")
                
                if not tanggal_str:
                    tanggal_str = art_data.get("date", "") 
                
                # Cek batas waktu
                if tanggal_str:
                    try:
                        date_obj = datetime.strptime(tanggal_str[:10], "%Y-%m-%d")
                        if date_obj < datetime(2026, 4, 1):
                            artikel_lama_di_halaman_ini += 1
                            continue 
                    except ValueError:
                        pass
                
                # Filter Keyword Ekonomi
                kw = keyword(text, daftar_keyword)
                if not kw:
                    continue 

                artikel_ekonomi_didapat += 1
                hasil.append({
                    "tanggal": tanggal_str[:10] if tanggal_str else "",
                    "url": url,
                    "judul_berita": art_data.get("title", ""),
                    "isi_berita": text,
                    "ringkasan": summarize(text),
                    "keyword_ekonomi": kw,
                    "sumber": "Detik"
                })
                print(f"  ✓ Dapat [{tanggal_str[:10] if tanggal_str else 'N/A'}]: {art_data.get('title', url)[:40]}...")

            print(f"--> Laporan Halaman {page}: Mengecek {len(links)} link, dapat {artikel_ekonomi_didapat} artikel ekonomi, {artikel_lama_di_halaman_ini} artikel kedaluwarsa.")

            # Berhenti jika mayoritas (3 atau lebih) artikel di halaman ini sudah lama
            if artikel_lama_di_halaman_ini >= 3:
                stop_scraping = True
                print(f"\nBatas kedaluwarsa tercapai. Berhenti memproses Detik.")
                break

        except requests.exceptions.Timeout:
            print(f"\nKoneksi Timeout di halaman {page}! Menghentikan scraping Detik dengan aman.")
            break 
        except Exception as e:
            print(f"\nGagal memproses halaman {page}: {e}")
            break

        if stop_scraping:
            break

        page += 1
        
        # Jeda 2 detik antar halaman
        time.sleep(2) 

    return hasil