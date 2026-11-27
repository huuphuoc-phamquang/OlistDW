"""Regenerate the standalone teaching notebook from the shared pipeline source."""

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "mining/seller_segmentation.py").read_text(encoding="utf-8")
step1 = source[:source.index("def create_features(")]
step2 = source[source.index("def create_features("):source.index("def preprocess_features(")]
step3 = source[source.index("def preprocess_features("):source.index('if __name__ == "__main__":')]
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
nb = nbf.v4.new_notebook()
nb.metadata = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.12"},
}
nb.cells = [
    md("""# Olist: chuẩn bị dữ liệu phân khúc nhà bán hàng

**Phụ trách: Tzy | Bước 1-3 trong mục Data mining.**

Nguồn: [Olist SQLite trên Kaggle](https://www.kaggle.com/datasets/terencicp/e-commerce-dataset-by-olist-as-an-sqlite-database).
Mục tiêu: một dòng mỗi seller và ma trận đầu vào dùng chung cho K-Means, GMM, DBSCAN. Chưa huấn luyện phân cụm.

Notebook độc lập, chứa mã đồng bộ từ `mining/seller_segmentation.py`. Trên Kaggle, **Add Input** dataset Olist; trên Colab/máy cá nhân đặt `SOURCE` rõ ràng. Nếu thiếu thư viện, cài `numpy pandas scikit-learn matplotlib` trong môi trường notebook rồi chạy lại.

Chỉ tính đơn **delivered** có ngày mua hợp lệ. Seller ngoài cohort được xuất riêng. Đánh giá/giao hàng là thông tin của cả đơn, có thể dùng chung cho nhiều seller. Xem `mining/README.md` trong repo để đọc đầy đủ giả định và định nghĩa."""),
    md("""## Bước 1: Chuẩn bị dữ liệu

Đọc Sellers, Order items, Orders, Products và Reviews. Kiểm tra schema/khóa/giá tiền, xóa trùng hoàn toàn, từ chối khóa mâu thuẫn và khóa ngoại lỗi. Gom review ở mức order trước khi nối để tránh nhân bản doanh số.

`SOURCE` nhận file SQLite hoặc thư mục CSV thô; không dùng file fact/dim sau ETL. Tự tìm chỉ khi có đúng một nguồn phù hợp. Chỉnh ô cấu hình dưới nếu không tự tìm được."""),
    code(step1),
    code('''import os

# Ví dụ Kaggle: Path("/kaggle/input/<dataset-folder>/olist.sqlite")
# Ví dụ máy cá nhân: Path("../data/raw/olist.sqlite")
# Hoặc Path("../data/raw/csv") nếu dùng CSV gốc.
SOURCE = Path(os.environ["OLIST_SOURCE"]) if os.environ.get("OLIST_SOURCE") else None
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
OUTPUT = Path("/kaggle/working/seller_segmentation") if Path("/kaggle/working").exists() else ROOT / "artifacts/seller_segmentation"

if SOURCE is None:
    candidates = []
    for base in [Path("/kaggle/input"), ROOT / "data/raw"]:
        if base.exists():
            candidates.extend(path for path in base.rglob("*") if path.suffix.lower() in {".sqlite", ".sqlite3", ".db"})
            for filename in ["sellers.csv", "olist_sellers_dataset.csv"]:
                candidates.extend(path.parent for path in base.rglob(filename))
    candidates = sorted(set(path.resolve() for path in candidates))
    if len(candidates) != 1:
        raise ValueError(f"Hãy đặt SOURCE tới nguồn Olist cần dùng. Tìm được {len(candidates)} nguồn: {candidates}")
    SOURCE = candidates[0]

tables, manifest = load_sources(SOURCE)
sales, sellers, audit = prepare_data(tables)
display(pd.DataFrame({"table": list(audit["source_rows"]), "rows": list(audit["source_rows"].values())}))
print("Eligible delivered item rows:", len(sales))
print("Multi-seller orders:", audit["multi_seller_orders"])
display(sales[["seller_id", "order_id", "price", "freight_value", "review_score"]].head())'''),
    md("""## Bước 2: Tạo đặc trưng

Gom item thành seller-order rồi mới tính chỉ số theo seller. Nhờ vậy đơn nhiều item không được cho trọng số review lớn hơn. Mốc tham chiếu chung = ngày sau ngày mua cuối trong cohort, không phụ thuộc ngày chạy.

**9 cột mô hình:** số đơn, giá trị đơn trung bình, số ngành hàng, tỷ lệ phí vận chuyển/giá hàng, điểm review trung bình, tỷ lệ giao trễ, số ngày giao trung bình, recency và tenure. Tổng giá hàng, số sản phẩm, địa lý và coverage giữ riêng để diễn giải. Không dùng ID làm đặc trưng số.

Tỷ lệ giao trễ chỉ dùng ngày hợp lệ; giao bất kỳ giờ nào trong ngày hẹn vẫn là đúng hạn. Giá hàng giữ BRL, thời gian tính ngày, tỷ lệ ở thang 0-1 (riêng phí/giá có thể lớn hơn 1)."""),
    code(step2),
    code('''profiles, excluded, details = create_features(sales, sellers)
audit.update(details)
audit["source_manifest"] = manifest
print("Eligible sellers:", len(profiles), "| Excluded sellers:", len(excluded))
print("Reference date:", audit["reference_date"])
display(profiles[["seller_id"] + MODEL_FEATURES].head())
display(profiles[MODEL_FEATURES].describe().T)
display(excluded.head())'''),
    md("""## Bước 3: Tiền xử lý dữ liệu

Điền thiếu bằng median, `log1p` các biến lệch phải rồi `StandardScaler` (z-score, phương sai tổng thể). Dừng nếu một đặc trưng thiếu toàn bộ. Không xóa hoặc clipping outlier tự động: DBSCAN cần có cơ hội nhận diện seller khác biệt. Lưu số ngoại lệ IQR để tham khảo.

Fit trên toàn bộ cohort để phân cụm mô tả. Chưa có bài toán dự báo/tập kiểm tra; nếu sau này dùng cohort mới, tái sử dụng các tham số đã lưu. Review và tỷ lệ trễ của seller ít đơn có độ tin cậy thấp; xem kèm số đơn và coverage khi diễn giải cụm."""),
    code(step3),
    code('''matrix, metadata = preprocess_features(profiles)
audit["model_shape"] = list(matrix.shape)
assert len(profiles) + len(excluded) == len(sellers)
assert profiles["seller_id"].tolist() == matrix.index.tolist()
assert profiles["item_count"].sum() == len(sales)
assert np.isclose(profiles["total_sales"].sum(), sales["price"].sum())
assert np.isclose(profiles["total_freight"].sum(), sales["freight_value"].sum())
assert np.isfinite(matrix.to_numpy()).all()
np.testing.assert_allclose(matrix.mean(), 0, atol=1e-10)
nonconstant = matrix.std(ddof=0) > 0
np.testing.assert_allclose(matrix.loc[:, nonconstant].std(ddof=0), 1, atol=1e-10)
export_results(profiles, excluded, matrix, audit, metadata, OUTPUT)
display(pd.DataFrame({"missing_before": metadata["missing_before_imputation"],
                      "iqr_outliers_retained": metadata["iqr_outlier_counts"],
                      "scaled_mean": matrix.mean(), "scaled_std": matrix.std(ddof=0)}))
print("Model shape:", matrix.shape)
print("All grain, total, ID alignment and finite-value checks passed.")
display(matrix.head())'''),
    code('''import matplotlib.pyplot as plt

fig, axes = plt.subplots(3, 3, figsize=(13, 9), constrained_layout=True)
for ax, feature in zip(axes.flat, MODEL_FEATURES):
    values = profiles[feature].fillna(metadata["medians"][feature])
    if feature in LOG_FEATURES:
        values = np.log1p(values)
    ax.hist(values, bins=30, color="#227c9d", edgecolor="white", linewidth=.3)
    ax.set_title(feature, fontsize=10)
    ax.set_xlabel("log1p" if feature in LOG_FEATURES else "Original scale")
    ax.set_ylabel("Sellers")
fig.suptitle("Feature distributions after imputation and log transform")
plt.show()

corr = matrix.corr()
fig, ax = plt.subplots(figsize=(10, 8), constrained_layout=True)
image = ax.imshow(corr, vmin=-1, vmax=1, cmap="RdBu_r")
ax.set_xticks(range(len(MODEL_FEATURES)), MODEL_FEATURES, rotation=55, ha="right", fontsize=9)
ax.set_yticks(range(len(MODEL_FEATURES)), MODEL_FEATURES, fontsize=9)
for row in range(len(MODEL_FEATURES)):
    for col in range(len(MODEL_FEATURES)):
        value = corr.iloc[row, col]
        ax.text(col, row, f"{value:.2f}", ha="center", va="center", fontsize=8,
                color="white" if abs(value) > .65 else "black")
fig.colorbar(image, ax=ax, shrink=.8)
ax.set_title("Correlation of model inputs")
plt.show()'''),
    md("""### Bàn giao cho bước huấn luyện

Các file được xuất vào `artifacts/seller_segmentation` (Kaggle: `/kaggle/working/seller_segmentation`).

- `seller_features.csv`: đặc trưng trước impute/log/scale, dùng diễn giải cụm.
- `seller_model_input.csv`: seller ID + 9 đặc trưng đã chuẩn hóa.
- `excluded_sellers.csv`: seller ngoài cohort và lý do.
- `preprocessing.json`: thứ tự cột, median/log/mean/scale, số thiếu/ngoại lệ và phiên bản.
- `data_quality.json`: hash nguồn, kiểm tra dữ liệu, thời gian và quy mô cohort.
- `feature_summary.csv`: thống kê mô tả.

Dùng **cùng ma trận và cùng thứ tự seller** để so sánh K-Means/GMM/DBSCAN. Không đưa `seller_id` vào X. Chưa có nhãn cụm hoặc kết luận phân khúc trong notebook này."""),
    code('''model_input = pd.read_csv(OUTPUT / "seller_model_input.csv")
seller_ids = model_input.pop("seller_id")
X = model_input.to_numpy()
np.testing.assert_allclose(X, matrix.to_numpy(), rtol=1e-8, atol=1e-8)
assert seller_ids.tolist() == profiles["seller_id"].tolist()
print(f"Ready for clustering: {X.shape[0]} sellers x {X.shape[1]} features")'''),
]
nbf.validate(nb)
nbf.write(nb, ROOT / "notebooks/seller_segmentation_preparation.ipynb")
print("Notebook generated from mining/seller_segmentation.py")
