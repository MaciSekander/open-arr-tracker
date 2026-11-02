"""Checks on the model maths and the collectors. Standard library only.

    python3 -m unittest discover tests
"""
import datetime as dt, json, math, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'pipeline'), str(ROOT / 'pipeline' / 'collectors')]
import build as B  # noqa: E402
import collect_ramp as CR  # noqa: E402

D = dt.date.fromisoformat
VINTAGE = ROOT / 'data' / 'vintage_2026-10-19'  # a fixed, committed vintage so results do not move with new data


def daily(start, values):
    return [(D(start) + dt.timedelta(days=i), v) for i, v in enumerate(values)]


class Series(unittest.TestCase):
    def test_trailing_mean_needs_full_window(self):
        s = daily('2026-01-01', [10] * 30)
        self.assertEqual(B.trailing_mean(s, D('2026-01-28'), 28), 10)
        self.assertIsNone(B.trailing_mean(s, D('2026-01-27'), 28))  # window starts before the series

    def test_trailing_mean_tolerates_a_few_gaps_only(self):
        vals = [10] * 28
        for i in range(5):
            vals[i] = None
        self.assertEqual(B.trailing_mean(daily('2026-01-01', vals), D('2026-01-28'), 28), 10)
        vals[5:10] = [None] * 5
        self.assertIsNone(B.trailing_mean(daily('2026-01-01', vals), D('2026-01-28'), 28))

    def test_weekly_mean_uses_disjoint_weeks(self):
        s = daily('2026-01-01', list(range(1, 29)))  # day 28 has value 28
        self.assertEqual(B.weekly_mean(s, D('2026-01-28'), 28), (28 + 21 + 14 + 7) / 4)

    def test_growth_refuses_across_a_break(self):
        sig = {'kind': 'daily', 'breaks': ['2026-03-01'], 'series': {'X': daily('2026-01-01', [1] * 120)}}
        g, why = B.growth(sig, 'X', D('2026-02-15'), D('2026-04-01'), 28)
        self.assertIsNone(g)
        self.assertIn('break', why)
        g, _ = B.growth(sig, 'X', D('2026-04-01'), D('2026-04-28'), 28)
        self.assertEqual(g, 1)


class ModelOnCommittedVintage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reg = {n: json.loads((ROOT / 'registry' / f'{n}.json').read_text()) for n in ['anchors', 'model']}
        cls.m = B.Model(B.load_signals(VINTAGE), reg['model'], reg['anchors']['anchors'])
        cls.out = {c: cls.m.company(c) for c in B.COMPANIES}

    def test_backtest_never_uses_later_reports(self):
        for c in B.COMPANIES:
            pairs = self.m.fit[c]['pairs']
            self.assertEqual(pairs[0]['rt_beta'], 1.0, 'first report has no history, so one for one')
            for i, p in enumerate(pairs):
                self.assertAlmostEqual(p['rt_beta'], B.Model._beta(pairs[:i]))

    def test_two_piece_borrows_only_earlier_donor_reports(self):
        donor = self.m.fit['Anthropic']['pairs']
        for p in self.m.fit['OpenAI']['pairs']:
            expect = B.Model._beta([q for q in donor if q['date'] < p['date']])
            self.assertAlmostEqual(self.m.donor_beta_before('OpenAI', p['date']), expect)

    def test_range_is_ordered_and_sized_by_past_misses(self):
        for c, x in self.out.items():
            n = x['nowcast']
            self.assertLess(n['low'], n['reference'])
            self.assertLess(n['reference'], n['high'])
            self.assertAlmostEqual(math.log(n['high'] / n['reference']), x['band']['rmse_log'])
            if x['latest']['qualifier'] == '>':
                self.assertGreaterEqual(n['low'], x['latest']['value_b'])

    def test_curve_ends_at_the_headline(self):
        for x in self.out.values():
            self.assertEqual(x['curve'][-1][0], x['as_of'])
            self.assertAlmostEqual(x['curve'][-1][1], x['nowcast']['reference'], places=1)

    def test_parts_add_up(self):
        for x in self.out.values():
            self.assertAlmostEqual(x['public']['reference'] + x['residual']['reference'], x['nowcast']['reference'])

    def test_outlook_cases(self):
        for x in self.out.values():
            o = x['outlook']
            self.assertEqual(o['flat_b'], x['nowcast']['reference'])
            self.assertAlmostEqual(o['steady_b'] - o['flat_b'], o['added_per_month_b'] * o['months'])
            self.assertAlmostEqual(o['recent_b'] - o['flat_b'], o['recent_per_month_b'] * o['months'])

    def test_headline_beats_naive_baseline(self):
        for c in B.COMPANIES:
            methods = {m['method']: m for m in self.m.fit[c]['methods']}
            model = next(m for m in methods.values() if m['is_model'])
            self.assertLess(model['mape'], methods['Carry forward']['mape'])


class RampCollector(unittest.TestCase):
    def setUp(self):
        self._fetch = CR.fetch

    def tearDown(self):
        CR.fetch = self._fetch

    def test_falls_back_to_chart_data_endpoint(self):
        rows = [{'usage_date': '2026-10-23', 'model_maker': 'openai', 'token_type': 'all_tokens', 'token_count_7d': 1, 'token_cost_usd_7d': 1}]
        seen = []
        CR.fetch = lambda url, path: (seen.append(url), json.dumps(rows).encode())[1]
        got, origin = CR.load('<html></html>', 'tokenPrices', Path('/nonexistent'))
        self.assertEqual((got, origin), (rows, 'chart-data'))
        self.assertEqual(seen, [CR.CHART_DATA + 'tokenPrices'])

    def test_format_change_fails_loudly(self):
        CR.fetch = lambda url, path: json.dumps([{'unexpected': 1}]).encode()
        with self.assertRaisesRegex(ValueError, 'missing fields'):
            CR.load('<html></html>', 'tokenPrices', Path('/nonexistent'))


if __name__ == '__main__':
    unittest.main()
