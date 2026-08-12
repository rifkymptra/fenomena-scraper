import os
import json
import time
from supabase import create_client, Client
from google import genai # Menggunakan library baru

from scrapers.infogarut import scrape as infogarut
from scrapers.antara import scrape as antara
from scrapers.detik import scrape as detik

# --- KREDENSIAL ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 

if not SUPABASE_URL or not SUPABASE_KEY or not GEMINI_API_KEY:
    raise ValueError("Kredensial Supabase atau Gemini tidak ditemukan!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Inisiasi Client Gemini yang Baru
ai_client = genai.Client(api_key=GEMINI_API_KEY)

def analisis_dengan_ai(teks):
    """Mengirim teks ke Gemini untuk disaring, diringkas, dan dicek sentimennya."""
    prompt = f"""
    Analisis artikel berita berikut yang berkaitan dengan Kabupaten Garut.
    Tugas:
    1. Tentukan apakah berita ini BENAR-BENAR membahas ekonomi, harga pangan, pertanian, pariwisata, UMKM, atau bisnis. (Jawab false jika ini berita kriminal, pembunuhan, pendidikan, atau kecelakaan meskipun ada kata 'harga').
    2. Buat ringkasan yang enak dibaca (maksimal 2 kalimat).
    3. Tentukan sentimen berita terhadap perekonomian (Positif, Negatif, atau Netral).

    Output WAJIB berupa format JSON murni persis seperti ini (tanpa markdown tambahan):
    {{
        "relevan": true,
        "ringkasan": "Isi ringkasan...",
        "sentimen": "Positif"
    }}

    Teks berita:
    {teks[:3000]} 
    """
    try:
        # Cara panggil API dengan format genai terbaru
        response = ai_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt
        )
        # Membersihkan format markdown bawaan AI agar bisa dibaca Python
        result_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(result_text)
    except Exception as e:
        print(f"Error AI: {e}")
        return None

def main():
    print("--- MEMULAI PROSES SCRAPING ---")
    
    try:
        response = supabase.table('pengaturan_keyword').select('kata_kunci').eq('is_active', True).execute()
        daftar_keyword = [item['kata_kunci'] for item in response.data]
    except Exception as e:
        print(f"Gagal ambil keyword: {e}")
        return

    if not daftar_keyword: return

    try:
        res_url = supabase.table('fenomena_ekonomi').select('url').execute()
        url_existing = set(item['url'] for item in res_url.data) 
    except:
        url_existing = set()

    berita = []
    print("\nMenjalankan scraper...")
    berita.extend(infogarut(daftar_keyword, url_existing))
    berita.extend(antara(daftar_keyword, url_existing))
    berita.extend(detik(daftar_keyword, url_existing))

    if len(berita) == 0:
        print("Tidak ada berita baru yang relevan.")
        return

    # Deduplikasi internal
    berita_unik_dict = {item['url']: item for item in berita}
    berita_mentah = list(berita_unik_dict.values())

    # --- FASE KECERDASAN BUATAN (AI) ---
    print(f"\nMemproses {len(berita_mentah)} berita...")
    berita_final_siap_simpan = []

    # Jika berita terlalu banyak (tarikan awal/reset), lewati AI agar tidak kena limit 20/hari
    if len(berita_mentah) > 15:
        print("Volume berita terlalu besar untuk API gratis. Mengabaikan AI untuk mengamankan kuota...")
        for item in berita_mentah:
            item['sentimen'] = 'Netral' # Default sentimen
            berita_final_siap_simpan.append(item)
    else:
        print("Menggunakan AI Gemini untuk analisis mendalam...")
        for item in berita_mentah:
            print(f"- Analisis AI: {item['judul_berita'][:40]}...")
            hasil_ai = analisis_dengan_ai(item['isi_berita'])
            
            if hasil_ai and hasil_ai.get('relevan') == True:
                item['ringkasan'] = hasil_ai.get('ringkasan', item['ringkasan'])
                item['sentimen'] = hasil_ai.get('sentimen', 'Netral')
                berita_final_siap_simpan.append(item)
                print(f"  ✓ Lolos | Sentimen: {item['sentimen']}")
            else:
                print("  x Dibuang (Konteks tidak relevan)")
            
            # Jeda dinaikkan jadi 15 detik agar aman dari limit "5 request per menit"
            time.sleep(15) 

    # --- SIMPAN KE DATABASE ---
    print(f"\nMenyimpan {len(berita_final_siap_simpan)} berita ke Supabase...")
    berita_masuk = 0
    for item in berita_final_siap_simpan:
        try:
            supabase.table('fenomena_ekonomi').insert(item).execute()
            berita_masuk += 1
        except Exception:
            pass

    print(f"\nBerhasil disimpan: {berita_masuk} berita siap disajikan ke pimpinan!")

if __name__ == "__main__":
    main()