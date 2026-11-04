"""Checks for physical invariants and invalid user input, no Inventor claims."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import run_model
import cad_core


class ParametersTest(unittest.TestCase):
    def setUp(self):
        self.data=run_model.load_config(run_model.ROOT/'config/paper_default.json')

    def load_changed(self,**changes):
        d={**self.data,**changes}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'p.json';path.write_text(json.dumps(d))
            return run_model.load_config(path)

    def test_reference_size(self):
        p=run_model.geometry(self.data)
        self.assertAlmostEqual(p['cell_pitch_mm'],77.1,places=9)
        self.assertAlmostEqual(p['l1_mm'],p['b_mm'],places=9)

    def test_uniform_scale_preserves_angles_and_density(self):
        a=run_model.geometry(self.data)
        b=run_model.geometry({**self.data,'ScaleFactor':.25})
        for key in ('l1_mm','l2_mm','l3_mm','cell_pitch_mm','a_mm','c_mm'):
            self.assertAlmostEqual(b[key]/a[key],.25)
        self.assertAlmostEqual(b['nominal_mu'],a['nominal_mu'])

    def test_negative_diameter(self):
        with self.assertRaises(ValueError):self.load_changed(D_base=-1)

    def test_noninteger_repeat(self):
        with self.assertRaises(ValueError):self.load_changed(Nx=1.5)

    def test_zero_repeat(self):
        with self.assertRaises(ValueError):self.load_changed(Nz=0)

    def test_nonfinite(self):
        with self.assertRaises(ValueError):self.load_changed(Theta=float('nan'))

    def test_extreme_angle(self):
        with self.assertRaises(ValueError):self.load_changed(Theta=40)

    def test_too_short_axial_connector(self):
        with self.assertRaises(ValueError):run_model.geometry({**self.data,'L1_base':.1})

    def test_nonincident_collision_rejected(self):
        p=run_model.geometry({**self.data,'D_base':15})
        nodes,edges=cad_core.cell_graph(p)
        with self.assertRaises(ValueError):cad_core.graph_checks(nodes,edges,p['radii_mm'])

    def test_repetition_boundaries(self):
        p=run_model.geometry(self.data);nodes,edges=cad_core.cell_graph(p)
        nn,ee,joints=cad_core.repeat_graph(nodes,edges,(2,2,2),p['cell_pitch_mm'])
        self.assertEqual((len(nn),len(ee),len(joints)),(244,432,12))
        for j in joints:
            incident=[(u,v,t) for u,v,t in ee if j['node'] in (u,v)]
            self.assertEqual(len(incident),2)
            self.assertTrue(all(t==1 for _,_,t in incident))


if __name__=='__main__':unittest.main(verbosity=2)
