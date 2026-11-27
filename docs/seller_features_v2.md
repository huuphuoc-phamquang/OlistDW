# Định nghĩa đặc trưng seller phiên bản 2

Triển khai đề xuất của leader ngày 27/11/2026 trong `mining/seller_features_extended.py`. Bảng đầu ra có 82 cột, bao gồm ID, đặc trưng, metadata và cờ kiểm chứng; không phải 82 cột đưa vào mô hình.

## Nguồn và mức chi tiết

Đọc CSV thô tại `D:\IS217\csv\csv` trong lần chạy kiểm chứng, giữ nguyên 112.650 order items và 99.441 orders. Không phụ thuộc việc fact_order_items trên máy đã được bổ sung ngày/trạng thái hay chưa. CSV thô có đủ các trường cần dùng; hash cả chín nguồn được lưu trong `data_quality.json`. Có thể đọc SQLite tương đương.

Doanh số, ngành hàng, giá và kích thước sản phẩm dùng 110.197 item thuộc 96.478 đơn delivered có ngày mua hợp lệ. Chỉ số theo đơn được gom thành seller–order trước khi lấy trung bình. Một đơn nhiều seller chia sẻ thông tin review, giao hàng, khách và phương thức thanh toán; không thể suy ra chất lượng riêng từng seller từ các trường đó.

Mẫu số `cancel_rate` và `undelivered_rate` là toàn bộ đơn có item gắn được seller, gồm cả đơn chưa giao. Các đơn hủy không có item không thể quy cho một seller. Ngày tham chiếu chung là 30/08/2018, lấy ngày sau ngày mua cuối trong cohort, không phải ngày chạy code.

## Định nghĩa theo nhóm

| Nhóm | Cột | Quy tắc |
|---|---|---|
| Quy mô | order_count, total_sales, item_count, product_count | Đếm đơn distinct, cộng price, đếm item, đếm product distinct trên delivered |
| Giá trị đơn | avg_order_value, items_per_order | Tổng giá hàng hoặc số item chia số seller–order |
| Hoạt động | active_months, orders_per_active_month | Đếm tháng có đơn, số đơn chia số tháng hoạt động |
| Tăng trưởng seller | sales_growth | Doanh số [02/2018,08/2018) / [08/2017,02/2018) − 1; thiếu nếu giai đoạn gốc bằng 0 |
| Sản phẩm chủ lực | top_product_share | Doanh số sản phẩm lớn nhất / tổng doanh số seller |
| Thời gian | recency_days, tenure_days | Ngày tham chiếu trừ ngày bán cuối/đầu |
| Mùa vụ | weekend_sales_share, q4_sales_share | Tỷ trọng doanh số cuối tuần hoặc quý 4 trên toàn lịch sử; chưa điều chỉnh số tháng quan sát |
| Giá | avg_item_price, price_cv | Trung bình giá item; std dân số của giá / mean |
| So giá ngành | price_index | Tổng w(s,c) × giá item trung bình seller-ngành / giá item trung bình ngành |
| Số ngành | category_count, known_category_count | Count distinct gồm `__unknown__`; cột known giữ cách đếm bỏ thiếu của baseline |
| Tập trung | category_hhi, category_entropy, top_category_share | Tổng w², −tổng w ln(w), max(w); w là tỷ trọng doanh thu seller theo ngành |
| Độ phổ biến | hot_score, pct_rev_top10_cat | Tổng w × tỷ trọng doanh thu ngành; tổng w trong 10 ngành có doanh thu lớn nhất |
| Vị thế ngành | market_share_in_cat, competition_exposure | Tổng w × doanh thu seller-ngành/doanh thu ngành; tổng w × số seller ngành |
| Tăng trưởng ngành | growth_exposure | Tổng có trọng số cat_growth của tháng 1–7 năm 2018 so cùng tháng năm 2017; chuẩn hóa lại trọng số trên ngành tính được |
| Coverage tăng trưởng | growth_exposure_coverage | Tổng w của ngành có mẫu số gốc dương; ngành không có doanh số gốc không gán tăng trưởng bằng 0 |
| Review ngành | review_index | Review trung bình seller–order–ngành chia review trung bình order–ngành; tổng hợp theo w và chuẩn hóa lại trên ngành có review |
| Giao hàng | late_delivery_rate, delivery_days_mean, delivery_days_std | Trễ so theo ngày; thời gian mua đến giao theo ngày liên tục; std mẫu theo seller–order |
| Cam kết | promised_days_mean | Chênh lệch ngày lịch từ ngày mua đến ngày hẹn, loại thời gian âm |
| Mức trễ/sớm | days_late_mean, days_early_mean | Trung bình số ngày lịch trễ chỉ trên đơn trễ; sớm chỉ trên đơn sớm; thiếu nếu không có đơn phù hợp |
| Trạng thái | cancel_rate, undelivered_rate | Tỷ lệ canceled/unavailable; tỷ lệ shipped/invoiced/processing/approved trên toàn bộ seller–order có item |
| Phí | freight_to_price_ratio, freight_per_item | Tổng phí / tổng giá; tổng phí / item_count; phí/giá không vào mô hình v2 |
| Khoảng cách | avg_ship_distance_km | Haversine seller–customer centroid theo seller–order; bán kính Trái Đất 6371,0088 km |
| Khác bang | interstate_rate | Tỷ lệ seller–order có bang khách khác bang seller, chỉ khi biết cả hai bang |
| Độ phủ | n_customer_states, n_customer_cities | Đếm bang; đếm cặp bang + tên thành phố đã chuẩn hóa |
| Vùng seller | seller_state, seller_region, is_sp | 5 vùng Brazil; cờ SP; chỉ mô tả |
| Khách hàng | unique_customers, repeat_customer_rate | Count customer_unique_id; số khách có ≥2 đơn seller chia số khách distinct |
| Review | review_score_mean, review_score_std | Mỗi order gom trung bình review trước; mean và std dân số của các seller–order có review |
| Mức sao | five_star_rate, low_star_rate | Tỷ lệ 5 sao hoặc 1–2 sao trong mỗi order, rồi trung bình theo seller–order có review; tránh item weighting |
| Bình luận | comment_rate | Tỷ lệ review có nội dung không rỗng trong mỗi order rồi trung bình theo seller–order có review |
| Thời gian review | review_answer_hours | Mean chênh lệch answer timestamp − creation timestamp không âm, gom order trước; không diễn giải là thời gian seller trả lời khách |
| Trả góp | avg_installments | Trung bình số kỳ trong order, sau đó trung bình seller–order có dữ liệu |
| Hình thức trả | credit_card_rate, boleto_rate, voucher_rate | Tỷ lệ order có sử dụng hình thức đó; nhiều hình thức trong một đơn nên các tỷ lệ không nhất thiết cộng bằng 1 |
| Sản phẩm | avg_weight_g, avg_volume_cm3, avg_photos, avg_description_len | Trung bình theo item bán; volume là dài × cao × rộng khi đủ ba số không âm |
| Marketing | business_segment, business_type, lead_type, declared_monthly_revenue | Lead thắng mới nhất theo won_date, tie-break mql_id; không impute, chỉ mô tả |

Ngành thiếu không làm mất doanh thu khi tính trọng số: thêm `__unknown__`, lưu `unknown_category_share`. Có 56 seller chỉ bán sản phẩm thiếu ngành. Có 1.596 seller chỉ có một nhóm ngành sau quy tắc này; HHI/entropy ít khả năng phân biệt nhóm đó.

## Địa lý và chất lượng

Gom median lat/lng theo zip prefix, không join trực tiếp bảng hơn một triệu dòng vào orders. Chuẩn hóa tên thành phố bằng chữ thường, bỏ dấu Unicode và khoảng trắng thừa. Loại 33 dòng tọa độ nằm ngoài khung Brazil lat [−34,6], lng [−74,−34] trước khi gom median; đây là lọc khung bao, không phải kiểm tra biên giới polygon.

Fallback theo thành phố trong cùng bang, rồi theo bang; các trung tâm fallback dùng median của các median zip, tránh zip có nhiều bản ghi chi phối. Kết quả: 3.088 seller lấy được tọa độ zip, 7 seller dùng city; khách hàng gồm 99.162 zip, 221 city, 58 state. Không còn seller–order trong cohort thiếu khoảng cách. Khoảng cách là đường chim bay từ centroid, không phải quãng đường thực giao.

Các cột coverage và số mẫu gồm review_coverage, reviewed_order_count, valid_delivery_order_count, valid_deadline_order_count, distance_coverage, payment_coverage, growth_exposure_coverage. Ngày sai/thiếu không được tính là giao đúng hạn. Có 8 seller–order thiếu ngày giao/hẹn hợp lệ trong dữ liệu thật.

Đối chiếu marketing có 380 seller vừa có lead thắng vừa có bất kỳ item bán; khi giới hạn delivered còn 376. Cả 376 giá trị declared_monthly_revenue đều bằng 0. Khác biệt với con số 380 trong đề xuất là do cohort, không phải thiếu join.

## Chọn đặc trưng và tiền xử lý

Mô hình chính yêu cầu ≥3 đơn delivered: 2.129 seller. 841 seller dưới ngưỡng giữ riêng; 125 seller không có giao dịch đủ điều kiện giữ lý do loại. Ngưỡng là lựa chọn triển khai để giảm tỷ lệ/mean quá nhiễu, chưa phải quyết định nghiệp vụ cuối cùng. Đã xuất ma trận sensitivity cho toàn bộ 2.970 seller.

15 ứng viên lấy theo mục 11 của đề xuất, cộng hot_score. Fit median trên cohort; log1p số đơn, giá trị đơn, recency, tenure, thời gian giao, số ngành, price_index, khoảng cách. Tính tương quan trên dữ liệu sau biến đổi, giữ đại diện có ưu tiên diễn giải và loại |r| ≥ 0,75. Sau đó StandardScaler trên 12 cột giữ lại.

| Cặp | Pearson | Quyết định |
|---|---:|---|
| avg_order_value – price_index | 0,8815 | Giữ avg_order_value |
| review_score_mean – low_star_rate | −0,9044 | Giữ review_score_mean |
| category_count – category_hhi | −0,8184 | Giữ category_count |
| late_delivery_rate – delivery_days_mean | 0,5549 | Giữ cả hai, ghi nhận tương quan trung bình |

Bộ cuối: order_count, avg_order_value, recency_days, tenure_days, late_delivery_rate, review_score_mean, category_count, avg_ship_distance_km, repeat_customer_rate, cancel_rate, hot_score, delivery_days_mean. Các cột loại vẫn còn trong bảng profile, không xóa khỏi phân tích.

Không clipping/xóa outlier tự động, không đưa địa lý dạng chữ hay marketing vào khoảng cách. Cả hai scaler main/all đều được lưu riêng. Fit toàn lịch sử phục vụ phân cụm mô tả; không gọi đây là đánh giá dự báo ngoài mẫu.
