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

## Uitbreiding 0.6.0 — bijna even hoge carports

Rechtstreeks live uitgevoerd op QGIS 4.2.3, zonder Computer Use. Het nieuwe screenshot is gematcht op het werkelijke BAG-blok aan Esperenkamp/Florencelaan. BGT-pandcontouren zijn onderzocht maar geven hier geen aanvullende scheiding; deze zijn daarom geen afhankelijkheid van de plugin geworden.

Het woon- en carportdak ligt grotendeels rond 19,5 m NAP; kleinere substantiële dakdelen liggen rond 20,0 m NAP. De eerdere 1,75 m-zonegrens kan dit onderscheid niet maken. De aanvullende analyse vereist daarom tegelijk een sterk ingesneden contour, een kleine robuuste hoogtecontrastzone (0,3–1,0 m), een gebouwhoogte van 1,8–4,5 m boven gemeten DTM-terrein en afzonderlijke dakdelen van minstens 12 m² nabij de geregistreerde VBO-punten. De BAG-vorm beslaat hierbij maximaal 82% van de convexe omhulling. Bij gebrek aan deze bewijzen blijft de normale beoordeling actief.

DTM bevat onder gebouwen vaak geen waarden. De hoogte boven maaiveld wordt daarom bepaald met echte DTM-metingen buiten de BAG-contour, ook in binnenplaatsen; er worden geen terreinhoogten verzonnen of onder het dak ingevuld.

**Op expliciete aanwijzing blijft het BAG-pand met twee VBO’s appartement.** De aanvullende dakcontrole mag zijn carportcontacten wel onderscheiden zodat de naburige woningen niet als rijwoning worden meegeteld. Het aantal VBO’s en de BAG-contour worden niet herschreven.

| Groep | Werkelijke test | Uitkomst |
|---|---|---|
| Nieuw blok | 13 BAG-panden, 14 VBO’s | 12 vrijstaand; 1 appartement met 2 VBO’s |
| Rijwoningcontrole | 10 echte nabije BAG-woonpanden | 2 hoekwoningen; 8 tussenwoningen |
| Eerdere screenshots | 27 BAG-woonpanden | Alle 27 behouden de gevraagde indeling |

De volledige live Processing-route slaagt voor 50/50 doelpanden. Iedere run maakt één automatisch gecategoriseerde resultaatlaag. Het live-gebied bevat daarnaast niet-woonpanden, die de lege categorie houden.

De tien controlewoningen vormen een echte doorlopende rij met hoofdcontacten, met BAG-ID’s 0772100000339629 tot en met 0772100000339638. Dit zijn geen synthetische rechthoeken.

### Exacte nieuwe doelpanden

| BAG-ID | Verwachte en gemeten categorie | Aantal VBO |
|---|---|---:|
| 0772100000338954 | vrijstaande woning | 1 |
| 0772100000338955 | appartement | 2 |
| 0772100000338956 | vrijstaande woning | 1 |
| 0772100000338958 | vrijstaande woning | 1 |
| 0772100000338960 | vrijstaande woning | 1 |
| 0772100000338961 | vrijstaande woning | 1 |
| 0772100000338962 | vrijstaande woning | 1 |
| 0772100000339048 | vrijstaande woning | 1 |
| 0772100000339049 | vrijstaande woning | 1 |
| 0772100000339051 | vrijstaande woning | 1 |
| 0772100000339053 | vrijstaande woning | 1 |
| 0772100000339054 | vrijstaande woning | 1 |
| 0772100000339056 | vrijstaande woning | 1 |

### Regressietest

`python qgis_tests/flat_regression.py` controleert de echte snapshots, SHA-256, gewijzigde featurevolgorde/contactrichting, herstel van dakverfijning na cache-evictie, terugval bij ontbrekend VBO-bewijs, het behouden BAG-aantal VBO en één automatisch gestylede geheugen-/GeoPackage-laag. De gewone rij en de appartementcategorie zijn expliciete controles.

Bronnen: BAG WFS, BAG OGC API verblijfsobject, AHN WCS `dsm_05m` én `dtm_05m`. Zie [data_flat/provenance.json](qgis_tests/data_flat/provenance.json) voor bron-URL’s, opnamedatum van de snapshot en SHA-256. De opnamedatum van de snapshot is niet de vliegdatum van AHN.

Niet gevalideerd: alle denkbare vlakke rijwoning- en bungalowvarianten, heel Nederland, of de geopende QGIS-interface. Een nauwe aansluiting met dezelfde hoogte kan ook met deze gegevens onzeker blijven. De straatfoto ondersteunt de gewenste interpretatie van dit blok; de plugin classificeert geen straatfoto’s en gebruikt geen plaats- of BAG-ID-specifieke uitzondering. Techbase blijft ongemoeid.

## Uitbreiding 0.7.0 — De Koppele, Goudrenetstraat en Sterappelstraat

De zes nieuwe afbeeldingen zijn gekoppeld aan drie echte BAG-locaties. De straatfoto’s en de expliciete aanwijzing van de gebruiker vormen de verwachte interpretatie; de uitvoer wordt berekend uit echte BAG-contouren en AHN-metingen. Er zijn geen plaatsafhankelijke uitzonderingen toegevoegd aan de plugin.

### Oorzaken en wijzigingen

- **De Koppele:** aan de scheiding meten we op circa 0,5 m diepte ongeveer 20–21 m NAP. Het dak stijgt vervolgens binnen 3 m gelijkmatig naar circa 25 m NAP aan beide kanten. De vorige hoogtezone zag de lage aansluiting als bijgebouw. De aanvullende profieltest herkent de doorgaande steile hoofdkappen.
- **Goudrenetstraat:** de garageverbinding piekt lokaal rond 23,6 m NAP, terwijl de hoofdvolumes rond 24,8–25,7 m NAP komen. De vorige ruime hoofdzone liet dat garagedak meetellen. De aangescherpte hoofdzone sluit de verbinding uit; een apart profielpad bewaart echte lage hoofdcontacten.
- **Sterappelstraat:** bij een laag garagecontact ontbraken enkele cellen in het footprintgrid, terwijl op die contactpunten wel directe lage DSM-metingen beschikbaar waren. Die metingen tellen nu als laag bewijs. Werkelijk ontbrekende hoogten blijven onzeker.

De alternatieve profieltest vraagt vier opeenvolgende contactprofielen. Aan beide zijden moet het dak vanaf de scheiding direct stijgen, zonder plateau of grote sprong, en op 2–3,5 m diepte een substantiële hoofddakzone bereiken. Hierdoor wordt niet alleen de hoogte maar ook de vorm van de verbinding beoordeeld. Voor normale hoge dakzones is de onderste marge nu 0,5 m onder het robuuste 80e percentiel; voor vlakke daken en de aanvullende laagbouwanalyse blijven hun aparte regels gelden.

### Nieuwe geometrische regressies

| Locatie | Werkelijke panden in nieuwe fixture | Uitkomst |
|---|---:|---|
| De Koppele | 6 | 3 juiste twee-onder-een-kapparen |
| Goudrenetstraat | 22 | 4 twee-onder-een-kapparen plus echte rijen van 8 en 6 woningen |
| Sterappelstraat | 22 | 4 twee-onder-een-kapparen plus echte rijen van 8 en 6 woningen |

De nieuwe fixture omvat 50 echte panden. Samen met de eerdere 27 en 23 panden zijn 100 unieke doelpanden rechtstreeks via de live PDOK WFS-provider met echte AHN-data doorgerekend op QGIS 4.2.3. Alle 100 voldoen aan de vastgelegde verwachte categorie. Ook de 38 rijwoningcontroles binnen deze verzameling blijven hoek-/tussenwoning. Het pand met twee VBO’s blijft appartement conform de gebruikersinstructie.

### De twaalf nieuw aangewezen woningen

| Locatie | BAG-ID | Juiste partner BAG-ID |
|---|---|---|
| koppele | 0772100000336194 | 0772100000336193 |
| koppele | 0772100000336193 | 0772100000336194 |
| koppele | 0772100000336192 | 0772100000336191 |
| koppele | 0772100000336191 | 0772100000336192 |
| koppele | 0772100000336190 | 0772100000336189 |
| koppele | 0772100000336189 | 0772100000336190 |
| goudrenet | 0772100000331672 | 0772100000331671 |
| goudrenet | 0772100000331671 | 0772100000331672 |
| sterappel | 0772100000330694 | 0772100000330693 |
| sterappel | 0772100000330693 | 0772100000330694 |
| sterappel | 0772100000330692 | 0772100000330691 |
| sterappel | 0772100000330691 | 0772100000330692 |

Nieuwe originele BAG- en DSM-snapshots, bron-URL’s, querybbox en SHA-256: [data_pairs/provenance.json](qgis_tests/data_pairs/provenance.json). De 14 DSM-tegels zijn opnieuw via WCS gedownload.

`python qgis_tests/pair_regression.py` controleert alle 50 nieuwe panden, expliciet de juiste woningpartners, omgekeerde contactrichting/featurevolgorde en één automatisch gestylede geheugen- en GeoPackage-laag. De eerdere geografische suites blijven verplicht in dezelfde CI-matrix voor QGIS 3.34, 3.44.5 en 4.2.0.

De live runner is uitgebreid met de drie nieuwe gebieden: `python qgis_tests/live_pdok.py <nieuwe-uitvoermap>`. Er is geen Computer Use gebruikt. De open QGIS-interface en heel Nederland zijn niet gevalideerd. Bij andere dakvormen, vegetatie of onvoldoende AHN-dekking blijft de indeling indicatief; 100 juiste gevallen zijn geen garantie voor elk pand in Nederland. De originele Techbase-plugin is ongemoeid gebleven.

## Uitbreiding 0.8.0 — brede lage woondaken aan Zoekant

De gebruiker heeft de interpretatie van de pijlen expliciet bevestigd: Zoekant 8+10 en 14+16 vormen twee-onder-een-kapparen; 12 en 18 zijn vrijstaand. De adressen zijn gekoppeld aan echte BAG-panden en VBO-punten, niet afgeleid uit een getekende testgeometrie.

### Gemeten dakpatroon

Het brede woondak ligt doorgaans op circa 19,5–19,7 m NAP. De verbindende garages liggen rond 18,8–19,0 m NAP. De eerdere laagbouwregel vereiste een verschil tussen het 90e percentiel en de mediaan; dat werkt voor een klein verhoogd dakdeel, maar mist een hoger woondak dat de meerderheid van de footprint beslaat.

De aanvullende route wordt nu ook onderzocht als de mediaan minstens 0,3 m en maximaal 1,0 m boven het lagere robuuste niveau ligt, terwijl de totale robuuste spreiding hoogstens 1,5 m is. De overige contour- en maaiveldvoorwaarden blijven van kracht. Voor deze brede-dakvariant moet bovendien:

- de mediaan van echte DSM-samples binnen 2 m van elk woningpunt binnen 0,2 m overeenkomen met de brede dakhoogte, met minstens twaalf bruikbare lokale metingen;
- ieder woningpunt een eigen substantiële samenhangende dakzone ondersteunen;
- de gezamenlijke ondersteunde dakzone minstens 40% van de bruikbare footprint-samples beslaan.

De scheiding van de brede dakzone ligt 0,2 m onder de robuuste mediaan. Dat is geen zelfstandige algemene woningtypegrens: alle bovenstaande bewijzen blijven nodig. Bij de bestaande variant met kleinere verhoogde dakdelen blijft de eerder vastgelegde grens actief.

### Exacte nieuwe doelpanden

| Adres | BAG-ID | Verwachte en verkregen indeling |
|---|---|---|
| Zoekant 8 | 0772100000335658 | Twee-onder-een-kap met 10 |
| Zoekant 10 | 0772100000335564 | Twee-onder-een-kap met 8 |
| Zoekant 12 | 0772100000950142 | Vrijstaand |
| Zoekant 14 | 0772100000335043 | Twee-onder-een-kap met 16 |
| Zoekant 16 | 0772100000900420 | Twee-onder-een-kap met 14 |
| Zoekant 18 | 0772100000335042 | Vrijstaand |

De nieuwe fixture bevat twintig echte panden: de zes doelpanden en veertien omliggende controlepanden. Samen met de eerdere honderd zijn 120 unieke panden opnieuw via de volledige live PDOK WFS-route en echte AHN-data beoordeeld op de lokaal geïnstalleerde QGIS 4.2.3. Alle categorieën en woningpartners voldoen aan de vastgelegde verwachtingen. De 38 eerdere rijwoningcontroles blijven hoek-/tussenwoning; de behouden appartementcategorie verandert niet.

### Reproduceerbaarheid en terugval

`python qgis_tests/low_regression.py` controleert originele BAG/VBO/DSM/DTM-snapshots, SHA-256, juiste partners, beide contactrichtingen, omgekeerde featurevolgorde, herstel na cache-evictie, terugval bij ontbrekend VBO-bewijs en één automatisch gestylede geheugen-/GeoPackage-laag. De twaalf DSM-/DTM-tegels zijn opnieuw gedownload. Bronnen en checksums staan in [data_low/provenance.json](qgis_tests/data_low/provenance.json).

Bij een geschikt vlak dakpatroon zonder passend aanvullend bewijs blijft de bestaande berekening actief en vermeldt `Controle` dat controle nodig is. `DakOnzeker` blijft het aantal onzekere dakcontacten tellen; het is geen volledige zekerheidsscore voor de woningtype-indeling.

De live runner verwerkt nu ook Zoekant: `python qgis_tests/live_pdok.py <nieuwe-uitvoermap>`. Geen Computer Use of wijziging van de geopende QGIS-sessie. Geen wijziging aan Techbase. De volledige landelijke verwerking en andere, nog niet opgenomen lage vlakke rijwoningtypen zijn niet live gevalideerd; de 120 controlepanden zijn geen garantie voor alle woningvormen in Nederland.
