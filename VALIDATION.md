# Validatie 0.5.0 — echte BAG en AHN

Uitgevoerd op 3 november 2026 via de lokaal geïnstalleerde QGIS 4.2.3 / Qt6, rechtstreeks vanuit Python. Geen Computer Use gebruikt. De geopende QGIS-sessie is niet opnieuw geladen of via de interface getest. De lokale Techbase-plugin is niet gewijzigd.

## Live geografische gevallen

| Screenshot | RD-extent (xmin, ymin, xmax, ymax) | Gewenst en verkregen |
|---|---|---|
| 1 | 162273, 388284, 162322, 388304 | 4 twee-onder-een-kap; 1 vrijstaand |
| 2 | 162286, 388402, 162326, 388421 | 4 vrijstaand |
| 3 | 162543, 388378, 162601, 388457 | 18 twee-onder-een-kap |

De identificatie berust op de overeenkomst van de volledige contourvorm en relatieve pandposities met de drie screenshots. Geval 3 ligt tussen Florencelaan en Lokert. De screenshots zijn geen bron van synthetische geometrie. De BAG-ID’s hieronder leggen de gematchte gevallen exact vast.

De live runner gebruikt de echte PDOK WFS-provider, de normale buurbuffer en de echte AHN-rasterprovider zonder vervanging van bronfuncties. Geval 3 bevat daarnaast vijf niet-woonpanden; die hebben een lege categorie. Alle 27 woonpanden hebben `DakOnzeker=0`. Dit betekent voldoende bewijs binnen de heuristiek; geen onafhankelijke bouwkundige certificering.

## Metingen en verwerking

- De oude grensmediaan verloor hoofdcontacten als het grootste grensdeel laag garagedak was, en nam lage contacten zonder groot lokaal hoogteverschil juist als hoofddak mee. Daarnaast werden unieke garageparen alsnog gekoppeld.
- Ruimtelijke dakzones binnen elke echte BAG-contour vervangen de enkele representatieve hoogte. De onderste verbindingsdaken van geval 3 liggen rond 19,5 m NAP, met hoofdcontacten rond 22–23 m NAP. Er is geen hard gecodeerde locatie of BAG-ID in de pluginlogica.
- Hoofdcontact vergt vier opeenvolgende circa 0,5 m-profielen met gekoppelde hoge zones. Ten minste 80% bruikbare contactprofielen en 80% lage contacten zijn vereist voor de kwalificatie bijgebouw. Ontbrekende gegevens blijven onzeker.
- Segmentatie verwijdert losse hoge componenten onder 6 m² of 4% van het pandgrid; grote footprint-grids zijn begrensd op circa 4096 cellen. Dit is geen volledige dakvlakreconstructie.
- De uitvoersink wordt voor het laden voltooid. Het echte QGIS `runAndLoadResults`-pad levert voor zowel tijdelijke als GeoPackage-uitvoer één gevulde laag met categorierenderer op `Woningtype`. De test past de styling niet handmatig toe en roept geen opruimfunctie voor dubbele lagen aan.

## Exacte BAG-ID’s

| Geval | BAG-ID | Resultaat | Hoofdcontacten | Lage contacten |
|---|---|---|---:|---:|
| 1 | 0772100000337367 | twee-onder-een-kap | 1 | 0 |
| 1 | 0772100000337366 | twee-onder-een-kap | 1 | 1 |
| 1 | 0772100000337365 | twee-onder-een-kap | 1 | 1 |
| 1 | 0772100000337364 | twee-onder-een-kap | 1 | 1 |
| 1 | 0772100000337363 | vrijstaande woning | 0 | 1 |
| 2 | 0772100000339354 | vrijstaande woning | 0 | 1 |
| 2 | 0772100000339353 | vrijstaande woning | 0 | 2 |
| 2 | 0772100000339352 | vrijstaande woning | 0 | 2 |
| 2 | 0772100000339351 | vrijstaande woning | 0 | 1 |
| 3 | 0772100000338342 | twee-onder-een-kap | 1 | 1 |
| 3 | 0772100000338343 | twee-onder-een-kap | 1 | 1 |
| 3 | 0772100000338344 | twee-onder-een-kap | 1 | 1 |
| 3 | 0772100000338345 | twee-onder-een-kap | 1 | 1 |
| 3 | 0772100000338434 | twee-onder-een-kap | 1 | 1 |
| 3 | 0772100000338435 | twee-onder-een-kap | 1 | 1 |
| 3 | 0772100000338436 | twee-onder-een-kap | 1 | 1 |
| 3 | 0772100000338437 | twee-onder-een-kap | 1 | 1 |
| 3 | 0772100000338438 | twee-onder-een-kap | 1 | 1 |
| 3 | 0772100000338439 | twee-onder-een-kap | 1 | 1 |
| 3 | 0772100000338440 | twee-onder-een-kap | 1 | 2 |
| 3 | 0772100000338441 | twee-onder-een-kap | 1 | 2 |
| 3 | 0772100000338442 | twee-onder-een-kap | 1 | 1 |
| 3 | 0772100000338443 | twee-onder-een-kap | 1 | 2 |
| 3 | 0772100000338444 | twee-onder-een-kap | 1 | 2 |
| 3 | 0772100000338445 | twee-onder-een-kap | 1 | 1 |
| 3 | 0772100000338446 | twee-onder-een-kap | 1 | 1 |
| 3 | 0772100000338447 | twee-onder-een-kap | 1 | 1 |

## Herhalen

Binnen een QGIS-Pythonomgeving, vanuit de repository:

```text
python -m unittest discover -s tests -v
python qgis_tests/smoke.py
python qgis_tests/real_regression.py
python qgis_tests/live_pdok.py <nieuwe-uitvoermap>
```

`real_regression.py` gebruikt originele PDOK-snapshots en controleert hun SHA-256. Alleen netwerktoegang wordt naar die snapshots gerouteerd; geometrie, rasterwaarden, segmentatie, classificatie en Processing worden echt uitgevoerd. De snapshots zijn op deze datum opnieuw gedownload, niet gegenereerd. `live_pdok.py` gebruikt opnieuw de PDOK-services en de normale AHN-cache; deze online test is afhankelijk van servicebeschikbaarheid.

## Grenzen van de validatie

Wel live: alle drie screenshotlocaties, 27 woonpanden, volledige WFS-verwerking op QGIS 4.2.3. Daarnaast herhaalde snapshot-tests met omgekeerde featurevolgorde/contactrichting en twee uitvoerformaten. CI voert dezelfde geografische regressies en integratiecontroles uit voor QGIS 3.34, 3.44.5 en 4.2.0.

Niet gevalideerd: een volledige landelijke run, andere ongeziene geografische woninggevallen, de bediening/herlaadactie in de geopende QGIS-interface, of een vergelijking met constructieve bouwtekeningen/LoD2-dakvlakken van 3DBAG. AHN-ouderdom, bomen, smalle daken en complexe hoofdvolumes blijven mogelijke foutbronnen.

## Bronnen

- BAG: https://service.pdok.nl/kadaster/bag/wfs/v2_0 (GetFeature bag:pand, EPSG:28992, gepagineerd)
- AHN: https://service.pdok.nl/rws/ahn/wcs/v1_0 (`dsm_05m`, WCS 2.0.1, oorspronkelijke GeoTIFFs)
- Ophaling, queryomschrijving en SHA-256: [provenance.json](qgis_tests/data/provenance.json)
- QGIS 4-metadata: https://plugins.qgis.org/docs/migrate-qgis4 (`qgisMaximumVersion=4.99`; alleen metadata aanpassen bewijst geen runtime-compatibiliteit).
