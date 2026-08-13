import os
import json
import time
from supabase import create_client, Client
from google import genai

# --- GANTI DENGAN KREDENSIAL SUPABASE & GEMINI MILIKMU || ini untuk eksekusi manual di lokal kalo limit API Gemini habis---
SUPABASE_URL = ""
SUPABASE_KEY = ""
GEMINI_API_KEY = ""

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Menambahkan parameter teks_keyword
def proses_borongan(chunk_berita, teks_keyword):
    """Mengirim 30 berita sekaligus ke AI dengan keyword dinamis."""
    
    # Menyiapkan teks gabungan
    daftar_teks = []
    for b in chunk_berita:
        # Kita ambil 1500 huruf pertama saja agar AI tidak kelebihan beban membaca
        teks_potong = b['isi_berita'][:1500].replace('\n', ' ') 
        daftar_teks.append({"id": b['id'], "teks": f"Judul: {b['judul_berita']} | Isi: {teks_potong}"})

    # Menyuntikkan teks_keyword langsung ke dalam prompt AI
    prompt = f"""
    Kamu adalah analis data Badan Pusat Statistik (BPS) yang melakukan pengumpulan fenomena untuk mendukung penyusunan PDRB. Analisis {len(chunk_berita)} artikel berita Garut berikut.
    Tugas untuk masing-masing artikel:
    1. Cek relevansi (Apakah artikel ini BENAR-BENAR membahas konteks dari salah satu kata kunci berikut: {teks_keyword}?). Jawab false jika ini hanya berita kriminal, kecelakaan, atau tidak nyambung dengan konteks kata kunci tersebut meskipun kebetulan ada katanya.
    2. Buat ringkasan 2 kalimat.
    3. Tentukan sentimen (Positif, Negatif, atau Netral).

    Output WAJIB berupa JSON Array murni, contoh format:
    [
      {{"id": 123, "relevan": true, "ringkasan": "Ringkasan...", "sentimen": "Positif"}},
      {{"id": 124, "relevan": false, "ringkasan": "", "sentimen": "Netral"}}
    ]

    Daftar Artikel (JSON):
    {json.dumps(daftar_teks)}
    """

    try:
        response = ai_client.models.generate_content(
            model='gemini-3.6-flash', # Gunakan model terbaru
            contents=prompt
        )
        result_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(result_text)
    except Exception as e:
        print(f"Error AI: {e}")
        return []

def main():
    print("--- MEMULAI PEMBERSIHAN DATA (BATCH AI) ---")
    
    # --- AMBIL KEYWORD DARI DATABASE ---
    try:
        res_kw = supabase.table('pengaturan_keyword').select('kata_kunci').eq('is_active', True).execute()
        daftar_keyword = [item['kata_kunci'] for item in res_kw.data]
        if not daftar_keyword:
            print("Tidak ada keyword aktif di database!")
            return
        teks_keyword = ", ".join(daftar_keyword)
        print(f"Menggunakan acuan {len(daftar_keyword)} kata kunci: {teks_keyword}")
    except Exception as e:
        print(f"Gagal ambil keyword: {e}")
        return
    
    res = supabase.table('fenomena_ekonomi').select('id, judul_berita, isi_berita').eq('sentimen', 'Netral').execute()
    berita_mentah = res.data
    
    if not berita_mentah:
        print("Semua data sudah bersih dan teranalisis AI!")
        return

    print(f"Ditemukan {len(berita_mentah)} berita yang belum dianalisis secara mendalam.")
    
    batch_size = 30 # Sesuai permintaanmu
    
    for i in range(0, len(berita_mentah), batch_size):
        chunk = berita_mentah[i:i + batch_size]
        print(f"\nMengirim Batch {i+1} sampai {i+len(chunk)} ke Gemini...")
        
        # --- SISTEM AUTO-RETRY ---
        maksimal_coba = 3
        berhasil = False
        
        for percobaan in range(maksimal_coba):
            # Memasukkan teks_keyword saat memanggil fungsi
            hasil_ai = proses_borongan(chunk, teks_keyword)
            
            if hasil_ai:
                berhasil = True
                berita_diupdate = 0
                berita_dihapus = 0
                
                for hasil in hasil_ai:
                    id_berita = hasil.get('id')
                    if not id_berita: continue
                    
                    if hasil.get('relevan') == True:
                        supabase.table('fenomena_ekonomi').update({
                            'ringkasan': hasil.get('ringkasan'),
                            'sentimen': hasil.get('sentimen')
                        }).eq('id', id_berita).execute()
                        berita_diupdate += 1
                    else:
                        supabase.table('fenomena_ekonomi').delete().eq('id', id_berita).execute()
                        berita_dihapus += 1
                        
                print(f"Selesai! Update: {berita_diupdate} | Hapus (Nyasar): {berita_dihapus}")
                break # Keluar dari loop percobaan karena sudah sukses
                
            else:
                print(f"Gagal (Terkena Limit). Menunggu 60 detik sebelum mencoba lagi (Percobaan {percobaan+1}/{maksimal_coba})...")
                time.sleep(60)
        
        if not berhasil:
            print("Gagal 3x berturut-turut. Terpaksa melewati batch ini.")

        # Waktu pendinginan standar antar batch agar aman dari limit per menit
        print("Istirahat 60 detik untuk mendinginkan server...")
        time.sleep(60)

    print("\n--- PROSES SELESAI ---")

if __name__ == "__main__":
    main()