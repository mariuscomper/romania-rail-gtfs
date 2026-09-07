# romania-rail-gtfs

## Arhivă reproductibilă pentru calea ferată de călători din România

Acest depozit reunește infrastructura de date din `gtfs-feroviar` cu atlasul timp–distanță din `romania-train-graph`. Livrează același snapshot GTFS în patru forme utile:

- pachet GTFS standard, pentru aplicații de rutare și cercetare;
- bază de date SQLite, pentru interogări locale rapide;
- strat GeoJSON cu stațiile și operatorii care le deservesc;
- atlas compact de coridoare, pentru vizualizări și analiză programatică.

Include și scripturi de construire, manifesturi SHA-256 și validatoare fără dependențe externe. Scopul este să existe o copie publică, verificabilă și reutilizabilă a mersului anual de trenuri, nu doar o pagină de prezentare.

### Ce poate face pentru oameni

Datele pot fi folosite de dezvoltatori pentru planificatoare de călătorie, de cercetători și jurnaliști pentru comparații între operatori, de administrații pentru cartografierea accesului la transport și de pasageri pentru instrumente independente. Un format comun face posibilă verificarea afirmațiilor despre rețea și păstrează un punct de plecare pentru comparații între ani.

### Ce nu este

Este un orar anual planificat pentru perioada 14 decembrie 2025 – 12 decembrie 2026. Nu este flux GTFS-RT și nu descrie poziții reale, întârzieri, anulări, capacitate sau număr de călători. `route_type=200` rămâne în datele GTFS și în SQLite, dar este exclus din atlasul feroviar deoarece reprezintă servicii rutiere de înlocuire.

## Conținut

| Cale | Rol |
| --- | --- |
| `data/raw/gtfs/` | snapshotul de intrare, fixat la un commit și verificabil prin SHA-256 |
| `data/derived/gtfs/` | fișierele GTFS necomprimate, generate pentru reutilizare directă |
| `data/derived/gtfs-romania-feroviar.zip` | pachetul GTFS standard |
| `data/derived/romania-rail.sqlite` | tabele relaționale și indici pentru interogări locale |
| `data/derived/stations.geojson` | 1.695 de puncte `Point` cu operatori și număr de opriri |
| `data/derived/atlas/` | datele compactate pentru cele 12 coridoare ale atlasului |
| `data/derived/metadata.json` | statistici și proveniență pentru această versiune |
| `scripts/` | descărcare fixată, construire și validare |
| `qa/` | rapoarte generate de validatoare |
| `examples/queries.sql` | interogări SQLite de pornire |

## Pornire rapidă

Nu este necesară o bibliotecă Python terță.

```bash
make build
make validate
make test
```

Pentru a reîmprospăta intrarea din commitul fixat:

```bash
make refresh
make build
make validate
```

`make refresh` folosește internetul și înlocuiește numai fișierele din `data/raw/gtfs/` atunci când suma verificată corespunde commitului din `scripts/fetch_gtfs.py`. Pentru o versiune nouă trebuie actualizate împreună commitul, sumele, perioada de valabilitate, nota de licență și rapoartele QA.

## Interogare de exemplu

```bash
sqlite3 data/derived/romania-rail.sqlite \
  'SELECT agency_name, COUNT(*) AS trips
     FROM trips
     JOIN routes USING (route_id)
     JOIN agencies USING (agency_id)
    GROUP BY agency_id
    ORDER BY trips DESC;'
```

Pentru alte exemple, vezi [`examples/queries.sql`](examples/queries.sql) și [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md).

## Proveniență și republicare

Snapshotul este generat de converterul open-source [data.gov.ro-gtfs-exporter](https://github.com/vasile/data.gov.ro-gtfs-exporter), la commitul `a8d353dec5e6ac0c82de58c81c3396d7a78c5de3`, din datele publicate de [S.C. Informatică Feroviară S.A. pe data.gov.ro](https://data.gov.ro/organization/9b0bc5fc-2062-4aef-b916-b48b7c459af7?organization=sc-informatica-feroviara-sa). Licențele se aplică pe set și pe operator; nu presupuneți că licența codului se extinde asupra datelor. Citiți [`LICENSES.md`](LICENSES.md) înainte de a încărca un snapshot pe un serviciu public sau de a-l redistribui într-un produs.

Exploratorul editorial bilingv care a stat la baza fuziunii este disponibil la [mariuscomper.uk/gtfs-feroviar](https://mariuscomper.uk/gtfs-feroviar/).

## Pentru mentenanță

Ordinea recomandată este:

1. fixați un singur snapshot GTFS și verificați toate sumele;
2. construiți GTFS, SQLite, GeoJSON și atlasul;
3. rulați toate validatoarele;
4. verificați manual perioada, operatorii și termenii de reutilizare;
5. publicați numai după ce raportul din `qa/report.json` este `pass`.

Detaliile despre modelarea axelor, orele după miezul nopții, coordonate și limitele de interpretare sunt în [`DATA_NOTES.md`](DATA_NOTES.md). Pentru schimbări, consultați [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## Reproducible Romanian passenger-rail archive

This repository combines the reusable data layer from `gtfs-feroviar` with the time–distance atlas from `romania-train-graph`. It publishes the same GTFS snapshot in four practical forms:

- a standard GTFS package for routing tools and research;
- a SQLite database for fast local queries;
- a GeoJSON station layer with operators and scheduled calls;
- a compact corridor atlas for visualisation and programmatic analysis.

It also includes dependency-free build scripts, SHA-256 manifests and validators. The aim is a public, auditable and reusable copy of the annual timetable rather than a presentation page alone.

### Quick start

```bash
make build
make validate
make test
```

The snapshot is a planned annual timetable for 14 December 2025 – 12 December 2026. It is not GTFS-RT and contains no live positions, delays, cancellations, capacity or ridership. Data provenance and mixed per-source licensing are documented in [`LICENSES.md`](LICENSES.md) and [`data/source.json`](data/source.json).

## Citation

If this archive supports published work, please cite [`CITATION.cff`](CITATION.cff), name the upstream converter and retain the publisher/operator attribution required by the source datasets.
