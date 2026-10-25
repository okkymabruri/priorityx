# Contoh AutoViz: insiden TI

Contoh publik ini memakai hasil analisis insiden TI yang sudah tersimpan. Tidak ada fitting atau refit yang dijalankan saat membuka workspace.

## Membuka contoh

    python -m priorityx app --bundle examples/autoviz/incidents-quarterly.json

Pilih **Bahasa Indonesia** pada pengaturan untuk menerjemahkan judul, sumbu, legenda, hover text, tabel, dan status grafik. `entity`, `source_id`, periode (`YYYY-Qn`/`YYYY-MM`), dan nilai kuadran tetap apa adanya.

## Membaca tiga grafik

1. **Matriks kuadran** memperlihatkan posisi skor setiap entitas.
2. **Linimasa transisi** memperlihatkan peristiwa YTD dan kelas algoritmiknya.
3. **Trajektori** memperlihatkan perpindahan skor pada periode tersimpan.

Pemilihan entitas menghubungkan ketiga grafik. Ekspor HTML offline menyimpan pilihan bahasa dan riwayat lengkap.

Gunakan [kontrak bundel hasil](saved-results.md) untuk kolom wajib, validasi, dan pemetaan CSV.

[Lihat contoh English](../autoviz-example.md).
