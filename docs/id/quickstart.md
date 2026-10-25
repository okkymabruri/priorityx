# Mulai cepat

## Instalasi

    python -m pip install priorityx pandas

## Membuka hasil tersimpan

    python -m priorityx app --bundle results.json

## Analisis dasar

    import pandas as pd
    import priorityx as px

    events = pd.read_csv("events.csv", dtype={"entity_id": str})
    events["observed_at"] = pd.to_datetime(events["observed_at"], errors="raise")
    matrix = px.fit_priority_matrix(events, entity_col="entity_id", timestamp_col="observed_at", temporal_granularity="quarterly")
    movement = px.track_movement(events, entity_col="entity_id", timestamp_col="observed_at", temporal_granularity="quarterly")
    transitions = px.extract_transitions(movement)

## Grafik Bahasa Indonesia

`language="id"` hanya menerjemahkan teks tampilan. Nilai skor, koordinat, klasifikasi, dan data pemanggil tidak berubah.

    px.plot_priority_matrix(matrix, entity_name="Layanan", language="id")
    px.plot_transition_timeline(transitions, entity_name="Layanan", language="id")
    px.plot_entity_trajectories(movement, entity_name="Layanan", language="id")

Label atau judul yang diberikan pemanggil tetap memiliki prioritas atas terjemahan default. Bahasa Inggris tetap digunakan jika parameter tidak diisi.

Simpan tabel lengkap sebelum membuka AutoViz. Lihat [bundel hasil tersimpan](saved-results.md) untuk skema dan aturan periode.

[Lihat mulai cepat English](../quickstart.md).
