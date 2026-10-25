# Instalasi

PriorityX membutuhkan **Python 3.12 atau lebih baru**. Pemeriksaan otomatis mencakup Python 3.12, 3.13, dan 3.14.

## macOS dan Linux

    python3 --version
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install priorityx

## Windows PowerShell

    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install priorityx
    .\.venv\Scripts\python.exe -m priorityx app

## Menjalankan AutoViz

    python -m priorityx app
    python -m priorityx app --bundle results.json

AutoViz berjalan pada browser tanpa Node.js atau instalasi chart library terpisah. Setelah membuka bundel, gunakan **Tata letak dan pengaturan → Bahasa → Bahasa Indonesia** untuk menghasilkan tampilan grafik berbahasa Indonesia.

## Memperbarui

    python -m pip install --upgrade priorityx

[Lihat dokumentasi English](../installation.md).
