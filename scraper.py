import os
import json
import time
from supabase import create_client, Client
from google import genai 

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
ai_client = genai.Client(api_key=GEMINI_API_KEY)

def analisis_batch(chunk_berita, teks_keyword):
    """Mengirim berita sekaligus ke AI menggunakan nomor urut sebagai ID sementara."""
    
    daftar_teks = []
    # Menggunakan enumerate untuk memberikan nomor indeks (0, 1, 2, dst)
    for i, b in enumerate(chunk_berita):
        teks_potong = b['isi_berita'][:1500].replace('\n', ' ') 
        daftar_teks.append({"id": i, "teks": f"Judul: {b['judul_berita']} | Isi: {teks_potong}"})

    prompt = f"""
    Kamu adalah analis data Badan Pusat Statistik (BPS) yang melakukan pengumpulan fenomena untuk mendukung penyusunan PDRB. Analisis {len(chunk_berita)} artikel berita Garut berikut.
    Tugas untuk masing-masing artikel:
    1. Cek relevansi (Apakah artikel ini BENAR-BENAR membahas konteks dari salah satu kata kunci berikut: {teks_keyword}?). Jawab false jika ini hanya berita kriminal, kecelakaan, atau tidak nyambung dengan konteks kata kunci tersebut meskipun kebetulan ada katanya.
    2. Buat ringkasan 2 kalimat.
    3. Tentukan sentimen (Positif, Negatif, atau Netral).

    Output WAJIB berupa JSON Array murni, contoh format:
    [
      {{"id": 0, "relevan": true, "ringkasan": "Ringkasan...", "sentimen": "Positif"}},
      {{"id": 1, "relevan": false, "ringkasan": "", "sentimen": "Netral"}}
    ]

    Daftar Artikel (JSON):
    {json.dumps(daftar_teks)}
    """

    try:
        response = ai_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt
        )
        result_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(result_text)
    except Exception as e:
        print(f"Error AI: {e}")
        return []

def main():
    print("--- MEMULAI PROSES SCRAPING HARIAN ---")
    
    # 1. AMBIL KEYWORD & JADIKAN STRING
    try:
        res_kw = supabase.table('pengaturan_keyword').select('kata_kunci').eq('is_active', True).execute()
        daftar_keyword = [item['kata_kunci'] for item in res_kw.data]
        if not daftar_keyword:
            print("Tidak ada keyword aktif di database!")
            return
        teks_keyword = ", ".join(daftar_keyword)
        print(f"Menggunakan acuan kata kunci: {teks_keyword}")
    except Exception as e:
        print(f"Gagal ambil keyword: {e}")
        return

    # 2. AMBIL URL EXISTING UNTUK DEDUPLIKASI
    try:
        res_url = supabase.table('fenomena_ekonomi').select('url').execute()
        url_existing = set(item['url'] for item in res_url.data) 
    except:
        url_existing = set()

    # 3. PROSES SCRAPING
    berita = []
    print("\nMenjalankan scraper...")
    berita.extend(infogarut(daftar_keyword, url_existing))
    berita.extend(antara(daftar_keyword, url_existing))
    berita.extend(detik(daftar_keyword, url_existing))

    if not berita:
        print("Tidak ada berita baru yang relevan hari ini.")
        return

    # Deduplikasi internal
    berita_unik_dict = {item['url']: item for item in berita}
    berita_mentah = list(berita_unik_dict.values())

    # 4. FASE KECERDASAN BUATAN (AI BATCHING)
    print(f"\nMemproses {len(berita_mentah)} berita baru dengan AI...")
    berita_final_siap_simpan = []
    batch_size = 5
    
    for i in range(0, len(berita_mentah), batch_size):
        chunk = berita_mentah[i:i + batch_size]
        print(f"\nMengirim Batch {i+1} sampai {i+len(chunk)} ke Gemini...")
        
        maksimal_coba = 3
        berhasil = False
        
        for percobaan in range(maksimal_coba):
            hasil_ai = analisis_batch(chunk, teks_keyword)
            
            if hasil_ai:
                berhasil = True
                for hasil in hasil_ai:
                    idx = hasil.get('id')
                    # Cocokkan nomor urut AI dengan urutan artikel di dalam chunk
                    if isinstance(idx, int) and 0 <= idx < len(chunk):
                        if hasil.get('relevan') == True:
                            artikel = chunk[idx]
                            artikel['ringkasan'] = hasil.get('ringkasan', artikel.get('ringkasan', ''))
                            artikel['sentimen'] = hasil.get('sentimen', 'Netral')
                            berita_final_siap_simpan.append(artikel)
                            print(f"  ✓ Lolos | Sentimen {artikel['sentimen']}: {artikel['judul_berita'][:30]}...")
                        else:
                            print(f"  x Dibuang (Konteks tidak relevan)")
                break 
                
            else:
                print(f"Gagal (Terkena Limit). Menunggu 60 detik (Percobaan {percobaan+1}/{maksimal_coba})...")
                time.sleep(60)
        
        if not berhasil:
            print("Gagal 3x berturut-turut. Memasukkan sisa berita secara mentah tanpa AI...")
            # Fallback (Jaring Pengaman): Masukkan data mentah agar berita tidak hilang
            for artikel in chunk:
                artikel['sentimen'] = 'Netral'
                berita_final_siap_simpan.append(artikel)

        # Pendinginan antar batch (hanya berlaku jika masih ada sisa batch setelahnya)
        if i + batch_size < len(berita_mentah):
            print("Istirahat 60 detik untuk mendinginkan server...")
            time.sleep(60)

    # 5. SIMPAN KE DATABASE
    print(f"\nMenyimpan {len(berita_final_siap_simpan)} berita terverifikasi AI ke Supabase...")
    berita_masuk = 0
    for item in berita_final_siap_simpan:
        try:
            supabase.table('fenomena_ekonomi').insert(item).execute()
            berita_masuk += 1
        except Exception:
            pass

    print(f"Berhasil disimpan: {berita_masuk} berita siap diekspor untuk penyusunan PDRB!")

if __name__ == "__main__":
    main()