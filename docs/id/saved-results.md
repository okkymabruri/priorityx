# Bundel hasil tersimpan

`priorityx.results` adalah format pertukaran portable untuk aplikasi visualisasi lokal. Dataset mengidentifikasi satu tipe entitas dan cadence (`monthly` atau `quarterly`) serta dapat berisi tabel matrix, movement, dan transitions.

## Membuat dan membuka bundel

    from priorityx.results import ResultBundle, import_results_csv

    dataset = import_results_csv(entity_type="entity", cadence="monthly", source_id="saved-results-2026", coverage_start="2025-01", as_of="2026-09", matrix_path="priority_matrix.csv", movement_path="movement.csv", transitions_path="transitions.csv")
    ResultBundle([dataset]).save("results.json")

    python -m priorityx app --bundle results.json

## Kolom wajib

| Peran | Identitas | Periode | Kolom lain |
|---|---|---|---|
| Matrix | `entity` | metadata `as_of` | `x_score`, `y_score`, `count`, `quadrant` |
| Movement | `entity` | `quarter` atau `month` | `period_x`, `period_y`, `period_quadrant`, `global_quadrant` |
| Transitions | `entity` | `transition_quarter`/`transition_month` | `from_quadrant`, `to_quadrant`, `risk_level` |

Gunakan periode canonical `YYYY-Qn` atau `YYYY-MM`. Simpan `entity` sebagai string agar pengenal seperti `001` tidak kehilangan nol di depan.

## Bahasa dan provenance

Pilih Bahasa Indonesia di AutoViz atau gunakan `language="id"` pada grafik Matplotlib. Pilihan bahasa hanya mengubah tampilan. `bundle_id`, tabel, nilai skor, kuadran, risiko, dan riwayat lengkap tetap identik.

Kolom tambahan dipertahankan sebagai metadata pemanggil. PriorityX tidak menebak mapping kolom sumber; adapter pemanggil harus melakukan rename secara eksplisit.

[Lihat kontrak saved-results English](../saved-results.md).
