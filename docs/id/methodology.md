# Metodologi

PriorityX memperkirakan posisi skor entitas dengan GLMM, mengelompokkan tanda skor ke dalam kuadran, lalu melacak perubahan pada fitting kumulatif. Skor dan kelas peristiwa adalah keluaran model; keduanya bukan bukti kausalitas atau distress yang terverifikasi.

## Model dan agregasi

Analisis count menghitung baris per entitas-periode atau menjumlahkan `count_col`. Metrik kontinu memakai model Gaussian atau Gamma sesuai konfigurasi. Waktu dipusatkan dan dapat memakai efek musiman.

## Membaca skor

| Kuadran | X | Y |
|---|---|---|
| Q1 | `> 0` | `> 0` |
| Q2 | `<= 0` | `> 0` |
| Q3 | `<= 0` | `<= 0` |
| Q4 | `> 0` | `<= 0` |

Klasifikasi kuadran hanya memakai tanda skor. Filter observasi dan filter label adalah lapisan terpisah.

## Movement dan peristiwa

`track_movement()` mendukung Quarterly dan Monthly. `extract_transitions()` memakai riwayat movement untuk memilih peristiwa. `risk_level` tersimpan dan kelas tampilan Crisis/Investigate/Monitor/Low bukan konsep yang sama.

## Bahasa

Bahasa hanya mengubah teks yang dirender. Koordinat, ukuran panel, marker, tabel tersimpan, dan hasil model tidak berubah. Ini memungkinkan grafik kesehatan/asuransi yang sama dirender ulang dalam Indonesian ketika renderer lokal dipakai, tanpa refit atau migrasi agregat.

## Reproduksibilitas

Atur `PRIORITYX_GLMM_SEED` atau panggil `set_glmm_random_seed()` sebelum fitting untuk hasil yang dapat diulang dalam lingkungan data dan software yang sama.

[Lihat metodologi English](../methodology.md).
