import re

def summarize(text, n=3):
    text = text.replace("\n"," ")
    kalimat = re.split(r'(?<=[.!?]) +', text)
    return " ".join(kalimat[:n])

# Tambahkan parameter daftar_keyword
def keyword(text, daftar_keyword):
    text = text.lower()
    hasil = []
    for k in daftar_keyword:
        if k in text:
            hasil.append(k)
    return ", ".join(sorted(set(hasil)))