import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio_native.model import *

class ModelTests(unittest.TestCase):
    def test_defaults_are_compatible(self):
        s=new_state()
        self.assertEqual(validate(s),[])
        self.assertEqual(len(s['edges']),1)
        self.assertEqual(s['format'],'smi.dynamic-node-lab')
    def test_port_type_and_existing_input(self):
        s=new_state(); a,b,c=s['nodes']
        with self.assertRaisesRegex(ValueError,'already connected'):
            connect(s,a['id'],a['draft_ports']['outputs'][0]['id'],b['id'],b['draft_ports']['inputs'][0]['id'])
        with self.assertRaisesRegex(ValueError,'Type mismatch'):
            connect(s,c['id'],c['draft_ports']['outputs'][1]['id'],b['id'],b['draft_ports']['inputs'][1]['id'])
    def test_remove_port_prunes_edges(self):
        s=new_state(); a=s['nodes'][0]
        remove_port(s,a['id'],a['draft_ports']['outputs'][0]['id'])
        self.assertEqual(len(s['edges']),0)
    def test_pagination_and_search(self):
        s=make_node('folder')['containers'][0]
        rows,page,pages,total=paged_rows(s)
        self.assertEqual((page,total,len(rows)),(0,1,1))
        self.assertTrue(matches(s['rows'][0],'dataset_098'))
    def test_round_trip_and_reject_broken(self):
        s=new_state()
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'test.json'
            write_state(path,s)
            self.assertEqual(read_state(path),s)
            s['edges'][0]['targetPort']='unknown'
            self.assertIn('Broken edge',validate(s))
    def test_settings_projection_can_use_same_model(self):
        s=new_state(); s['settings']['port_label_mode']='always'
        self.assertEqual(validate(s),[])
if __name__=='__main__':unittest.main()

class InlineDefaultTests(unittest.TestCase):
    def test_typed_fallbacks_are_roundtrip_safe(self):
        self.assertEqual(parse_input_default('bool',' FALSE '),False)
        self.assertEqual(parse_input_default('string',''), '')
        self.assertEqual(parse_input_default('u32','4294967295'),4294967295)
        self.assertEqual(parse_input_default('i32','-2147483648'),-2147483648)
        self.assertEqual(parse_input_default('f64','2.5'),2.5)
        with self.assertRaises(ValueError):parse_input_default('bool','yes')
        with self.assertRaises(ValueError):parse_input_default('u32','-1')
        with self.assertRaises(ValueError):parse_input_default('i32','2147483648')
        with self.assertRaises(ValueError):parse_input_default('f32','nan')
        with self.assertRaises(ValueError):parse_input_default('audio','1')

    def test_default_remains_stored_when_an_edge_connects(self):
        s=new_state()
        a,b,_=s['nodes']
        target=b['draft_ports']['inputs'][2]
        self.assertEqual(target['type'],'f32')
        target['default']=0.5
        source=make_node('custom')
        s['nodes'].append(source)
        connect(s,source['id'],source['draft_ports']['outputs'][0]['id'],b['id'],target['id'])
        self.assertEqual(target['default'],0.5)
        self.assertEqual(validate(s),[])
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'draft.json'
            write_state(p,s)
            restored=read_state(p)
            self.assertEqual(restored['nodes'][1]['draft_ports']['inputs'][2]['default'],0.5)

    def test_rejects_invalid_default_in_external_graph(self):
        s=new_state()
        p=s['nodes'][0]['draft_ports']['inputs'][0]
        p['default']=True  # audio fallback is not a supported scalar
        self.assertIn('Invalid input default/type combination',validate(s))
        p.pop('default')
        p=s['nodes'][0]['draft_ports']['outputs'][0]
        p['default']=1
        self.assertIn('Output port cannot have an inline default',validate(s))
