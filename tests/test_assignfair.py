import itertools
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from assignfair import optimize, greedy, compare, render
ROOT=Path(__file__).resolve().parents[1]
def student(i,p):return dict(id=i,available=p[:],preferences=p[:])
def brute(data):
    best=None
    for choice in itertools.product(*[[None]+s['preferences'] for s in data['students']]):
        if any(choice.count(k)>v for k,v in data['sessions'].items()):continue
        objective=(-sum(x is not None for x in choice),sum(s['preferences'].index(x) for s,x in zip(data['students'],choice) if x is not None))
        if best is None or objective<best:best=objective
    return best
class Tests(unittest.TestCase):
    def test_rerouting_improves_cardinality(self):
        d=json.loads((ROOT/'examples/students.json').read_text());r=compare(d)
        self.assertEqual(r['optimized']['assigned'],2);self.assertEqual(r['greedy']['assigned'],1)
        self.assertEqual(r['optimized']['preference_cost'],1)
        self.assertIsNone(r['comparison']['preference_cost_reduction_at_equal_count'])
        self.assertEqual({x['reason'] for x in r['optimized']['unmet_demand']},{'no_available_session','all_available_sessions_have_zero_capacity'})
    def test_equal_cardinality_cost_improvement(self):
        d={'sessions':{'A':1,'B':1,'C':0},'students':[student('1',['A','B']),student('2',['A','C','B'])]}
        self.assertEqual(optimize(d)['assigned'],2);self.assertEqual(greedy(d)['assigned'],2)
        self.assertEqual(optimize(d)['preference_cost'],1);self.assertEqual(greedy(d)['preference_cost'],2)
    def test_zero_students(self):
        self.assertEqual(optimize({'sessions':{'A':1},'students':[]})['assigned'],0)
    def test_capacity_competition(self):
        r=optimize({'sessions':{'A':1},'students':[student('1',['A']),student('2',['A'])]})
        self.assertEqual(r['unassigned'],1);self.assertEqual(r['unmet_demand'][0]['reason'],'capacity_competition')
    def test_invalid(self):
        cases=[{}, {'sessions':{'A':True},'students':[]},{'sessions':{'A':-1},'students':[]}, {'sessions':{'A':1},'students':[student('1',['B'])]}, {'sessions':{'A':1},'students':[student('1',['A','A'])]}, {'sessions':{'A':1},'students':[student('1',[]),student('1',[])]}, {'sessions':{'A':1},'students':[dict(id='1',available=['A'],preferences=[])]}]
        for d in cases:
            with self.subTest(d=d),self.assertRaises(ValueError):optimize(d)
    def test_seeded_against_exhaustive(self):
        rng=random.Random(42)
        for _ in range(200):
            d={'sessions':{s:rng.randrange(3) for s in 'ABC'},'students':[student(str(i),rng.sample(list('ABC'),rng.randrange(4))) for i in range(4)]}
            before=json.dumps(d);r=optimize(d)
            self.assertEqual((-r['assigned'],r['preference_cost']),brute(d))
            self.assertEqual(json.dumps(d),before)
            self.assertTrue(all(s['used']<=s['capacity'] for s in r['sessions']))
            self.assertEqual(r,optimize(d))
    def test_html_escape(self):
        self.assertNotIn('<script>',render(compare({'sessions':{'A':1},'students':[student('<script>',['A'])]})))
    def test_cli(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'out';cmd=[sys.executable,str(ROOT/'assignfair.py'),str(ROOT/'examples/students.json'),'--out',str(out)]
            r=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(json.loads((out/'report.json').read_text())['optimized']['assigned'],2)
            self.assertTrue((out/'index.html').exists());self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,2)
if __name__=='__main__':unittest.main()
