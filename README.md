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
2. De plugin leest alleen BAG-panden in het gebied plus een smalle buurbuffer, en herkent appartementen via woonfunctie + aantal VBO's.
3. Een lokale ruimtelijke index bepaalt welke pandcontouren werkelijk aangrenzen (standaard maximaal 0,20 m afstand).
4. **Uitsluitend voor aangrenzende woonpanden** vraagt de plugin beperkte AHN DSM-rastertegels op. Van gedeelde gevels worden hoogten kort binnen beide panden vergeleken. Hiermee kan een schijnbaar aansluitende lage carport / aanbouw worden onderscheiden van waarschijnlijk doorlopende dakvlakken.
5. DSM-GeoTIFF-tegels worden hergebruikt uit een permanente lokale cache onder de gebruikersmap. Zonder netwerk kan **Alleen lokaal opgeslagen AHN gebruiken** aan. Als hoogten ontbreken of te twijfelachtig zijn, blijven BAG-pandrelaties leidend en wordt een controle-indicator gezet.
6. Het resultaat kan als GeoPackage worden opgeslagen en op BAG-identificatie of locatie gekoppeld aan Techbase LS Netontwerp. De plugin **wijzigt geen ontwerpstroomregels**.

## Installatie

Download de **plugin-ZIP vanuit [Releases](https://github.com/LukaStuurman/Woningtype-3d-bagloos/releases)** (niet de standaard GitHub-broncode-ZIP). De plugin-ZIP bevat **uitsluitend de bovenste map** `woningtype_3d_bagloos/` (die `metadata.txt` en `__init__.py` bevat). Ga in QGIS naar **Plugins → Plugins beheren en installeren → Installeren vanuit ZIP**. Herstart QGIS, en gebruik de werkbalkknop of **Processing → Woningtype 3D-bagloos → Bepaal woningtypen met BAG en lokaal AHN**.

Doelplatform: QGIS 3.34+ en QGIS 4 (PyQGIS / GDAL, zonder externe Python-pakketten). Er is een pure-Python eenheidstest: `python -m unittest discover -s tests -v`.

## Bronnen

- BAG WFS: <https://service.pdok.nl/kadaster/bag/wfs/v2_0>
- AHN WCS: <https://service.pdok.nl/rws/ahn/wcs/v1_0> — `dsm_05m`, OGC WCS 2.0.1.
- 3DBAG wordt **niet** benaderd. Dit is een nieuwe, zelfstandige benadering; er wordt geen code uit de Techbase-plugin of 3DBAG-implementatie gekopieerd.

## Aandachtspunten en betrouwbaarheid

**Dit is een heuristische woningtypebepaling, geen vervanging van een nauwkeurige 3D-reconstructie.** De AHN-DSM toont oppervlakken, niet de constructieve woningscheidingswand. Een lage verbindingsbouw, bomen, kappen met afwijkende vorm, slechte AHN-dekking, perceelverschuivingen of recente nieuwbouw kunnen een onjuiste of onzekere classificatie opleveren. Bij geen AHN-bewijs wordt een woning **niet** als zeker losstaand bestempeld. Controleer altijd de twijfelgevallen bij toepassing in netwerkontwerpen.

De uitvoer bewaart het **BAG-bouwjaar**. Een woningtype zegt niets over de aanwezigheid van een warmtepomp of tapwaterbuffer; zulke ontwerpaannames worden niet uit AHN afgeleid.

## Licentie

De repository bevat zelfgeschreven pluginbroncode. Voeg desgewenst een expliciete open-sourcelicentie toe voordat je hergebruik door derden wilt toestaan.
