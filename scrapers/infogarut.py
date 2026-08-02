import json
import requests
import trafilatura
from datetime import datetime

from utils import summarize, keyword

# Menggunakan endpoint API dari hasil inspect network
BASE_API = "https://api.infogarut.id/api/posts"
WEB_URL = "https://www.infogarut.id/posts/"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def scrape():
    hasil = []
    visited = set()
    page = 1
    stop_scraping = False

    while not stop_scraping:
        print(f"Mengambil InfoGarut halaman {page}...")
        
        # URL disesuaikan dengan pola dari tab Network
        url = f"{BASE_API}?page={page}&per_page=10&category=berita"
        
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                print(f"API error dengan status: {r.status_code}")
                break
            
            data_json = r.json()
            
            # API umumnya membungkus list artikel di dalam key 'data'
            items = data_json.get("data", data_json)
            
            if not items:
                print("Sudah tidak ada artikel. Berhenti.")
                break 

            for item in items:
                # Asumsi API mengembalikan 'slug' untuk URL
                slug = item.get("slug", "")
                if not slug:
                    continue
                    
                href = f"{WEB_URL}{slug}"
                
                if href in visited:
                    continue
                visited.add(href)

                # Ekstrak konten menggunakan Trafilatura
                downloaded = trafilatura.fetch_url(href)
                if downloaded is None:
                    continue

                extracted = trafilatura.extract(
                    downloaded,
                    output_format="json",
                    with_metadata=True
                )

                if extracted is None:
                    continue

                art_data = json.loads(extracted)
                text = art_data.get("text", "")
                tanggal_str = art_data.get("date", "") # Format standar: YYYY-MM-DD
                
                # 1. Terapkan Filter Keyword
                kw = keyword(text)
                if not kw:
                    continue # Lewati jika tidak ada keyword ekonomi
                    
                # 2. Terapkan Batas Waktu (April 2026)
                if tanggal_str:
                    try:
                        date_obj = datetime.strptime(tanggal_str, "%Y-%m-%d")
                        
                        # Cek apakah tanggal sebelum 1 Juni 2026
                        if date_obj < datetime(2026, 7, 25):
                            stop_scraping = True
                            print("\nBatas waktu (April 2026) tercapai. Selesai.")
                            break # Keluar dari loop artikel
                    except ValueError:
                        pass # Lewati jika web mengembalikan format tanggal aneh

                hasil.append({
                    "tanggal": tanggal_str,
                    "url": href,
                    "judul_berita": art_data.get("title", ""),
                    "isi_berita": text,
                    "ringkasan": summarize(text),
                    "keyword_ekonomi": kw,
                    "sumber": "InfoGarut"
                })
                print(f"✓ Dapat: {art_data.get('title', href)}")

        except Exception as e:
            print(f"Gagal memproses halaman {page}: {e}")
            break
            
        page += 1

    return hasil