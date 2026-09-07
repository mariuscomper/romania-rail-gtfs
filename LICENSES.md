# Proveniență, atribuiri și licențe

## Datele mersului de tren

**Publicator:** S.C. Informatică Feroviară S.A., prin data.gov.ro<br>
**Sursă organizațională:** <https://data.gov.ro/organization/9b0bc5fc-2062-4aef-b916-b48b7c459af7?organization=sc-informatica-feroviara-sa><br>
**Descriere:** mersul anual planificat al trenurilor de călători din România

Licența se verifică pe fiecare set de operator. Pentru snapshotul folosit aici, metadatele consultate listează OGL-ROU-1.0 pentru seturile CFR Călători, Regio Călători, InterRegional și Softrans și CC BY 4.0 pentru Ferotrafic–TFI. Păstrați atribuirea către publicator, operator și converter și aplicați condiția cea mai restrictivă relevantă.

## Conversia GTFS

**Proiect:** Romanian Railways GTFS exporter<br>
**Autor/repository:** Vasile Coțovanu, [`vasile/data.gov.ro-gtfs-exporter`](https://github.com/vasile/data.gov.ro-gtfs-exporter)<br>
**Snapshot:** `a8d353dec5e6ac0c82de58c81c3396d7a78c5de3`<br>
**Licența codului converterului:** MIT, conform proiectului upstream

Fișierele GTFS distribuite aici sunt derivate din datele portalului și păstrează obligațiile de atribuire ale sursei. Acest depozit nu este afiliat cu și nu este validat de CFR Călători, Informatică Feroviară, AFER, ARF sau operatorii reprezentați.

## Codul acestui depozit

Scripturile de construire, validare și exemplele originale sunt oferite sub [`LICENSE-CODE`](LICENSE-CODE). Această licență nu extinde și nu modifică termenii fișierelor de date, ai converterului upstream sau ai surselor istorice.

## Regula de republicare

Înainte de publicarea unui snapshot nou, verificați pagina de metadate pentru fiecare operator, actualizați `data/source.json`, păstrați atribuirea vizibilă și rulați `make validate`. Dacă termenii s-au schimbat sau sunt ambigui, păstrați datele doar local până la clarificare.
