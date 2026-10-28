"""Functional acceptance checks for score endpoints, quality gates, input integrity and export."""
import copy,json,pathlib,tempfile,unittest
import pandas as pd
from analysis import analyze,default_config,rescore,load_inputs,load_supplement,ASSETS
from exporter import export_all

class FunctionalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.example=ASSETS/'examples/合成示例_三条鱼.csv';cls.result=analyze([cls.example])
    def test_endpoints_and_monotonicity(self):
        s=self.result['scores'].set_index('fish_id').score
        self.assertEqual(sum(r['weight']>0 for r in default_config()['scoring']['rules']),31)
        self.assertTrue(s.dropna().between(0,100).all())
        self.assertEqual(len(self.result['stats']),58);self.assertEqual(len(self.result['details']),3*58)
    def test_weighted_contributions_reconcile(self):
        for f,g in self.result['details'].groupby('fish_id'):
            score=self.result['scores'].set_index('fish_id').loc[f,'score']
            self.assertAlmostEqual(score,g.contribution.sum(),places=8)
    def test_changed_engine_requires_reanalysis(self):
        c=default_config();c['engine']['v_move_m_s']=.1
        with self.assertRaisesRegex(ValueError,'重新分析'):rescore(copy.deepcopy(self.result),c)
    def test_quality_gate_preserves_missing(self):
        c=default_config();c['quality']['min_score_duration_s']=300
        r=rescore(copy.deepcopy(self.result),c)
        self.assertTrue(r['scores'].score.isna().all())
        self.assertTrue(r['details'].query('metric_id==1').value.isna().all())
    def test_duplicate_input_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'同一鱼'):load_inputs([self.example,self.example],default_config())
    def test_single_short_track_exports_without_social(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t)/'tiny.csv';pd.read_csv(self.example).iloc[:2].to_csv(p,index=False)
            r=analyze([p]);self.assertTrue(r['scores'].score.isna().all())
            self.assertEqual(len(r['details']),58);export_all(r,pathlib.Path(t)/'out')
    def test_seconds_alias(self):
        with tempfile.TemporaryDirectory() as t:
            d=pd.read_csv(self.example);d['time_s']=d.pop('timestamp_ms')/1000
            p=pathlib.Path(t)/'seconds.csv';d.to_csv(p,index=False)
            r=analyze([p]);self.assertAlmostEqual(r['span_s'],self.result['span_s'])
    def test_segment_boundary_does_not_add_distance(self):
        with tempfile.TemporaryDirectory() as t:
            d=pd.DataFrame({'fish_id':['F']*8,'segment_id':[1]*4+[2]*4,'timestamp_ms':list(range(0,800,100)),
                'x_m':[0]*4+[.5]*4,'y_m':[0]*8,'z_m':[.4]*8})
            p=pathlib.Path(t)/'segment.csv';d.to_csv(p,index=False);r=analyze([p])
            self.assertAlmostEqual(r['individual'].iloc[0].path_length_m,0)
    def test_supplement_traceability_and_custom_score(self):
        with tempfile.TemporaryDirectory() as t:
            p=pathlib.Path(t)/'supp.csv'
            pd.DataFrame([{'fish_id':'SYNTH_MID','metric_id':1,'value':30,'unit':'s','source':'人工核验视频A','protocol':'出避难所潜伏期'}]).to_csv(p,index=False)
            r=analyze([self.example],supplement=p)
            v=r['details'].query("fish_id=='SYNTH_MID' and metric_id==1").iloc[0]
            self.assertEqual(v.status,'实验补充');self.assertEqual(v.value,30)
            c=default_config();c['scoring']['rules'][0].update(weight=5,low=0,high=300)
            self.assertEqual(rescore(r,c)['score_title'],'探索性综合行为分')
    def test_bad_coordinates_and_infinity_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            d=pd.read_csv(self.example).iloc[:5].copy();d.loc[0,'x_m']=float('inf')
            p=pathlib.Path(t)/'bad.csv';d.to_csv(p,index=False)
            with self.assertRaisesRegex(ValueError,'无穷'):analyze([p])
    def test_export_values_and_structure(self):
        import openpyxl
        with tempfile.TemporaryDirectory() as t:
            export_all(self.result,t);w=openpyxl.load_workbook(pathlib.Path(t)/'58项指标分析.xlsx',read_only=True,data_only=True)
            self.assertEqual(len(w.sheetnames),7)
            self.assertEqual(w['58项指标明细'].max_row,175);self.assertEqual(w['58项指标统计'].max_row,59)
            self.assertEqual(w['个体评分']['B2'].value, None if pd.isna(self.result['scores'].iloc[0].score) else self.result['scores'].iloc[0].score)
            self.assertIsNone(w['58项指标明细']['E2'].value)
            w.close()
            self.assertEqual(len(json.loads((pathlib.Path(t)/'分析参数与权重.json').read_text(encoding='utf-8'))['scoring']['rules']),58)

if __name__=='__main__':unittest.main(verbosity=2)
