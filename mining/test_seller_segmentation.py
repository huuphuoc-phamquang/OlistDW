"""Regression checks for join grain, service metrics and portable source loading."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing

import numpy as np
import pandas as pd

from seller_segmentation import create_features, load_sources, prepare_data, preprocess_features


def fixture():
    return {
        "sellers": pd.DataFrame({"seller_id": ["a", "b", "c"], "seller_city": ["x"] * 3, "seller_state": ["SP"] * 3}),
        "order_items": pd.DataFrame([
            ["one", 1, "p", "a", 10., 1.], ["one", 2, "p", "a", 20., 2.],
            ["one", 3, "p", "b", 5., 1.], ["two", 1, "q", "a", 30., 3.],
            ["cancel", 1, "p", "c", 100., 10.],
        ], columns=["order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"]),
        "orders": pd.DataFrame([
            ["one", "delivered", "2018-01-01 10:00", "2018-01-03 16:00", "2018-01-03"],
            ["two", "delivered", "2018-01-02 10:00", "2018-01-06 10:00", "2018-01-05"],
            ["cancel", "canceled", "2018-01-03 10:00", None, "2018-01-05"],
        ], columns=["order_id", "order_status", "order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date"]),
        "products": pd.DataFrame({"product_id": ["p", "q"], "product_category_name": ["cat1", "cat2"]}),
        "order_reviews": pd.DataFrame({"order_id": ["one", "one", "two"], "review_score": [1, 5, 5]}),
    }


class SellerPreparationTests(unittest.TestCase):
    def test_no_review_fanout_or_item_weighted_order_metrics(self):
        sales, sellers, audit = prepare_data(fixture())
        profiles, excluded, _ = create_features(sales, sellers)
        a = profiles.set_index("seller_id").loc["a"]
        self.assertEqual(len(sales), 4)
        self.assertEqual(a["total_sales"], 60)
        self.assertEqual(a["avg_order_value"], 30)
        self.assertEqual(a["review_score_mean"], 4)  # mean(mean(1, 5), 5)
        self.assertEqual(a["late_delivery_rate"], .5)  # same-day delivery is on time
        self.assertEqual(excluded["seller_id"].tolist(), ["c"])
        self.assertEqual(audit["multi_seller_orders"], 1)

    def test_invalid_dates_do_not_become_on_time_deliveries(self):
        tables = fixture()
        tables["orders"].loc[0, "order_delivered_customer_date"] = "2017-12-31"
        sales, sellers, _ = prepare_data(tables)
        profiles, _, _ = create_features(sales, sellers)
        a = profiles.set_index("seller_id").loc["a"]
        self.assertEqual(a["valid_deadline_order_count"], 1)
        self.assertEqual(a["late_delivery_rate"], 1)

    def test_conflicting_keys_and_orphans_are_rejected(self):
        tables = fixture()
        tables["sellers"] = pd.concat([tables["sellers"], pd.DataFrame([
            {"seller_id": "a", "seller_city": "other", "seller_state": "SP"}])])
        with self.assertRaisesRegex(ValueError, "duplicate key"):
            prepare_data(tables)
        tables = fixture()
        tables["order_items"].loc[0, "seller_id"] = "missing"
        with self.assertRaisesRegex(ValueError, "unmatched keys"):
            prepare_data(tables)

    def test_imputation_and_scaling_can_be_reproduced_from_json_parameters(self):
        sales, sellers, _ = prepare_data(fixture())
        profiles, _, _ = create_features(sales, sellers)
        profiles.loc[0, "review_score_mean"] = np.nan
        matrix, metadata = preprocess_features(profiles)
        restored = profiles.set_index("seller_id")[metadata["feature_order"]].astype(float)
        restored = restored.fillna(metadata["medians"])
        restored[metadata["log1p_features"]] = np.log1p(restored[metadata["log1p_features"]])
        restored = (restored - pd.Series(metadata["mean"])) / pd.Series(metadata["scale"])
        np.testing.assert_allclose(restored, matrix)
        self.assertTrue(np.isfinite(matrix).all().all())
        np.testing.assert_allclose(matrix.mean(), 0, atol=1e-12)

    def test_sqlite_and_csv_sources_produce_same_features(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with closing(sqlite3.connect(root / "olist.sqlite")) as connection:
                for name, frame in fixture().items():
                    frame.to_sql(name, connection, index=False)
                    frame.to_csv(root / f"{name}.csv", index=False)
                connection.commit()
            results = []
            for source in [root, root / "olist.sqlite"]:
                tables, _ = load_sources(source)
                sales, sellers, _ = prepare_data(tables)
                results.append(create_features(sales, sellers)[0])
            pd.testing.assert_frame_equal(*results)


if __name__ == "__main__":
    unittest.main()
