import pandas as pd

from scrapers.garutkab import scrape as garutkab
from scrapers.infogarut import scrape as infogarut
from scrapers.antara import scrape as antara
from scrapers.detik import scrape as detik
from scrapers.statusjabar import scrape as statusjabar

berita = []

print("Scraping Garutkab...")
berita.extend(garutkab())

print("Scraping InfoGarut...")
berita.extend(infogarut())

print("Scraping Antara Jabar...")
berita.extend(antara())

print("Scraping Detik...")
berita.extend(detik())


# Kolom wajib ada meskipun tidak ada berita sama sekali yang didapat,
# supaya tidak crash saat df kosong (misal semua sumber gagal koneksi).
KOLOM = ["tanggal", "url", "judul_berita", "isi_berita", "ringkasan", "keyword_ekonomi", "sumber"]

df = pd.DataFrame(berita, columns=KOLOM)

df = df.drop_duplicates(subset=["url"])

df.to_excel("fenomena.xlsx", index=False)

print(df.head())

print()

print("Total berita :", len(df))

if len(df) > 0:
    print(df[["tanggal", "judul_berita", "sumber"]])
else:
    print("Tidak ada berita yang berhasil diambil dari semua sumber.")