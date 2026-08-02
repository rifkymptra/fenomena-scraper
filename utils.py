import re

KEYWORDS = [
    "pertanian","perkebunan","peternakan","perikanan",
    "industri","tekstil","garment","pariwisata",
    "hotel","restoran","wisata","umkm",
    "perdagangan","pasar","harga","inflasi",
    "investasi","jalan","transportasi",
    "ekspor","impor","cabai","beras",
    "bawang","kopi","teh","kentang",
    "tenaga kerja","pengangguran","ekonomi","pdrb"
]


def summarize(text, n=3):

    text = text.replace("\n"," ")

    kalimat = re.split(r'(?<=[.!?]) +', text)

    return " ".join(kalimat[:n])


def keyword(text):

    text = text.lower()

    hasil = []

    for k in KEYWORDS:
        if k in text:
            hasil.append(k)

    return ", ".join(sorted(set(hasil)))