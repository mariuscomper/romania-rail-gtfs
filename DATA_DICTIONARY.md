# Dicționar de date

## GTFS

Intrarea și pachetul distribuit păstrează coloanele sursei:

- `agency.txt`: operatori (`agency_id`, nume, URL, fus orar);
- `routes.txt`: relația operator–rută și tipul GTFS (`route_type`);
- `trips.txt`: definiții de curse și servicii calendaristice;
- `stops.txt`: stații/puncte de oprire și coordonate WGS84;
- `stop_times.txt`: sosiri, plecări și ordinea opririlor;
- `calendar.txt`: tiparul săptămânal și intervalul de bază;
- `calendar_dates.txt`: excepții de adăugare sau eliminare pentru o dată.

Cheile primare sunt `agency_id`, `route_id`, `trip_id`, `stop_id` și `service_id`. Validatoarele verifică legăturile externe și ordinea temporală.

## SQLite

SQLite reproduce relațiile GTFS în tabelele `agencies`, `routes`, `trips`, `stops`, `stop_times`, `calendar` și `calendar_dates`. Sunt incluse indici pentru `stop_times.stop_id`, `stop_times.trip_id`, `trips.route_id`, `routes.agency_id` și `calendar_dates.service_id`.

## GeoJSON

`data/derived/stations.geojson` este un `FeatureCollection` cu câte un `Point` pentru fiecare `stop_id`. Coordonatele sunt în ordinea GeoJSON `[lon, lat]`. Proprietățile sunt:

- `id`: `stop_id` din GTFS;
- `name`: numele stației;
- `calls`: numărul de rânduri din `stop_times` pentru stație;
- `operators`: numele operatorilor care au cel puțin o oprire acolo;
- `operator_count`: lungimea listei `operators`.

## Atlas

`data/derived/atlas/atlas.json` este un artefact pentru cele 12 coridoare configurate în `config/corridors.json`. Conține axe ordonate, servicii, calendare, operatori și puncte de timp. `atlas.js` este aceeași structură învelită pentru consum local în browser.

## English summary

The SQLite schema mirrors the seven GTFS tables and adds indexes for the common station, trip, route and operator joins. GeoJSON uses WGS84 coordinates in `[longitude, latitude]` order. The atlas is a derived visualisation bundle and must not be mistaken for a second authoritative timetable.
