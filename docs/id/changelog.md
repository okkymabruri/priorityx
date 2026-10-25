# Changelog

Halaman ini merangkum perubahan publik. Untuk rincian lengkap dan nomor versi, lihat [changelog English](../changelog.md).

## v0.7.3 (belum dirilis)

- Menambahkan lokalisasi English/Bahasa Indonesia untuk grafik Matplotlib,
  ekspor hasil tersimpan, dan workspace AutoViz berbasis Plotly.
- Menambahkan dokumentasi paralel Bahasa Indonesia tanpa mengubah default
  English, schema hasil tersimpan, nilai analisis, atau geometri grafik.

## v0.7.2

- Cache movement memakai fingerprint permintaan 16 heksadesimal yang mencakup data dan pengaturan analisis.
- Permintaan identik memakai file yang sama; refresh mengganti hanya kunci yang cocok secara atomik.

## v0.7.1

- Perbaikan jendela driver Quarterly, forwarding `count_col`, metadata trajektori, dan kontribusi driver berbasis perubahan neto.

## v0.7.0

- AutoViz lokal memakai Plotly untuk matriks, linimasa, dan trajektori dari hasil tersimpan.
- Ekspor HTML offline dan ekspor Matplotlib tetap tersedia.

Penerjemahan chart tidak mengubah data tersimpan, model, atau nilai output.
