import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from brief_contract import read_json, resolve_style
from prepare_icon_jobs import prepare

class LimitedRetirementTests(unittest.TestCase):
    def test_only_user_selected_three_are_retired_with_original_numbering(self):
        styles=read_json(ROOT/'references/style-recipes.json')['styles']
        self.assertEqual({s['id'] for s in styles if s['status']=='retired'}, {'embroidered-textile','embossed-leather','glazed-porcelain'})
        active=[s for s in styles if s['status']=='active']
        self.assertEqual(len(active),21)
        self.assertEqual(sum(s['number'] is not None for s in active),20)
        self.assertEqual([(s['id'],s['number']) for s in active if s['number'] is None],[('enterprise-narrative',None)])

    def test_retirement_applies_to_both_asset_kinds_and_all_existing_aliases(self):
        styles=read_json(ROOT/'references/style-recipes.json')['styles']
        for style in (s for s in styles if s['status']=='retired'):
            for selector in [style['id'],style['nameZh'],style['nameJa'],style['nameEn'],str(style['number'])]:
                with self.assertRaises(ValueError):resolve_style({'styleId':selector})
            for kind in ['icon','illustration']:
                brief={'direction':{'styleId':style['id']},'palette':{'roles':{'ink':'#0D2046','primary':'#1456D9'}},
                       'assets':[{'id':'pending','kind':kind,'meaning':'Review remains pending','subject':'A document with a waiting cue'}]}
                with self.assertRaises(ValueError):prepare(brief,allow_illustrations=True)

if __name__=='__main__':unittest.main()
