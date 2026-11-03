import json,os,sys
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
OUT=Path(sys.argv[1] if len(sys.argv)>1 else 'live-pdok-results').resolve();OUT.mkdir(parents=True,exist_ok=True)
from qgis.core import *
from qgis.PyQt.QtCore import QSize
app=QgsApplication([],False);app.initQgis();sys.path.append(str(Path(QgsApplication.pkgDataPath())/'python'/'plugins'))
from processing.core.Processing import Processing
Processing.initialize()
import processing
from woningtype_3d_bagloos.plugin import WoningtypeBagloosProvider
provider=WoningtypeBagloosProvider();QgsApplication.processingRegistry().addProvider(provider)
expected=json.loads((root/'qgis_tests/data/expected.json').read_text())
regions={'case1':(162273,388284,162322,388304),'case2':(162286,388402,162326,388421),'case3':(162543,388378,162601,388457)}
results={}
for case,bounds in regions.items():
 project=QgsProject.instance();before=set(project.mapLayers());context=QgsProcessingContext();context.setProject(project)
 feedback=QgsProcessingFeedback()
 feedback.progressChanged.connect(lambda p:None)
 output=OUT/(case+'.gpkg')
 processing.runAndLoadResults('woningtypebagloos:bepaal_woningtypen',{'AREA_MODE':1,'EXTENT':QgsRectangle(*bounds),'MODE':0,'OFFLINE':False,'TOLERANCE':.2,'OUTPUT':str(output.resolve())},context=context,feedback=feedback)
 created=set(project.mapLayers())-before;assert len(created)==1,created
 layer=project.mapLayer(created.pop());assert layer.renderer().classAttribute()=='Woningtype'
 features={f['identificatie']:f for f in layer.getFeatures()};rows=[]
 for bagid,e in expected.items():
  if e['case']!=case:continue
  assert bagid in features,(case,bagid,'missing')
  f=features[bagid];assert f['Woningtype']==e['woningtype'],(case,bagid,f.attributes());assert f['DakOnzeker']==0,f.attributes()
  rows.append({'bag_id':bagid,'woningtype':f['Woningtype'],'dakbijgeb':f['DakBijgeb'],'dakverbonden':f['DakVerbonden'],'controle':f['Controle']})
 results[case]={'total_features':layer.featureCount(),'validated':len(rows),'results':rows};print(case,results[case],flush=True)
 settings=QgsMapSettings();settings.setLayers([layer]);settings.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:28992'));settings.setExtent(QgsRectangle(*bounds));settings.setOutputSize(QSize(1000,850));settings.setBackgroundColor(__import__('qgis.PyQt.QtGui',fromlist=['QColor']).QColor('white'))
 job=QgsMapRendererParallelJob(settings);job.start();job.waitForFinished();job.renderedImage().save(str(OUT/(case+'.png')))
 # Persist categorized style alongside each GeoPackage.
 layer.saveNamedStyle(str(OUT/(case+'.qml')))
 project.removeMapLayer(layer.id())
Path('outputs/live_validation.json').write_text(json.dumps({'qgis':Qgis.QGIS_VERSION,'source':'LIVE PDOK WFS + real AHN WCS/cache','cases':results},indent=2))
print('LIVE 27/27 OK',flush=True)
QgsProject.instance().clear()
app.exitQgis()

