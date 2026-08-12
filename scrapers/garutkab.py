import json
import re
import requests
import trafilatura

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from utils import summarize, keyword

BASE = "https://www.garutkab.go.id/berita"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0 Safari/537.36"
    )
}

MONTH = {
    "Januari": "01",
    "Februari": "02",
    "Maret": "03",
    "April": "04",
    "Mei": "05",
    "Juni": "06",
    "Juli": "07",
    "Agustus": "08",
    "September": "09",
    "Oktober": "10",
    "November": "11",
    "Desember": "12",
}


def parse_date(html: str) -> str:
    """
    Mengubah:
    Kamis, 20 Februari 2025
    menjadi:
    2025-02-20
    """

    pattern = (
        r"(Senin|Selasa|Rabu|Kamis|Jumat|Sabtu|Minggu),\s*"
        r"(\d{1,2})\s*"
        r"(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s*"
        r"(\d{4})"
    )

    m = re.search(pattern, html)

    if not m:
        return ""

    _, hari, bulan, tahun = m.groups()

    return f"{tahun}-{MONTH[bulan]}-{int(hari):02d}"


def get_title(soup):

    # cari h1 dulu
    h = soup.find("h1")
    if h:
        return h.get_text(" ", strip=True)

    # kalau tidak ada, cari h2
    h = soup.find("h2")
    if h:
        return h.get_text(" ", strip=True)

    # fallback
    return ""


def scrape(daftar_keyword, url_existing):

    hasil = []
    visited = set()

    homepage = requests.get(BASE, headers=HEADERS, timeout=30)

    soup = BeautifulSoup(homepage.text, "html.parser")

    for a in soup.find_all("a", href=True):

        href = a["href"]

        if href in url_existing:
            continue

        if "/berita/" not in href:
            continue

        url = urljoin(BASE, href)

        if url in visited:
            continue

        visited.add(url)

        try:

            response = requests.get(
                url,
                headers=HEADERS,
                timeout=30
            )

            html = response.text

            soup_detail = BeautifulSoup(html, "html.parser")

            judul = get_title(soup_detail)

            tanggal = parse_date(html)

            downloaded = trafilatura.fetch_url(url)

            if downloaded is None:
                continue

            extracted = trafilatura.extract(
                downloaded,
                output_format="json",
                with_metadata=True,
            )

            if extracted is None:
                continue

            data = json.loads(extracted)

            isi = data.get("text", "")

            kw = keyword(isi, daftar_keyword)
            if not kw:
                continue

            hasil.append(
                {
                    "tanggal": tanggal,
                    "url": url,
                    "judul_berita": judul,
                    "isi_berita": isi,
                    "ringkasan": summarize(isi),
                    "keyword_ekonomi": kw,
                    "sumber": "Garutkab",
                }
            )

            print(f"✓ {judul}")

        except Exception as e:

            print(f"Gagal: {url}")
            print(e)

    return hasil