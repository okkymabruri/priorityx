# PriorityX

PriorityX adalah pustaka Python untuk memprioritaskan entitas dan mendeteksi eskalasi menggunakan model GLMM. API dan kolom hasil tetap menggunakan nama teknis yang sama pada semua bahasa.

## Mulai

- [Instalasi](installation.md)
- [Mulai cepat](quickstart.md)
- [Contoh AutoViz](autoviz-example.md)

    python -m priorityx app

## AutoViz

AutoViz membaca bundel hasil tersimpan atau CSV hasil analisis. Aplikasi tidak menjalankan fitting saat grafik dibuka. Pilih Bahasa Indonesia pada **Tata letak dan pengaturan** untuk menerjemahkan label grafik dan antarmuka grafik; bahasa Inggris tetap menjadi default.

## Analisis Python

Gunakan [referensi API](api-reference.md) untuk fitting, movement, transisi, driver, dan grafik. [Metodologi](methodology.md) menjelaskan skor dan batas interpretasinya, sedangkan [klasifikasi prioritas](priority_classification.md) menjelaskan kuadran, risiko, dan kelas peristiwa.

Kunci data seperti `Q1`–`Q4`, `critical`, `high`, `medium`, `low`, `stable`, serta akhiran `*X`, `*Y`, `*XY` tidak diterjemahkan agar bundel tetap kompatibel.

[Lihat dokumentasi English](../index.md).
