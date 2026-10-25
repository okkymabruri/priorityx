# Kuadran, risiko transisi, dan kelas peristiwa

PriorityX memisahkan tiga konsep berikut:

| Konsep | Nilai |
|---|---|
| Kuadran skor | Q1–Q4 |
| Risiko transisi tersimpan | `critical`, `high`, `medium`, `low`, `stable` |
| Kelas peristiwa tampilan | 1 Krisis, 2 Investigasi, 3 Pantau, 4 Rendah |

Kunci dan nilai mesin tetap English; label tampilan dapat diterjemahkan.

## Risiko transisi tersimpan

Perpindahan menuju Q1 umumnya diberi `critical`, perpindahan menuju Q2 `high`, Q4 → Q3 `medium`, dan perpindahan rendah lainnya `low` atau `stable` sesuai aturan ekstraksi.

## Kelas peristiwa tampilan

Dengan riwayat movement dan cumulative count, renderer menerapkan aturan berurutan untuk delta skor dan pertumbuhan count. Jika riwayat tidak tersedia, kelas default adalah Investigate. Ambang ini adalah heuristik operasional, bukan tingkat akurasi yang tervalidasi.

## Akhiran spike

`*X`, `*Y`, dan `*XY` menunjukkan lonjakan sumbu skor. Akhiran, Q-code, dan data sumber tidak diterjemahkan.

[Lihat aturan klasifikasi English](../priority_classification.md).
