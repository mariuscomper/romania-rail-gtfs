# Contribuție și actualizări

Actualizările de orar trebuie să fie snapshoturi complete, nu editări manuale ale unui singur tabel.

1. Fixați commitul converterului și notați perioada de valabilitate.
2. Actualizați sumele din `scripts/fetch_gtfs.py` și verificați termenii pentru fiecare operator.
3. Rulați `make build`, `make validate` și `make test`.
4. Examinați `qa/report.json`, `data/derived/metadata.json` și diferențele de schemă.
5. Păstrați în `SOURCES.md` orice schimbare de metodă sau limitare.

Nu introduceți date live, date personale, informații comerciale nepublice sau o licență unică pentru toate fișierele fără o bază clară în metadatele sursei.
