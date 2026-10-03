import unittest,tempfile,sys,json,copy
from pathlib import Path
from xml.etree import ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pymupdf
from plan_structure import face_pair,page_point,dimension_scale
from plan_import import pdf
from drawing_editor import sanitized,clean_changes
from drawing_scene import resolve,cut_walls

class ReviewedStructure(unittest.TestCase):
 def test_rotated_pdf_paint_and_mapping_are_preserved_without_classifying(self):
  with tempfile.TemporaryDirectory() as tmp:
   doc=pymupdf.open();p=doc.new_page(width=200,height=300)
   p.draw_rect(pymupdf.Rect(10,20,30,80),color=(0,0,0),fill=(0,0,0))
   p.draw_line((40,40),(100,40),color=(1,0,0),dashes='[3 2] 1')
   p.insert_text((50,80),'Dimension');p.set_rotation(90)
   source=Path(tmp)/'input.pdf';doc.save(source);doc.close()
   row=pdf(source,Path(tmp))[0];svg=ET.fromstring(row['vector_path'].read_text())
   shapes=[x for x in svg if x.tag.endswith('path')]
   self.assertTrue(all(x.get('class')=='detail' for x in shapes))
   self.assertIn('fill:#000000',shapes[0].get('style'));self.assertIn('stroke-dasharray',shapes[1].get('style'))
   self.assertIn('style=',sanitized(shapes[0]));self.assertIn('rotate(90.0',row['vector_path'].read_text())
   self.assertEqual(row['metadata']['embedded_images'],0)
   with pymupdf.open(source) as d:self.assertEqual(page_point(d[0],pymupdf.Point(10,20),900,600),[840,30])
   self.assertEqual(resolve({'elements':[{'id':'n','kind':'detail','svg':sanitized(shapes[0])}]})[0],[])
 def test_faces_do_not_extend_past_their_evidenced_shared_span(self):
  f=face_pair([[0,0],[100,0]],[[20,4],[80,4]],'newtest')
  self.assertEqual(f['points'],[[20,2],[80,2]]);self.assertEqual(f['thickness'],4)
  for b in ([[101,4],[150,4]],[[20,2],[30,20]],[[0,0],[100,0]]):
   with self.assertRaises(ValueError):face_pair([[0,0],[100,0]],b,'newbad')
 def test_opening_cuts_only_its_wall_not_an_adjacent_cross_wall(self):
  wall=face_pair([[0,0],[100,0]],[[0,4],[100,4]],'newwall')
  vertical=face_pair([[40,10],[40,50]],[[44,10],[44,50]],'newvertical')
  rows=cut_walls([wall,vertical,dict(id='newdoor',kind='door',points=[[20,2],[30,2]],thickness=4)])
  self.assertEqual([r['points'] for r in rows if r['kind']=='wall'],[[[0,2],[20,2]],[[30,2],[100,2]],[[42,10],[42,50]]])
 def test_source_evidence_and_review_notes_survive_editing(self):
  f=face_pair([[0,0],[100,0]],[[0,4],[100,4]],'newtest',['pdfpage1path1'])
  doc=dict(width=200,height=100,elements=[],features=[f]);changed=copy.deepcopy(f)
  changed['points'][1][0]=90;changed['review_note']='Check junction';changed['evidence']={'source_ids':['forged']}
  _,features=clean_changes(doc,dict(features=[changed],edits={}))
  self.assertEqual(features[0]['evidence']['source_ids'],['pdfpage1path1'])
  self.assertTrue(features[0]['evidence']['manually_changed']);self.assertEqual(features[0]['review_note'],'Check junction')
 def test_source_styles_cannot_introduce_external_resources(self):
  node=ET.fromstring('<path d="M0 0 L1 1" style="fill:url(https://example.invalid);stroke:#000;position:absolute"/>')
  out=sanitized(node);self.assertNotIn('url',out);self.assertNotIn('position',out);self.assertIn('stroke:#000',out)
 def test_scale_requires_explicit_positive_dimension(self):
  self.assertAlmostEqual(dimension_scale([0,0],[100,0],3),.03)
  with self.assertRaises(ValueError):dimension_scale([0,0],[0,0],3)


class DraftIsolation(unittest.TestCase):
 def test_live_databases_are_refused_before_binding(self):
  from launch_plan_draft import make_draft_server
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'studio.json';path.write_text(json.dumps({'projects':{'p':{'name':'Active apartment'}},'jobs':{}}));before=path.read_bytes()
   with self.assertRaises(ValueError):make_draft_server(tmp,0)
   self.assertEqual(before,path.read_bytes())
 def test_non_drawing_mutations_are_refused_without_dispatch(self):
  from launch_plan_draft import DraftHandler
  from unittest.mock import patch
  for route in ['/api/projects/p/generation-phase','/api/projects/p/rooms/r/generate-image','/api/projects/p/rooms/r/generate-video','/api/studio/release','/api/renderer/start','/api/projects/p/rooms/r/approve-video']:
   class Request:
    path=route
    def reply(self,body,status):return body,status
   with patch('server.Handler.mutate',side_effect=AssertionError('must not dispatch')):
    body,status=DraftHandler.mutate(Request(),'POST');self.assertEqual(status,403)

if __name__=='__main__':unittest.main()
