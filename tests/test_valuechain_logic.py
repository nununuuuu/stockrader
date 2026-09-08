import json
import os
import tempfile
import unittest

from valuechain import HISTORY_SCHEMA_VERSION, valuechainManager


class ValuechainDataLogicTests(unittest.TestCase):
    def make_manager(self, temp_dir, valuechain_map):
        cache_file = os.path.join(temp_dir, "valuechain.json")
        history_file = os.path.join(temp_dir, "industry_history.json")
        with open(cache_file, "w", encoding="utf-8") as file:
            json.dump({
                "update_date": "2026-08-11",
                "map": valuechain_map,
            }, file, ensure_ascii=False)
        return valuechainManager(
            {"2330": {"electronics": "Yahoo 半導體"}},
            cache_file=cache_file,
            history_file=history_file,
        )

    def test_reload_does_not_replace_valuechain_with_yahoo_categories(self):
        source_map = {
            "2330": [
                {"main": "半導體", "path": "半導體 > IC製造 > 晶圓代工"},
                {"main": "人工智慧", "path": "人工智慧 > AI晶片 > 一般"},
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = self.make_manager(temp_dir, source_map)
            with open(manager.cache_file, "r", encoding="utf-8") as file:
                cache_before = file.read()

            self.assertTrue(manager.run_full_update())
            self.assertEqual(source_map, manager.valuechain_map)
            with open(manager.cache_file, "r", encoding="utf-8") as file:
                self.assertEqual(cache_before, file.read())

    def test_old_history_schema_is_ignored(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = os.path.join(temp_dir, "valuechain.json")
            history_file = os.path.join(temp_dir, "industry_history.json")
            with open(cache_file, "w", encoding="utf-8") as file:
                json.dump({"update_date": "2026-08-11", "map": {"2330": []}}, file)
            with open(history_file, "w", encoding="utf-8") as file:
                json.dump({"20260703": {"半導體::IC製造": {"inst_net": 99}}}, file)

            manager = valuechainManager({}, cache_file=cache_file, history_file=history_file)
            self.assertEqual({}, manager.history_data)

    def test_recent_history_stops_at_large_date_gap(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = self.make_manager(temp_dir, {"2330": []})
            manager.history_data = {
                "20260810": {},
                "20260808": {},
                "20260703": {},
            }
            self.assertEqual(
                ["20260810", "20260808"],
                manager._recent_history_dates("20260811"),
            )

    def test_each_group_uses_full_component_value_and_deduplicates_same_group(self):
        group_a = {"main": "半導體", "path": "半導體 > IC製造 > 一般"}
        group_a_duplicate = {"main": "半導體", "path": "半導體 > IC製造 > 晶圓代工"}
        group_b = {"main": "人工智慧", "path": "人工智慧 > AI晶片 > 一般"}
        valuechain_map = {
            "1111": [group_a, group_a_duplicate, group_b],
            "2222": [group_a],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            manager = self.make_manager(temp_dir, valuechain_map)
            manager.history_data = {
                date: {
                    "半導體::IC製造": {"net_force": 2.0, "inst_net": 2.0, "change": 1.0},
                    "人工智慧::AI晶片": {"net_force": 1.0, "inst_net": 1.0, "change": 1.0},
                }
                for date in ["20260810", "20260809", "20260808", "20260807"]
            }
            manager.fetch_market_prices = lambda _date: ({
                "1111": {"name": "甲", "amount": 10.0, "price": 100.0, "change_pct": 1.0},
                "2222": {"name": "乙", "amount": 20.0, "price": 100.0, "change_pct": 1.0},
            }, 100.0)

            result = manager.get_valuechain_industry_data(
                "20260811",
                {},
                chip_map={"1111": {"total": 1000}, "2222": {"total": 1000}},
                margin_map={"1111": {"f_change": 5000}, "2222": {"f_change": -1000}},
            )
            by_key = {item["key"]: item for item in result["top5"] + result["others"]}
            semiconductor = by_key["半導體::IC製造"]

            self.assertEqual(30.0, semiconductor["flow"])
            self.assertEqual(2.0, semiconductor["net_inst_1d"])
            self.assertEqual(10.0, semiconductor["inst_net_5d"])
            self.assertEqual(semiconductor["net_inst_1d"], semiconductor["net_force"])
            self.assertEqual(4.0, semiconductor["margin_net_1d"])
            self.assertEqual(2, len(semiconductor["components"]))
            self.assertEqual(5, semiconductor["history_days"])
            self.assertAlmostEqual(5.1, semiconductor["change_5d"], places=2)

    def test_new_history_file_has_schema_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = self.make_manager(temp_dir, {"2330": []})
            manager.history_data = {"20260811": {}}
            manager._save_history()
            with open(manager.history_file, "r", encoding="utf-8") as file:
                payload = json.load(file)
            self.assertEqual(HISTORY_SCHEMA_VERSION, payload["_schema_version"])
            self.assertIn("20260811", payload["dates"])


if __name__ == "__main__":
    unittest.main()
