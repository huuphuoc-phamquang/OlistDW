# Đề xuất đặc trưng cho Seller Segmentation (IS217 - Olist DW)

Tài liệu này gộp hai nguồn:
- file "Đề xuất đặc trưng cho Seller Segmentation (IS217 - Olist DW)", ngày 27/11/2026;
- danh sách đặc trưng bổ sung lấy được từ `OlistDW`, sau khi `fact_order_items` có trạng thái và mốc ngày đơn hàng (xem `docs/thay_doi_fact_order_items.md`).

Cột "Nguồn đề xuất" trong các bảng dùng 3 giá trị:
- **Đang dùng**: đã có trong `mining/seller_segmentation.py`.
- **Đề xuất (docx)**: lấy từ file đề xuất.
- **Bổ sung**: thêm mới trong tài liệu này.

Tên đặc trưng theo tên cột trong code. Một số đặc trưng trong file docx và `docs/agents_is217.md` có tên khác:
- `n_categories` là `category_count`;
- `HHI` là `category_hhi`;
- `freight_ratio` là `freight_to_price_ratio`;
- `pct_interstate` là `interstate_rate`;
- `avg_ship_distance` là `avg_ship_distance_km`.

Tất cả đặc trưng tính ở cấp `seller_id`. Các chỉ số theo đơn (thời gian giao, trễ hạn, review, thanh toán) phải gom về mức seller-đơn trước, để đơn nhiều món không bị tính nhiều lần.

## 1. Nguyên tắc chọn đặc trưng

- **Không one-hot khoảng 70 ngành hàng vào K-Means.** Ma trận thưa, nhiều chiều, khoảng cách Euclid mất ý nghĩa. Thay vào đó, biến ngành hàng thành số đo ở cấp ngành rồi tổng hợp có trọng số theo doanh thu về cấp seller.
- **Không đưa biến phân loại (bang, vùng, segment) vào K-Means.** Dùng sau khi phân cụm để mô tả cụm. Nếu bắt buộc phải đưa biến phân loại vào thì chuyển sang K-Prototypes.
- **Không đưa tất cả đặc trưng vào mô hình.** Danh sách dưới đây có khoảng 50 đặc trưng, nhiều cái đo cùng một thứ (quy mô, trễ hạn, độ phổ biến ngành). Khoảng cách Euclid sẽ lệch về nhóm có nhiều cột. Chọn khoảng 12-15 đặc trưng, mỗi nhóm 1-2 cái, sau khi kiểm tra tương quan (mục 11).
- **Xử lý phân phối lệch:** các chỉ số đếm, tiền, thời gian lệch phải mạnh nên dùng `log1p` rồi `StandardScaler`, như code hiện tại.
- **Seller ít đơn không ổn định:** 18% seller chỉ có 1 đơn, 28% có không quá 2 đơn. Tỷ lệ và trung bình của nhóm này dao động mạnh. Cân nhắc lọc theo số đơn tối thiểu hoặc phân cụm riêng.

## 2. Quy mô và tăng trưởng

| Đặc trưng | Mô tả | Nguồn trong `OlistDW` | Nguồn đề xuất |
|---|---|---|---|
| `order_count` | Số đơn đã giao có seller tham gia | `fact_order_items.order_id`, `order_status` | Đang dùng |
| `avg_order_value` | Tổng giá hàng của seller chia số đơn | `price`, `order_id` | Đang dùng |
| `total_sales` | Tổng giá hàng (BRL), chưa trừ chi phí | `price` | Đang dùng (chỉ để mô tả cụm) |
| `item_count`, `product_count` | Số món đã bán, số sản phẩm khác nhau | `order_item_id`, `product_id` | Đang dùng (chỉ để mô tả cụm) |
| `items_per_order` | Số món trung bình mỗi đơn | `order_item_id`, `order_id` | Bổ sung |
| `active_months` | Số tháng có ít nhất một đơn | `order_purchase_timestamp` | Đề xuất (docx) |
| `orders_per_active_month` | Số đơn trung bình mỗi tháng hoạt động | `order_purchase_timestamp`, `order_id` | Đề xuất (docx) |
| `sales_growth` | Doanh số 6 tháng cuối so với 6 tháng trước đó | `price`, `order_purchase_timestamp` | Bổ sung |
| `top_product_share` | Tỷ trọng doanh số của sản phẩm bán chạy nhất | `product_id`, `price` | Bổ sung |

## 3. Thời gian hoạt động

| Đặc trưng | Mô tả | Nguồn trong `OlistDW` | Nguồn đề xuất |
|---|---|---|---|
| `recency_days` | Số ngày từ lần bán cuối đến ngày tham chiếu | `order_purchase_timestamp` | Đang dùng |
| `tenure_days` | Số ngày từ lần bán đầu đến ngày tham chiếu | `order_purchase_timestamp` | Đang dùng, có trong docx |
| `weekend_sales_share` | Tỷ trọng doanh số đặt vào cuối tuần | `order_purchase_timestamp`, `price` | Bổ sung |
| `q4_sales_share` | Tỷ trọng doanh số quý 4 (mùa Black Friday) | `order_purchase_timestamp`, `price` | Bổ sung |

Ngày tham chiếu là ngày sau ngày mua cuối cùng trong tập đơn đủ điều kiện, không dùng ngày chạy code.

## 4. Giá

| Đặc trưng | Mô tả | Nguồn trong `OlistDW` | Nguồn đề xuất |
|---|---|---|---|
| `avg_item_price` | Giá trung bình một món | `price` | Bổ sung |
| `price_cv` | Hệ số biến thiên của giá (độ lệch chuẩn chia trung bình) | `price` | Bổ sung |
| `price_index` | Giá trung bình của seller chia giá trung bình của ngành, lấy trung bình có trọng số theo doanh thu. Lớn hơn 1 là định vị cao cấp | `price`, `dim_product.product_category_name` | Đề xuất (docx) |

## 5. Ngành hàng

Ký hiệu dùng chung:
- `rev(s,c)` = doanh thu của seller `s` trong ngành `c`.
- `w(s,c)` = `rev(s,c)` chia tổng doanh thu của seller `s`, là tỷ trọng doanh thu của seller trong từng ngành.

| Đặc trưng | Mô tả | Nguồn trong `OlistDW` | Nguồn đề xuất |
|---|---|---|---|
| `category_count` | Số ngành hàng khác nhau | `dim_product.product_category_name` | Đang dùng |
| `category_hhi` | Chỉ số tập trung HHI = tổng `w(s,c)` bình phương. Seller dồn 95% doanh thu vào 1 ngành có HHI khoảng 0,9; seller chia đều 5 ngành có HHI bằng 0,2 | như trên | Đề xuất (docx) |
| `category_entropy` | Entropy của `w(s,c)`, cùng ý nghĩa với HHI, chọn một trong hai | như trên | Đề xuất (docx) |
| `top_category_share` | `w(s,c)` lớn nhất, tức tỷ trọng ngành chính | như trên | Bổ sung |
| `hot_score` | Tổng `w(s,c)` nhân `cat_revenue_share(c)`, với `cat_revenue_share(c)` là doanh thu ngành chia tổng doanh thu toàn sàn (hoặc `cat_order_share` theo số đơn) | như trên | Đề xuất (docx) |
| `pct_rev_top10_cat` | Phần trăm doanh thu của seller đến từ Top 10 ngành, biến thể dễ giải thích của `hot_score` | như trên | Đề xuất (docx) |
| `growth_exposure` | Trung bình có trọng số của `cat_growth`, tức tăng trưởng doanh thu của ngành | như trên, cộng `order_purchase_timestamp` | Đề xuất (docx) |
| `competition_exposure` | Trung bình có trọng số của `cat_n_sellers`, số seller trong ngành | như trên | Đề xuất (docx) |
| `market_share_in_cat` | Doanh thu seller chia doanh thu ngành, lấy trung bình có trọng số. Tách "cá lớn ao nhỏ" khỏi "cá nhỏ ao lớn" | như trên | Đề xuất (docx) |
| `review_index` | Điểm review của seller chia điểm trung bình của ngành | `dim_review.review_score`, `dim_product` | Đề xuất (docx) |

Lưu ý khi tính:
- **HHI ít thông tin hơn mong đợi:** 55% seller chỉ bán 1 ngành nên HHI của họ đều bằng 1, trùng ý với `category_count`. Vẫn dùng được nhưng phải nêu rõ khi diễn giải.
- **`cat_growth` phải so cùng khoảng tháng.** Dữ liệu 2016 chỉ có vài tháng cuối năm, 2018 chỉ đến tháng 8. So cả năm 2017 với cả năm 2018 sẽ sai; nên so tháng 1-8 năm 2017 với tháng 1-8 năm 2018.
- **Nhóm này dễ trùng ý nhau.** `hot_score`, `pct_rev_top10_cat`, `competition_exposure` và `market_share_in_cat` đều xoay quanh độ lớn và độ phổ biến của ngành. Chỉ nên chọn 1-2 cái.
- **56 seller có `category_count = 0`** do sản phẩm không có tên ngành. Cần quyết định xếp vào một ngành "không rõ" hay bỏ khỏi các chỉ số ngành.
- **Phương án phụ:** lập ma trận tỷ trọng doanh thu seller × ngành, giảm xuống 3-5 chiều bằng TruncatedSVD hoặc NMF. Cách này giữ nhiều thông tin hơn nhưng khó đặt tên cụm, chỉ nên dùng để đối chiếu.

## 6. Giao hàng và vận hành

| Đặc trưng | Mô tả | Nguồn trong `OlistDW` | Nguồn đề xuất |
|---|---|---|---|
| `late_delivery_rate` | Tỷ lệ đơn giao sau ngày hẹn (so theo ngày) | `order_delivered_customer_date`, `order_estimated_delivery_date` | Đang dùng |
| `delivery_days_mean` | Thời gian trung bình từ lúc mua đến lúc giao | `order_delivered_customer_date`, `order_purchase_timestamp` | Đang dùng |
| `delivery_days_std` | Độ ổn định thời gian giao | như trên | Bổ sung |
| `promised_days_mean` | Số ngày hẹn giao trung bình kể từ lúc mua | `order_estimated_delivery_date`, `order_purchase_timestamp` | Bổ sung |
| `days_late_mean` | Số ngày trễ trung bình, chỉ tính các đơn trễ | ngày giao, ngày hẹn | Bổ sung |
| `days_early_mean` | Số ngày giao sớm hơn hẹn trung bình | ngày giao, ngày hẹn | Bổ sung |
| `cancel_rate` | Tỷ lệ đơn `canceled` hoặc `unavailable` | `order_status` | Bổ sung |
| `undelivered_rate` | Tỷ lệ đơn chưa giao (`shipped`, `invoiced`, `processing`, `approved`) | `order_status` | Bổ sung |
| `freight_to_price_ratio` | Tổng phí vận chuyển chia tổng giá hàng | `freight_value`, `price` | Đang dùng, có trong docx (`freight_ratio`) |
| `freight_per_item` | Phí vận chuyển trung bình mỗi món | `freight_value` | Bổ sung |

`cancel_rate` và `undelivered_rate` cần cả đơn không giao. Code hiện tại bỏ các đơn này trước khi tính đặc trưng, nên phải tách bước lọc ra.

## 7. Địa lý

Olist gần như không có dữ liệu nhân khẩu học của seller: chỉ có zip prefix, thành phố và bang. Vì vậy dùng đặc trưng địa lý và vận hành thay thế, và tách rõ cái nào đưa vào mô hình, cái nào chỉ để mô tả cụm.

| Đặc trưng | Mô tả | Nguồn trong `OlistDW` | Nguồn đề xuất |
|---|---|---|---|
| `avg_ship_distance_km` | Khoảng cách haversine trung bình từ seller đến khách | `dim_location.geolocation_lat/lng` của seller và customer | Đề xuất (docx) |
| `interstate_rate` | Tỷ lệ đơn giao khác bang | `dim_location.geolocation_state` | Đề xuất (docx) |
| `n_customer_states` | Số bang của khách, đo độ phủ thị trường | như trên | Đề xuất (docx) |
| `n_customer_cities` | Số thành phố của khách | `geolocation_city` | Bổ sung |
| `seller_state`, `seller_region` | Bang và vùng của seller (Sudeste, Sul, Nordeste, Norte, Centro-Oeste) | `dim_seller` nối `dim_location` | Đề xuất (docx), **chỉ để mô tả cụm** |
| `is_sp` | Cờ seller ở bang SP | như trên | Đề xuất (docx), **chỉ để mô tả cụm** |

Lưu ý khi tính:
- Trong 2.970 seller đủ điều kiện có 22 bang (file docx ghi 23), và 59,6% seller ở SP.
- Bảng geolocation gốc có nhiều dòng cho mỗi zip prefix. Trong `OlistDW` mỗi `location_id` đã có một tọa độ, nhưng nên kiểm tra lại trước khi tính khoảng cách.
- Zip không có tọa độ: lấy tọa độ trung tâm của thành phố hoặc bang.
- Tên thành phố không chuẩn (dấu, viết hoa, "sao paulo" và "são paulo") phải chuẩn hóa trước khi đếm.

## 8. Khách hàng và review

| Đặc trưng | Mô tả | Nguồn trong `OlistDW` | Nguồn đề xuất |
|---|---|---|---|
| `unique_customers` | Số khách thật theo `customer_unique_id` | `dim_customer` | Bổ sung |
| `repeat_customer_rate` | Tỷ lệ khách mua từ 2 đơn trở lên | `dim_customer.customer_unique_id` | Bổ sung |
| `review_score_mean` | Điểm review trung bình theo seller-đơn | `dim_review.review_score` | Đang dùng |
| `review_coverage` | Tỷ lệ đơn có review | `dim_review` | Đang dùng (chỉ để mô tả cụm) |
| `five_star_rate`, `low_star_rate` | Tỷ lệ review 5 sao, tỷ lệ review 1-2 sao | `review_score` | Bổ sung |
| `review_score_std` | Độ đồng đều của đánh giá | `review_score` | Bổ sung |
| `comment_rate` | Tỷ lệ review có viết bình luận | `review_comment_message` | Bổ sung |
| `review_answer_hours` | Số giờ từ lúc review được tạo đến lúc được phản hồi | `review_creation_date`, `review_answer_timestamp` | Bổ sung |

## 9. Thanh toán và sản phẩm

Thanh toán ghi ở mức đơn, nên seller trong đơn nhiều seller dùng chung thông tin thanh toán của đơn.

| Đặc trưng | Mô tả | Nguồn trong `OlistDW` | Nguồn đề xuất |
|---|---|---|---|
| `avg_installments` | Số kỳ trả góp trung bình | `fact_order_payment.payment_installments` | Bổ sung |
| `credit_card_rate`, `boleto_rate`, `voucher_rate` | Cơ cấu hình thức thanh toán của khách | `fact_order_payment.payment_type` | Bổ sung |
| `avg_weight_g`, `avg_volume_cm3` | Hàng nặng, cồng kềnh hay nhẹ | `dim_product.product_weight_g`, kích thước | Bổ sung |
| `avg_photos`, `avg_description_len` | Mức đầu tư vào trang sản phẩm | `dim_product.product_photos_qty`, `product_description_lenght` | Bổ sung |

## 10. Dữ liệu marketing funnel (chỉ để mô tả cụm)

| Đặc trưng | Mô tả | Nguồn trong `OlistDW` | Nguồn đề xuất |
|---|---|---|---|
| `business_segment`, `business_type`, `lead_type` | Thông tin lúc seller ký hợp đồng | `fact_seller_lead` | Đề xuất (docx) |
| `declared_monthly_revenue` | Doanh thu tháng seller tự khai | `fact_seller_lead` | Đề xuất (docx) |

File docx ước tính khoảng 840 seller có dữ liệu này (số lead thắng là 842). Trong `OlistDW` chỉ 380 seller vừa có lead thắng vừa có đơn bán, và `declared_monthly_revenue` của nhóm này đều bằng 0. Không impute rồi đưa vào phân cụm.

## 11. Bộ đặc trưng gợi ý đưa vào mô hình

Đây là bộ khởi đầu. Phải kiểm tra tương quan trên dữ liệu thật trước khi chốt.

| Nhóm | Đặc trưng | Ghi chú |
|---|---|---|
| Quy mô | `order_count`, `avg_order_value` | Đang dùng |
| Thời gian | `recency_days`, `tenure_days` | Đang dùng |
| Giao hàng | `late_delivery_rate`, `delivery_days_mean`, `cancel_rate` | `cancel_rate` cần cả đơn không giao |
| Review | `review_score_mean`, `low_star_rate` | |
| Ngành hàng | `category_count`, `category_hhi`, `price_index` | Bộ gọn của file docx còn có `hot_score`, `market_share_in_cat`; chọn thêm tối đa 1 cái |
| Địa lý | `avg_ship_distance_km` | |
| Khách hàng | `repeat_customer_rate` | |

So với 9 đặc trưng đang dùng:
- **Bỏ `freight_to_price_ratio`**, vì tương quan −0,75 với `avg_order_value`.
- **Theo dõi các cặp có tương quan trên 0,5:** `order_count` với `category_count` (0,59), `late_delivery_rate` với `delivery_days_mean` (0,50).

Các số tương quan trên tính từ `artifacts/seller_segmentation/seller_model_input.csv`. Các đặc trưng "Bổ sung" và "Đề xuất (docx)" chưa được tính thử trên dữ liệu thật.

## 12. Gắn kết quả phân cụm ngược vào SSAS

Sau khi có nhãn cụm:
- thêm `Seller Segment` và `Seller Region` làm attribute của `Dim Seller` trong cube `Olist DW`;
- viết thêm MDX slice và pivot theo phân khúc, ví dụ doanh thu theo Segment × Bang;
- trong báo cáo, nối phần data mining với phần OLAP thay vì để hai phần tách rời.
