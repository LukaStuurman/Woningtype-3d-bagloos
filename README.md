# Woningtype 3D-bagloos — QGIS-plugin

Bepaal woningtypen zonder afhankelijkheid van de 3DBAG-server. Deze zelfstandige QGIS Processing-plugin haalt de **BAG-pandgegevens** op via PDOK en maakt waar nodig zelf een **lichte dakcontactcontrole** uit het AHN-DSM (0,5 m resolutie). Er wordt **geen compleet 3D-gebouwmodel** aangemaakt.

## Onderzoeksgebied: kaartvenster of heel Nederland

Gebruik de plugin via de werkbalk en kies onder **Welk gebied verwerken?**:

- **Huidig QGIS-kaartvenster**: het gebied dat zichtbaar is op het moment van starten. Je kunt het kaartvenster in het dialoogvenster ook handmatig als extent aanpassen.
- **Zelf gekozen gebied**: geef een ruimtelijke extent op.
- **Heel Nederland**: de vastgelegde landelijke RD New-boundingbox wordt in maximaal 10 x 10 km BAG-tegels verwerkt. Extreem dichte tegels worden automatisch verder verdeeld; de plugin bewaart slechts één tegel tegelijk in het geheugen. De buurbuffer is 25 m, zodat woningen op tegelgrenzen met hun buren worden beoordeeld.

Bij **Heel Nederland** wordt een niet-ingestelde of tijdelijke uitvoer **automatisch een permanent GeoPackage** onder je gebruikersgegevensmap (`Woningtype3DBagloos/resultaten/`). Je kunt zelf een andere `.gpkg` als uitvoer kiezen, bijvoorbeeld op een snelle SSD. Een geheugenlaag is voor landelijke uitvoering niet geschikt.

**Landelijk standaard: BAG zonder AHN.** BAG-contouren worden gebruikt voor de eerste landelijke typebepaling. Wil je ook het AHN-DSM voor heel Nederland analyseren, vink dan apart **HEEL NEDERLAND: AHN-hoogtecontrole expliciet inschakelen** aan. Dat kan zeer veel WCS-verzoeken en schijfruimte vereisen. Voor betrouwbare dakcontrole is het doorgaans praktischer om eerst landelijk BAG te verwerken en vervolgens relevante deelgebieden met AHN te controleren.

Tijdens landelijke uitvoering verschijnen voortgang, tegelaantallen en geschreven panden in het Processing-log. Je kunt annuleren; een eventueel gedeeltelijk opgeslagen GeoPackage is **niet compleet** en mag niet als landelijke dataset worden gebruikt.

> Let op: landelijke verwerking is ontworpen om geheugenarm te verlopen, maar kan afhankelijk van BAG/WFS-beschikbaarheid, AHN-service en netwerkbelasting lang duren. Een volledige live landelijke run is nog niet gevalideerd. Er is wel een QGIS-test die tegels op de grens zonder dubbele BAG-ID's verwerkt.

## Resultaten

De uitvoer is een polygonenlaag met de BAG-pandcontour, BAG-identificatie, bouwjaar, gebruiksdoel, aantal verblijfsobjecten, indicatief woningtype, AHN-controlebron, aantal onderzochte buren, aantal aangetoonde dakverbindingen, aantal onzekerheden en een controle-indicator.

Gebruikte categorieën (compatibel met Techbase LS Netontwerp): `vrijstaande woning`, `twee-onder-een-kap`, `hoekwoning`, `tussenwoning/geschakeld`, `appartement`. Niet-woonpanden krijgen een lege woningtypewaarde.

## Werking

1. Start in QGIS de knop **Woningtype 3D-bagloos**. Kies het huidige kaartvenster, een eigen gebied of heel Nederland.
2. De plugin leest BAG-panden in het gebied plus een smalle buurbuffer, en herkent appartementen via woonfunctie + aantal VBO's. Afzonderlijke garage- of bergingpanden zonder woonfunctie tellen **niet** als buurwoning, ook als ze nul verblijfsobjecten bevatten.
3. Een lokale ruimtelijke index bepaalt welke pandcontouren werkelijk aangrenzen (standaard maximaal 0,20 m afstand).
4. **Uitsluitend voor aangrenzende woonpanden** vraagt de plugin AHN DSM-rastertegels op. Een ruimtelijk grid van 0,5 m binnen het hele BAG-pand wordt verdeeld in samenhangende hogere dakzones en lagere verbindingsdaken. Kleine losse hoge pixels worden uitgesloten. Voor grote contouren wordt de gridafstand begrensd vergroot. Langs de volledige gedeelde grens worden gekoppelde profielen om de circa 0,5 m beoordeeld. Een aantoonbaar hoofdcontact blijft behouden, ook als het grootste deel van die grens garage is. Lage garagecontacten vormen nooit zelfstandig een twee-onder-een-kappaar. Alleen puntcontacten tussen panden tellen niet mee.
5. DSM-GeoTIFF-tegels worden hergebruikt uit een permanente lokale cache onder de gebruikersmap. Zonder netwerk kan **Alleen lokaal opgeslagen AHN gebruiken** aan. Als hoogten ontbreken of te twijfelachtig zijn, blijven BAG-pandrelaties leidend en wordt een controle-indicator gezet.
6. Het resultaat kan als GeoPackage worden opgeslagen en op BAG-identificatie of locatie gekoppeld aan Techbase LS Netontwerp. De plugin **wijzigt geen ontwerpstroomregels**.

## Uitvoerlaag en automatische kleuren (v0.5.0)

De verwerking maakt één Processing-resultaatlaag met veld `Woningtype` aan. De sink wordt voltooid voordat QGIS de enige uitvoerlaag laadt; er is geen achteraf-opruimactie die projectlagen verwijdert. Bij het inladen van de resultaatlaag krijgt deze automatisch een **gecategoriseerde symbologie op `Woningtype`**, met eigen kleuren voor vrijstaand, twee-onder-een-kap, hoekwoning, tussenwoning/geschakeld en appartement. Panden zonder woonfunctie zijn lichtgrijs.

Deze styling gebeurt via QGIS' Processing-postprocessor: tijdens berekening wordt géén tweede kaartlaag aangemaakt. De indeling blijft een indicatieve AHN-heuristiek; garages zitten vaak **binnen dezelfde BAG-pandcontour** als het hoofdgebouw. Daarom vergelijkt de nieuwe dakcontrole de dakhoogtes bij elke grens met de hogere dakzone van het gehele BAG-pand. **BAG-only** kan dit onderscheid niet maken; hiervoor moet de AHN-modus actief zijn en hoogtegegevens beschikbaar zijn.

## Installatie

Download de **plugin-ZIP vanuit [Releases](https://github.com/LukaStuurman/Woningtype-3d-bagloos/releases)** (niet de standaard GitHub-broncode-ZIP). De plugin-ZIP bevat **uitsluitend de bovenste map** `woningtype_3d_bagloos/` (die `metadata.txt` en `__init__.py` bevat). Ga in QGIS naar **Plugins → Plugins beheren en installeren → Installeren vanuit ZIP**. Herstart QGIS, en gebruik de werkbalkknop of **Processing → Woningtype 3D-bagloos → Bepaal woningtypen met BAG en lokaal AHN**.

Doelplatform: QGIS 3.34+ en QGIS 4 (PyQGIS / GDAL, zonder externe Python-pakketten). Er is een pure-Python eenheidstest: `python -m unittest discover -s tests -v`.

## Bronnen

- BAG WFS: <https://service.pdok.nl/kadaster/bag/wfs/v2_0>
- AHN WCS: <https://service.pdok.nl/rws/ahn/wcs/v1_0> — `dsm_05m`, OGC WCS 2.0.1.
- 3DBAG wordt **niet** benaderd. Dit is een nieuwe, zelfstandige benadering; er wordt geen code uit de Techbase-plugin of 3DBAG-implementatie gekopieerd.

## Lage aansluitingen tussen steile kappen en hogere garages (0.7.0)

De dakcontrole volgt nu ook een profiel vanaf de woningscheiding naar binnen. Twee steile hoofdkappen kunnen laag tegen elkaar aansluiten: een onmiddellijk en geleidelijk stijgend profiel naar beide hoofddakzones bewijst dan een hoofdcontact. Een lager garagevlak met pas verderop een stap naar het hoofddak voldoet daar niet aan. De hoge dakzones zijn aangescherpt zodat een hoger garagedak niet automatisch hoofdvolume wordt. Direct gemeten lage rasterwaarden blijven bruikbaar als de dichtstbijzijnde cel van het footprintgrid ontbreekt.

Opnieuw live gevalideerd op **100 echte BAG-panden**, waaronder alle twaalf nieuw aangewezen woningen aan De Koppele, Goudrenetstraat en Sterappelstraat. De zes woningen aan De Koppele en de twee respectievelijk vier omcirkelde woningen zijn nu twee-onder-een-kap. Ook de concrete paarvorming wordt getest. De nabije echte rijwoningen, de eerdere dakgevallen en de behouden appartementcategorie blijven correct. Zie `qgis_tests/pair_regression.py` en [VALIDATION.md](VALIDATION.md).

## Bijna even hoge platte daken en carports (0.6.0)

Bij een specifiek laagbouwpatroon combineert de plugin nu de kleine dakstappen in AHN DSM met BAG-verblijfsobjectpunten, hoogte boven AHN DTM en een duidelijk ingesneden pandvorm. Alleen als al deze bewijzen samenpassen, worden de afzonderlijke dakdelen gebruikt voor de contactcontrole. De nieuwe regel wordt niet toegepast op iedere vlakke kap of iedere rijwoning. Het extra veld `Woonbewijs` maakt deze indicatieve beoordeling zichtbaar. Zonder voldoende bewijs blijft de bestaande analyse actief.

**De appartementregel blijft ongewijzigd:** meer dan één verblijfsobject in een woonpand blijft `appartement`, ook als het registerfeit vermoedelijk niet de werkelijke woningsplitsing beschrijft. De plugin corrigeert de BAG niet en maakt geen verzonnen woninggrenzen.

Live getest op het blok aan Esperenkamp/Florencelaan uit het vierde screenshot: twaalf panden vrijstaand en één pand met twee VBO's als appartement. Een nabije echte rij van tien woningen blijft twee hoekwoningen en acht tussenwoningen. De eerdere 27 screenshotpanden blijven correct. De extra 23 echte BAG-panden, VBO-punten, DSM- en DTM-tegels en checksums staan in `qgis_tests/data_flat`, met tests in `qgis_tests/flat_regression.py`.

Deze aanvullende regel is indicatief. Ook de controles met rijwoningen bewijzen niet dat iedere andere laagbouwvariant in Nederland correct wordt herkend. Zie de grenzen in [VALIDATION.md](VALIDATION.md).

## Gevalideerd met echte BAG en AHN (0.5.0)

De drie aangeleverde screenshots zijn gematcht op de werkelijke BAG-contouren in Eindhoven. Op 3 november 2026 zijn BAG WFS en twaalf originele AHN DSM-tegels opnieuw opgehaald. De volledige Processing-verwerking via live PDOK WFS geeft voor alle 27 betrokken woningen de gevraagde indeling: geval 1 vier twee-onder-een-kap en één vrijstaand; geval 2 vier vrijstaand; geval 3 achttien twee-onder-een-kap. Het betreft echte gemeten hoogten, geen gesimuleerde rasters.

Zie [VALIDATION.md](VALIDATION.md) voor BAG-ID's, bronnen, begrenzingen, beperkingen en reproduceerbare tests. De oorspronkelijke BAG/GeoTIFF-snapshots met SHA-256 staan onder `qgis_tests/data`. CI controleert deze echte gevallen inclusief omgekeerde featurevolgorde en contactrichting, geheugen- en GeoPackage-uitvoer, en precies één automatisch gestylede resultaatlaag. Publicatie wacht op de volledige testmatrix van QGIS 3.34, 3.44.5 en 4.2.0.

De nieuwe dakzones zijn een rasterbenadering, geen LoD2-dakvlakken of constructieve woningscheidingsanalyse. Er is geen 3DBAG-server of code uit de Techbase-plugin gebruikt. De Techbase-plugin wordt niet gewijzigd.

## Aandachtspunten en betrouwbaarheid

**Dit is een heuristische woningtypebepaling, geen vervanging van een nauwkeurige 3D-reconstructie.** De AHN-DSM toont oppervlakken, niet de constructieve woningscheidingswand. Een lage verbindingsbouw, bomen, kappen met afwijkende vorm, slechte AHN-dekking, perceelverschuivingen of recente nieuwbouw kunnen een onjuiste of onzekere classificatie opleveren. Bij geen AHN-bewijs wordt een woning **niet** als zeker losstaand bestempeld. Controleer altijd de twijfelgevallen bij toepassing in netwerkontwerpen.

De uitvoer bewaart het **BAG-bouwjaar**. Een woningtype zegt niets over de aanwezigheid van een warmtepomp of tapwaterbuffer; zulke ontwerpaannames worden niet uit AHN afgeleid.

## Licentie

De repository bevat zelfgeschreven pluginbroncode. Voeg desgewenst een expliciete open-sourcelicentie toe voordat je hergebruik door derden wilt toestaan.
