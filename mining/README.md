# Phân khúc nhà bán hàng Olist: bước 1-3 (Tzy)

Phần này chuẩn bị dữ liệu cho K-Means, GMM và DBSCAN. Nguồn vẫn là [Olist SQLite đã chọn](https://www.kaggle.com/datasets/terencicp/e-commerce-dataset-by-olist-as-an-sqlite-database). Đây là phần Data mining trong bảng phân công; chưa huấn luyện hay chọn mô hình phân cụm.

## Chạy notebook

Mở `notebooks/seller_segmentation_preparation.ipynb`, chỉnh `SOURCE` rồi **Run All**. Notebook chứa đầy đủ mã, chạy được khi tải riêng lên Kaggle/Colab. Trên Kaggle, Add Input dataset Olist SQLite rồi đặt `SOURCE` tới file `.sqlite` trong panel Input. Notebook tự tìm khi chỉ có một nguồn phù hợp trong `/kaggle/input` hoặc `data/raw`; nhiều nguồn cần chọn rõ để không dùng nhầm dữ liệu.

Hoặc chạy script từ thư mục gốc repo:

```bash
python -m pip install -r mining/requirements.txt
python mining/seller_segmentation.py --source data/raw/olist.sqlite
```

`--source` cũng nhận thư mục CSV thô (`sellers.csv`, `order_items.csv`, `orders.csv`, `products.csv`, `order_reviews.csv`), hoặc tên CSV Olist chuẩn `olist_*_dataset.csv`. Không dùng CSV fact/dim đã biến đổi vì thiếu các mốc ngày và có thể đã xử lý review theo cách khác.

## Bước 1: Chuẩn bị dữ liệu

Đọc 5 bảng trên, kiểm tra cột, khóa, bản ghi trùng, giá tiền và quan hệ. Xóa bản ghi trùng hoàn toàn; dừng khi khóa có nội dung mâu thuẫn hoặc khóa ngoại không khớp. Chỉ lấy đơn `delivered` có ngày mua hợp lệ để mô tả hoạt động bán hàng đã hoàn thành. Seller chưa có giao dịch phù hợp được xuất riêng, không gán doanh số 0 để đưa vào phân cụm.

Gom nhiều review của một đơn thành điểm trung bình trước khi nối. Tính chỉ số dịch vụ ở mức **seller-order** để một đơn nhiều sản phẩm không được tính nhiều lần. Mỗi seller trong đơn nhiều seller nhận cùng thông tin giao hàng/review của đơn: Olist không có đánh giá và thời điểm giao riêng cho từng seller. Đây là chỉ số đại diện, không phải đo chất lượng riêng seller một cách tuyệt đối.

## Bước 2: Tạo đặc trưng

Mỗi dòng đầu ra là một `seller_id`. Giá tiền giữ đơn vị gốc BRL, thời gian tính theo ngày. `total_sales` là tổng `price` hàng bán, chưa trừ chi phí và không phải lợi nhuận.

| Đặc trưng đưa vào mô hình | Định nghĩa |
|---|---|
| `order_count` | Số đơn đã giao có seller tham gia |
| `avg_order_value` | Tổng giá hàng của seller / số đơn của seller |
| `category_count` | Số ngành hàng khác nhau, không đếm category thiếu |
| `freight_to_price_ratio` | Tổng phí vận chuyển / tổng giá hàng; thiếu nếu mẫu số 0 |
| `review_score_mean` | Điểm review trung bình theo seller-order |
| `late_delivery_rate` | Tỷ lệ giao sau ngày hẹn, trên các seller-order có ngày hợp lệ |
| `delivery_days_mean` | Thời gian mua đến giao trung bình, bỏ khoảng thời gian âm/thiếu |
| `recency_days` | Số ngày từ lần bán cuối tới ngày tham chiếu chung |
| `tenure_days` | Số ngày từ lần bán đầu tới ngày tham chiếu chung |

Ngày tham chiếu là ngày sau ngày mua cuối cùng trong tập đơn đủ điều kiện, không dùng ngày chạy notebook. Giao bất kỳ giờ nào trong ngày hẹn đều tính đúng hạn. Ngày hẹn trước ngày mua, ngày giao trước lúc mua hoặc thiếu ngày không được tính là giao đúng hạn; mẫu số và số trường hợp lỗi được lưu để kiểm tra.

Các cột bổ sung (`total_sales`, `item_count`, `product_count`, tỷ lệ có review, số đơn có ngày hợp lệ, thành phố/bang...) giữ lại để diễn giải cụm. Không đưa `seller_id`, địa lý dạng chữ hoặc trực tiếp các cột doanh số/tổng sản phẩm có tính trùng lặp vào ma trận khoảng cách. `order_count` và `avg_order_value` vẫn cần xem tương quan khi đánh giá mô hình; 9 đặc trưng là bộ đầu vào ban đầu, không khẳng định đã tối ưu.

## Bước 3: Tiền xử lý dữ liệu

1. Chuyển đặc trưng sang số; giá trị không hữu hạn thành thiếu, từ chối số âm bất hợp lệ.
2. Điền thiếu bằng median từng cột, dừng nếu một cột thiếu toàn bộ.
3. Dùng `log1p` cho số đơn, giá trị đơn trung bình, số ngành hàng, tỷ lệ phí, thời gian giao, recency và tenure. Điểm review và tỷ lệ giao trễ giữ thang gốc trước chuẩn hóa.
4. Dùng `StandardScaler` cho tất cả 9 cột. Không tự xóa/clipping seller có quy mô lớn; lưu số ngoại lệ IQR để bước DBSCAN và đánh giá cụm có thể xem lại.

Fit tiền xử lý trên toàn bộ cohort để phân cụm mô tả dữ liệu lịch sử, không phải đánh giá dự báo. Khi đánh giá trên cohort mới, phải dùng lại median/mean/scale đã lưu; không fit lại trên tập đánh giá. Seller ít đơn có review/tỷ lệ trễ kém ổn định; cần xem cùng `order_count` và các cột coverage khi đặt tên cụm.

## Đầu ra và bàn giao

Kết quả chạy thực tế nằm trong `artifacts/seller_segmentation/`:

| File | Sử dụng |
|---|---|
| `seller_features.csv` | Dữ liệu theo seller, trước điền thiếu/log/scale, dùng diễn giải cụm |
| `seller_model_input.csv` | `seller_id` + 9 cột đã chuẩn hóa, dùng chung cho cả 3 thuật toán |
| `excluded_sellers.csv` | Seller ngoài cohort và lý do |
| `preprocessing.json` | Thứ tự cột, median, log1p, mean/scale, số thiếu/ngoại lệ, phiên bản thư viện |
| `data_quality.json` | Hash nguồn, số dòng, phạm vi thời gian, kiểm tra chất lượng và cohort |
| `feature_summary.csv` | Thống kê mô tả đặc trưng trước tiền xử lý |

```python
import pandas as pd
model_input = pd.read_csv("artifacts/seller_segmentation/seller_model_input.csv")
seller_ids = model_input.pop("seller_id")
X = model_input.to_numpy()  # cùng X, cùng thứ tự seller cho K-Means/GMM/DBSCAN
# Chưa gán nhãn cụm ở bước 1-3.
```

Notebook có bảng kiểm tra, histogram sau biến đổi log và heatmap tương quan. Mã dùng chung nằm ở `mining/seller_segmentation.py`; nếu sửa mã, chạy `python mining/build_notebook.py` để đồng bộ notebook rồi Run All trước khi commit.

## Kiểm tra

```bash
python -m unittest discover -s mining -p "test_*.py" -v
```

Kiểm tra nhiều review không nhân doanh số, đơn nhiều item không làm lệch trung bình review/tỷ lệ trễ, giao trong ngày hẹn, ngày sai, khóa lỗi, khôi phục phép chuẩn hóa và kết quả đọc CSV/SQLite tương đương. Khi chạy dữ liệu thật, đối chiếu tổng giá hàng/phí vận chuyển ở mức item với bảng seller và kiểm tra seller ID thẳng hàng với ma trận mô hình.
