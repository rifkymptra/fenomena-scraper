from supabase import create_client, Client
import os

from scrapers.infogarut import scrape as infogarut
from scrapers.antara import scrape as antara
from scrapers.detik import scrape as detik
from scrapers.garutkab import scrape as garutkab

# --- MENGAMBIL KREDENSIAL DARI ENVIRONMENT VARIABLES ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Kredensial Supabase tidak ditemukan di Environment Variables!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def main():
    print("--- MEMULAI PROSES SCRAPING ---")
    print("Mengambil pengaturan keyword dari database...")
    
    try:
        response = supabase.table('pengaturan_keyword').select('kata_kunci').eq('is_active', True).execute()
        daftar_keyword = [item['kata_kunci'] for item in response.data]
        print(f"Keyword aktif ({len(daftar_keyword)}): {', '.join(daftar_keyword)}")
    except Exception as e:
        print(f"Gagal mengambil keyword dari database: {e}")
        return

    if not daftar_keyword:
        print("Tidak ada keyword aktif. Proses dihentikan.")
        return

    # --- TAMBAHAN BARU: MENGAMBIL URL EXISTING ---
    print("Mengambil riwayat URL dari database untuk mencegah duplikasi...")
    try:
        res_url = supabase.table('fenomena_ekonomi').select('url').execute()
        # Ubah menjadi struktur data Set agar pencarian (lookup) super cepat
        url_existing = set(item['url'] for item in res_url.data) 
        print(f"Terdapat {len(url_existing)} berita di database.")
    except Exception as e:
        print(f"Gagal mengambil URL existing, lanjut dengan database kosong: {e}")
        url_existing = set()

    berita = []

    # Oper juga url_existing ke dalam fungsi

    print("\nMenjalankan scraper Garutkab...")
    berita.extend(garutkab(daftar_keyword, url_existing))

    print("\nMenjalankan scraper InfoGarut...")
    berita.extend(infogarut(daftar_keyword, url_existing))

    print("\nMenjalankan scraper Antara Jabar...")
    berita.extend(antara(daftar_keyword, url_existing))

    print("\nMenjalankan scraper Detik...")
    berita.extend(detik(daftar_keyword, url_existing))

    print(f"\nTotal berita baru yang berhasil diekstrak: {len(berita)}")
    if len(berita) == 0:
        print("Tidak ada berita baru yang relevan untuk disimpan.")
        return

    # --- 1. DEDUPLIKASI INTERNAL ---
    # Mengubah list menjadi dictionary dengan 'url' sebagai kunci untuk membuang duplikat otomatis
    berita_unik_dict = {item['url']: item for item in berita}
    berita_bersih = list(berita_unik_dict.values())

    print(f"Total berita unik siap simpan: {len(berita_bersih)}")
    print("Menyimpan data ke Supabase...")
    
    berita_masuk = 0
    berita_duplikat_db = 0

    # --- 2. PENYIMPANAN AMAN SATU PER SATU ---
    for item in berita_bersih:
        try:
            supabase.table('fenomena_ekonomi').insert(item).execute()
            berita_masuk += 1
        except Exception as e:
            # Jika masih gagal (misal karena constraint lain), script tidak akan mati total
            berita_duplikat_db += 1
            pass

    print("\n--- RINGKASAN ---")
    print(f"Berhasil disimpan : {berita_masuk} berita baru")
    if berita_duplikat_db > 0:
        print(f"Dilewati (Duplikat/Error) : {berita_duplikat_db} berita")

if __name__ == "__main__":
    main()