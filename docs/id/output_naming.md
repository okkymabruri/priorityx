# Penamaan output

Gunakan `plot_path` dan `csv_path` untuk menentukan lokasi output secara eksplisit. Nama fungsi dan kolom tetap English agar pipeline lama tetap berjalan.

    from pathlib import Path
    import priorityx as px

    px.plot_priority_matrix(
        results_df,
        language="id",
        plot_path=Path("results/plot/matriks.png"),
        csv_path=Path("results/csv/matriks.csv"),
    )

Bahasa hanya berlaku pada teks gambar. CSV tetap berisi schema dan nilai yang sama.

[Lihat penamaan output English](../output_naming.md).
