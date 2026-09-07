# Surse și registrul de proveniență

## Snapshotul GTFS

- **Publicatorul datelor:** S.C. Informatică Feroviară S.A., prin [data.gov.ro](https://data.gov.ro/organization/9b0bc5fc-2062-4aef-b916-b48b7c459af7?organization=sc-informatica-feroviara-sa).
- **Converterul:** [vasile/data.gov.ro-gtfs-exporter](https://github.com/vasile/data.gov.ro-gtfs-exporter).
- **Commit fixat:** `a8d353dec5e6ac0c82de58c81c3396d7a78c5de3`.
- **Perioadă:** 14 decembrie 2025 – 12 decembrie 2026.
- **Tip:** model static al mersului anual planificat.

Snapshotul a fost verificat prin SHA-256 înainte de fuziune. Fișierele brute din `data/raw/gtfs/` și membrii arhivei GTFS trebuie să aibă aceleași sume.

## Ce derivă din date

Statisticile despre operatori, curse, stații, opriri, excepții și coordonate sunt calculate din fișierele GTFS. GeoJSON și SQLite nu adaugă o sursă independentă; ele sunt materializări ale acelorași rânduri. Atlasul adaugă o modelare de coridor și distanțe geodezice aproximative.

Pentru snapshotul curent, profilarea locală produce 7 operatori, 1.023 de rute, 2.103 curse, 1.695 de stații, 30.267 de opriri programate, 203 de servicii calendaristice și 19.864 de excepții. Raportul verificat este în `qa/report.json` după rularea validatorului.

## Licențiere

Licențele sunt atașate fiecărui set de operator în portalul sursă. În metadatele consultate pentru snapshotul curent, seturile CFR Călători, Regio Călători, InterRegional și Softrans sunt listate sub OGL-ROU-1.0, iar setul Ferotrafic–TFI sub CC BY 4.0. Această evidență trebuie reverificată pentru fiecare versiune nouă.

Codul original al acestui depozit este acoperit de [`LICENSE-CODE`](LICENSE-CODE). Termenii datelor și atribuirea obligatorie nu sunt înlocuiți de licența codului; vezi [`LICENSES.md`](LICENSES.md).
