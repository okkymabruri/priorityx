# Workspace lokal AutoViz

Workspace lokal membaca bundel hasil atau CSV hasil analisis yang sudah disimpan. Membuka file, mengubah pilihan, dan mengatur tata letak tidak menjalankan model.

## Kontrol

- **Jenis**, **Frekuensi**, dan **Entitas** mengubah populasi tampilan.
- **Tata letak dan pengaturan → Bahasa** memilih English atau Bahasa Indonesia.
- **Lihat data** menyediakan tabel matrix, peristiwa linimasa, dan trajektori.
- **Detail** menjelaskan provenance, seleksi trajektori, dan layout report.
- **Ekspor** menyediakan HTML offline, SVG matriks, serta PNG/SVG cetak melalui service lokal.

Pilihan bahasa tersimpan dalam view settings dan ikut dalam HTML offline. Nilai data dan identitas bundel tidak berubah.

## Tiga grafik

Workspace menampilkan **Matriks kuadran → Linimasa transisi → Trajektori**. Quarterly menjadi pembuka jika tersedia; Monthly digunakan jika itu satu-satunya cadence. Linimasa menampilkan YTD, sedangkan tabel mempertahankan riwayat lengkap.

## Ekspor statis

    from priorityx.results import ResultBundle
    from priorityx.views import prepare_bundle, resolve_settings
    from priorityx.viz.export import render_static

    prepared = prepare_bundle(ResultBundle.load("results.json"))
    settings = resolve_settings(None, prepared)
    settings.language = "id"
    fig, report = render_static(prepared["datasets"][0], settings, "timeline")
    fig.savefig("linimasa.png", dpi=settings.dpi)

Renderer memakai ukuran baseline yang sama untuk English dan Indonesian. Jika teks lebih panjang dan bertabrakan, semua label tetap dipertahankan dan report menandai konflik.

[Lihat panduan workspace English](../app.md).
