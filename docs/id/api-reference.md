# Referensi API

Nama fungsi, parameter, kolom, dan nilai mesin tetap dalam English agar kode yang sudah ada tetap kompatibel. Parameter `language="id"` tersedia pada tiga fungsi grafik utama.

## Fungsi inti

- `fit_priority_matrix(...)` menghitung skor GLMM dan mengembalikan `entity`, `x_score`, `y_score`, `count`, dan `quadrant`.
- `aggregate_entity_metrics(...)` dan `add_priority_indices(...)` menyediakan metrik agregat dan indeks tambahan.
- `sensitivity_analysis(...)` membandingkan hasil pada bobot atau ambang yang berbeda.

## Tracking

- `track_movement(...)` menghitung posisi kumulatif pada jadwal Quarterly atau Monthly.
- `load_or_track_movement(...)` memakai cache movement yang dikunci oleh data dan pengaturan permintaan.
- `extract_transitions(...)` mendeteksi perpindahan kuadran.
- `extract_transition_drivers(...)` dan `display_transition_drivers(...)` menganalisis kontribusi driver.

## Grafik

    fig = px.plot_priority_matrix(results_df, entity_name="Layanan", language="id")
    fig = px.plot_transition_timeline(transitions_df, movement_df=movement_df, language="id")
    fig = px.plot_entity_trajectories(movement_df, entity_name="Layanan", language="id")

`language` menerima `"en"` atau `"id"`, dengan default `"en"`. `title`, `x_label`, `y_label`, dan nama entitas dari pemanggil tidak diterjemahkan otomatis.

`Q1`–`Q4`, `risk_level`, kelas numerik, dan akhiran spike tetap berupa nilai kontrak. Terjemahan hanya diterapkan pada judul, sumbu, legenda, keterangan, dan label tampilan.

## Workspace dan ekspor

`ResultBundle`, `prepare_bundle`, `resolve_settings`, dan `render_static` memakai hasil tersimpan yang sama dengan AutoViz. `ViewSettings.language` menyimpan pilihan bahasa; bundel dan nilai analisis tidak berubah. Ukuran, koordinat, dan marker grafik tidak berubah karena bahasa.

Untuk referensi parameter lengkap, lihat [API reference English](../api-reference.md).
