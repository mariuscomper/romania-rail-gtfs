# Note despre date și metodă

## Unitatea de analiză

Unitatea de bază este definiția programată a unei curse (`trip_id`) într-un mers anual. O cursă nu este o călătorie observată și nu reprezintă numărul de trenuri fizice care circulă într-o zi oarecare.

Calendarul se aplică prin `calendar.txt` și `calendar_dates.txt`. Orele GTFS de după `24:00:00` rămân în forma sursă, astfel încât trecerea peste miezul nopții să poată fi reconstituită corect.

## Atlasul de coridoare

Atlasul este construit din succesiunile de stații publicate de trenuri. Pentru fiecare coridor, scriptul caută o rută de referință și construiește o axă printr-un graf al punctelor de oprire. Distanțele sunt sume de distanțe haversine între coordonate, nu kilometraj oficial și nu lungimi exacte ale căii.

Serviciile cu `route_type=200` sunt păstrate în GTFS și SQLite pentru trasabilitate, dar excluse din graficul feroviar. Un punct de timp–poziție din atlas este o interpolare a orarului, nu dovada unei poziții reale.

## Domeniu și limite

Snapshotul acoperă șapte operatori de călători, 1.695 de stații și perioada 14 decembrie 2025 – 12 decembrie 2026. Nu include marfă, trenuri tehnice, restricții temporare, întârzieri operative, anulări, poziții GPS, ocupare sau cerere.

Coordonatele provin din GTFS. Validatoarele verifică limitele geografice largi pentru România, dar acest lucru nu confirmă poziția exactă a peronului sau a liniei.

## Reproducibilitate

Fișierele de intrare sunt fixate la commitul `a8d353dec5e6ac0c82de58c81c3396d7a78c5de3` al converterului upstream. `scripts/fetch_gtfs.py` și `MANIFEST.sha256` fac posibilă verificarea identității datelor. Orice actualizare trebuie să genereze din nou toate artefactele și rapoartele.

## Data and method in English

The base unit is a scheduled `trip_id` from an annual timetable. It is not an observed journey or a count of physical trains on a particular day. The atlas reconstructs corridor axes from published stop sequences and uses haversine distances between GTFS coordinates; it does not claim official railway kilometreage. Replacement-bus services (`route_type=200`) remain in GTFS and SQLite but are excluded from the rail graph.

The snapshot covers seven passenger operators, 1,695 stops and the 14 December 2025 – 12 December 2026 timetable period. It excludes freight, engineering movements, temporary restrictions, operational delays, cancellations, live GPS, capacity and ridership. See `data/source.json` and `LICENSES.md` for provenance and redistribution conditions.
