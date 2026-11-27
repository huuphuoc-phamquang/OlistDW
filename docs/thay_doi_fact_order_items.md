# Thêm trạng thái và mốc ngày đơn hàng vào `fact_order_items`

## 1. Lý do thay đổi

- **Đề bài yêu cầu data mining chạy trên warehouse database.** Code phân khúc seller (`mining/seller_segmentation.py`) cần trạng thái đơn, ngày mua, ngày giao và ngày hẹn giao. Trước đây `OlistDW` không có các cột này, nên code phải đọc dữ liệu thô Kaggle thay vì đọc từ kho.
- **4 trong 9 đặc trưng phụ thuộc vào ngày:** `late_delivery_rate`, `delivery_days_mean`, `recency_days`, `tenure_days`. Ngoài ra, cả 9 đặc trưng chỉ tính trên đơn `delivered`, nên cần `order_status` để lọc.
- **Thêm cột vào `fact_order_items` thay vì tạo bảng `dim_order` mới.** Cách này ít thay đổi nhất: không thêm Data Flow, khóa ngoại hay dimension mới trong cube. Các cột này là thuộc tính của đơn hàng (degenerate dimension). Vì bảng có grain 1 dòng = 1 món hàng, giá trị của chúng lặp lại giữa các món trong cùng một đơn.
- **Chỉ lấy các cột mà đặc trưng cần.** `order_approved_at` và `order_delivered_carrier_date` chưa dùng nên chưa thêm.
- **Không sửa cube SSAS.** Cube không dùng các cột mới, nên deploy lại vẫn ra kết quả cũ.

## 2. File đã sửa

| File | Thay đổi |
|---|---|
| `notebooks/olist_preprocessing.ipynb` và 2 notebook Kaggle | Lấy thêm 4 cột từ `orders` khi tạo `fact_order_items` (11 cột thay vì 7) |
| `data/processed/fact_order_items.csv` | Sinh lại với 11 cột. Thư mục `data/` không đưa lên git, mỗi máy cần chạy lại notebook |
| `sql/01_create_tables.sql` | Thêm 4 cột vào `CREATE TABLE dbo.fact_order_items` |
| `ssis/Project/Package.dtsx` | `FF_Conn_FACT_ORDER_ITEMS` và `DFT_Load_FACT_ORDER_ITEMS`: thêm 4 cột vào Flat File Source và ánh xạ sang OLE DB Destination |

## 3. Danh sách cột của `fact_order_items`

| STT | Cột | Kiểu SQL | Kiểu SSIS | Mô tả | Ghi chú |
|---|---|---|---|---|---|
| 1 | `order_id` | NVARCHAR(255) | DT_WSTR(255) | Mã đơn hàng, cùng `order_item_id` làm khóa chính | Cũ |
| 2 | `order_item_id` | INT | DT_I4 | Thứ tự món hàng trong đơn | Cũ |
| 3 | `customer_id` | NVARCHAR(255) | DT_WSTR(255) | Khách mua, khóa ngoại tới `dim_customer` | Cũ |
| 4 | `seller_id` | NVARCHAR(255) | DT_WSTR(255) | Người bán, khóa ngoại tới `dim_seller` | Cũ |
| 5 | `product_id` | NVARCHAR(255) | DT_WSTR(255) | Sản phẩm, khóa ngoại tới `dim_product` | Cũ |
| 6 | `price` | MONEY | DT_CY | Giá món hàng (BRL) | Cũ |
| 7 | `freight_value` | MONEY | DT_CY | Phí vận chuyển của món hàng (BRL) | Cũ |
| 8 | `order_status` | NVARCHAR(50) | DT_WSTR(50) | Trạng thái đơn: `delivered`, `shipped`, `canceled`, `invoiced`, `processing`, `unavailable`, `approved` | **Mới** |
| 9 | `order_purchase_timestamp` | DATETIME | DT_DBTIMESTAMP | Thời điểm khách đặt mua | **Mới** |
| 10 | `order_delivered_customer_date` | DATETIME | DT_DBTIMESTAMP | Thời điểm giao tới khách. NULL nếu đơn chưa giao (2.454 dòng) | **Mới** |
| 11 | `order_estimated_delivery_date` | DATETIME | DT_DBTIMESTAMP | Ngày hẹn giao, giờ luôn là 00:00:00 | **Mới** |

Các cột 8 đến 11 là thuộc tính của đơn, lặp lại ở mọi món trong cùng đơn. Khi tính chỉ số theo đơn (thời gian giao, tỷ lệ trễ), phải gom về mức `order_id` (hoặc `seller_id` + `order_id`) trước khi lấy trung bình, nếu không đơn nhiều món sẽ bị tính nhiều lần.

## 4. Đặc trưng data mining và cột nguồn trong kho

Danh sách 9 đặc trưng giữ nguyên như trong `mining/seller_segmentation.py`. Cột "Cần cột mới" cho biết đặc trưng nào trước đây không tính được từ `OlistDW`.

| STT | Đặc trưng | Kiểu | Mô tả | Cột nguồn trong `OlistDW` | Cần cột mới |
|---|---|---|---|---|---|
| 1 | `order_count` | int | Số đơn đã giao có seller tham gia | `fact_order_items.order_id`, `order_status` | Có (lọc `delivered`) |
| 2 | `avg_order_value` | float (BRL) | Tổng giá hàng của seller chia số đơn | `price`, `order_id`, `order_status` | Có (lọc `delivered`) |
| 3 | `category_count` | int | Số ngành hàng khác nhau seller đã bán | `product_id` nối `dim_product.product_category_name` | Có (lọc `delivered`) |
| 4 | `freight_to_price_ratio` | float | Tổng phí vận chuyển chia tổng giá hàng | `freight_value`, `price` | Có (lọc `delivered`) |
| 5 | `review_score_mean` | float (1-5) | Điểm review trung bình theo seller-đơn | `dim_review.review_score`, `order_id` | Có (lọc `delivered`) |
| 6 | `late_delivery_rate` | float (0-1) | Tỷ lệ đơn giao sau ngày hẹn (so theo ngày) | `order_delivered_customer_date`, `order_estimated_delivery_date` | Có |
| 7 | `delivery_days_mean` | float (ngày) | Thời gian trung bình từ lúc mua đến lúc giao | `order_delivered_customer_date`, `order_purchase_timestamp` | Có |
| 8 | `recency_days` | int (ngày) | Số ngày từ lần bán cuối đến ngày tham chiếu | `order_purchase_timestamp` | Có |
| 9 | `tenure_days` | int (ngày) | Số ngày từ lần bán đầu đến ngày tham chiếu | `order_purchase_timestamp` | Có |

Các cột dùng để mô tả cụm (`seller_city`, `seller_state`) lấy từ `dim_seller` nối `dim_location`.

Code mining hiện vẫn đọc dữ liệu thô. Bước tiếp theo là sửa `load_sources` để đọc các bảng trên từ `OlistDW` (ví dụ qua `pyodbc`), rồi so kết quả với bản đọc dữ liệu thô.

## 5. Kiểm chứng

Đã chạy thử trên database tạm `OlistDW_t4`: `01_create_tables.sql`, package SSIS, rồi `02_post_load_checks.sql`.

| Kiểm tra | Kết quả |
|---|---|
| Package SSIS | `DTSER_SUCCESS` |
| Số dòng `fact_order_items` | 112.650 (không đổi) |
| `SUM(price)` / `SUM(freight_value)` | 13.591.643,70 / 2.251.909,54 (không đổi) |
| `order_status = 'delivered'` | 110.197 dòng, khớp `data_quality.json` của phần mining |
| `order_purchase_timestamp` NULL | 0 |
| `order_delivered_customer_date` NULL | 2.454 |
| Khoảng ngày mua | 2016-09-04 đến 2018-09-03 |
| Kiểm tra mồ côi trong `02_post_load_checks.sql` | 830, 725, 462 (không đổi) |

## 6. Áp dụng vào `OlistDW`

`OlistDW` đang dùng chưa có các cột mới. Muốn cập nhật:

1. Chạy notebook tiền xử lý (hoặc lấy file `fact_order_items.csv` 11 cột) vào `data/processed/`.
2. Chạy `sql/01_create_tables.sql`. Script này DROP và tạo lại toàn bộ bảng.
3. Chạy package SSIS, rồi `sql/02_post_load_checks.sql`.
4. Deploy hoặc process lại cube SSAS, vì dữ liệu nguồn đã được nạp lại.
