# Bàn giao công việc Tzy ngày 27 tháng 11 năm 2026

## Kết quả

Đã thực thi đề xuất đặc trưng của leader, hoàn thiện Data mining bước 1–3 và phần K-Means bước 4 của Tzy trên nhánh `tzy/seller-features-kmeans`. Các kết quả dưới đây được chạy từ dữ liệu trên máy, không phải số liệu minh họa.

| Phần Tzy | Đã hoàn thành | Minh chứng |
|---|---|---|
| SSIS | Chạy thành công, 9/9 bảng khớp CSV, tổng tiền và 6 FK đạt; Word 7 trang có ảnh và lỗi ở cuối | Báo cáo `C:\Users\ACER\Documents\ChatGPT\IS217\outputs\ssis_tzy_20261127\Bao_cao_SSIS_Tzy_20261127.docx` |
| DM bước 1 | Kiểm tra khóa, grain, dates, customer/geo/payment/marketing; giữ đơn chưa giao cho cancel_rate | `mining/seller_features_extended.py`, `artifacts/seller_segmentation_v2/data_quality.json` |
| DM bước 2 | Tính các nhóm đặc trưng trong đề xuất, raw profile gồm 82 cột cả metadata và cờ kiểm tra | `artifacts/seller_segmentation_v2/seller_features.csv` |
| DM bước 3 | Phân tích tương quan, chọn 12 cột, median/log1p/StandardScaler, cohort chính và sensitivity | `seller_model_input.csv`, `preprocessing.json`, `seller_model_input_all.csv` trong thư mục v2 |
| DM bước 4 K-Means | Quét k=2..10, Elbow/Silhouette/DB/CH, kiểm tra 10 seed, kiểm tra độ nhạy cohort | `artifacts/seller_kmeans/` |
| Notebook | Hai notebook v2 và K-Means đã Run All, lưu bảng và biểu đồ | `notebooks/seller_segmentation_features_v2.ipynb`, `notebooks/seller_segmentation_kmeans.ipynb` |
| Nối OLAP | Mapping đủ 3.095 seller; SQL nạp Segment/Region; thêm attribute trong source SSAS và 3 MDX mẫu | `load_seller_segments.sql`, source Dim Seller/DSV/cube, `ssas/mdx/04_seller_segments.mdx` |

Hai notebook chứa mã đầy đủ. Giữ notebook baseline cũ làm đối chiếu; bộ dữ liệu v2 và kết quả K-Means nằm trong thư mục mới, không ghi đè artifacts baseline.

## Quy mô và kết quả K-Means

Từ 3.095 seller gốc, 2.970 seller có đơn delivered hợp lệ. Cohort chính gồm 2.129 seller có ≥3 đơn, giữ 97,997% tổng giá hàng delivered. Ngày tham chiếu 30/08/2018. Tổng price delivered là 13.221.498,11 BRL; trong cohort chính là 12.956.722,45 BRL. Các tổng này khác tổng SSIS toàn bộ trạng thái vì khác phạm vi đơn.

Chọn **k=5** trong các k có mọi cụm ≥2% cohort, tối đa hóa Silhouette. K=6 có Silhouette cao hơn (0,1546) nhưng tạo cụm chỉ 23 seller (1,08%), nên không đạt điều kiện kích thước đã đặt. Elbow giảm dần, không có cơ sở khẳng định điểm khuỷu sắc nét tại k=5.

| Chỉ tiêu k=5 | Giá trị |
|---|---:|
| Silhouette trên toàn cohort | 0,1480 |
| Davies–Bouldin | 1,7542 |
| Calinski–Harabasz | 277,8997 |
| ARI nhỏ nhất trong 10 seed với seed 42 | 0,9972 |
| ARI trung bình trong 10 seed | 0,9983 |
| ARI trên seller chung khi giữ cả seller ít đơn, cùng k | 0,5584 |
| Phương sai được giữ bởi PCA 2D | 36,17% |

Silhouette thấp cho thấy các cụm còn chồng lấn. ARI gần 1 giữa seed chỉ xác nhận tối ưu K-Means ổn định, không chứng minh phân khúc kinh doanh mạnh. ARI sensitivity 0,5584 cho thấy kết quả phụ thuộc đáng kể vào cách chọn cohort và fit scaler.

| Cụm ứng viên | Seller | Số đơn trung vị | Tỷ trọng giá hàng cohort | Điểm cần leader xem |
|---|---:|---:|---:|---|
| C0 | 55 | 6 | 0,58% | Tỷ lệ hủy trung bình theo seller 18,35%; nhóm nhỏ, tỷ lệ dễ nhiễu |
| C1 | 647 | 9 | 11,96% | Recency trung vị 144 ngày, cần xem khả năng giảm hoạt động |
| C2 | 532 | 7 | 5,76% | Tenure trung vị 105,5 ngày, recency 14 ngày |
| C3 | 240 | 7 | 5,36% | Review mean theo seller 3,52; late rate mean 25,02% |
| C4 | 655 | 62 | 76,35% | Quy mô bán cao hơn, recency trung vị 12 ngày |

Đây là mô tả số liệu, chưa gán tên nghiệp vụ chính thức. Bảng trung bình và trung vị đầy đủ đã xuất để leader dùng khi đối chiếu GMM/DBSCAN và đặt tên.

## Giả định đã dùng

Dùng nguồn CSV thô để bảo toàn ngày/trạng thái và nhiều review của một đơn; không phụ thuộc schema fact mới. Chọn min_orders=3 làm mô hình chính, giữ toàn bộ seller trong profile/mapping và chạy sensitivity toàn cohort. Chọn tương quan tuyệt đối ≥0,75 để loại cột trùng mạnh, theo dõi >0,5. Thiếu ngành đưa vào `__unknown__`, đồng thời giữ số ngành đã biết.

Tăng trưởng seller dùng hai giai đoạn sáu tháng đã đủ quan sát, kết thúc trước tháng 8/2018. Tăng trưởng ngành so tháng 1–7/2017 với 1–7/2018 để tránh tháng 8 cuối chưa đủ ngày. Không đưa growth_exposure hay marketing vào mô hình chính. Tiền xử lý là mô tả lịch sử, không đánh giá dự báo.

## Vấn đề và kiểm chứng

10 kiểm thử tự động đã đạt: khóa lỗi, join không nhân dòng, thời gian giao sai, chuẩn hóa khôi phục được, CSV/SQLite baseline tương đương, mẫu số cancel, review/payment theo order, khách quay lại, ngành thiếu, median địa lý và fallback, seller doanh thu bằng 0 không có HHI/entropy giả. Hai notebook có tổng 10 code cell đã chạy thành công, không có output lỗi. Kiểm tra số hữu hạn, mean 0, std 1 và khôi phục scaler cũng chạy trong notebook.

Mapping SQL đã chạy trên `OlistDW_SSIS_Tzy_20261127`, đủ 3.095 seller, không có mapping thiếu. Kiểm tra XML xác nhận Seller Segment và Seller Region trỏ đúng cột DSV và được khai báo trong cube. **Chưa build/deploy/Process Full hoặc chạy MDX trên SSAS:** máy hiện chỉ có dịch vụ MSSQLSERVER, không có dịch vụ SSAS. Không coi kiểm tra XML là bằng chứng cube đã triển khai.

376 seller có marketing trong cohort delivered, khác 380 khi dùng mọi seller có item; đã đối chiếu trực tiếp. Declared monthly revenue của 376 seller đều bằng 0. Review/giao hàng thuộc cả đơn; thời gian answer của review không phải KPI seller phản hồi. Cancel rate không đếm được đơn không có item xác định seller. Địa lý là khoảng cách centroid, không phải đường vận chuyển.

## Bàn giao

Phu0c chạy GMM và DBSCAN trên **cùng `artifacts/seller_segmentation_v2/seller_model_input.csv`**, cùng thứ tự seller, để kết quả so sánh có ý nghĩa. Sau khi chọn mô hình cuối, cập nhật mapping và tên phân khúc theo số liệu; radar chart, lựa chọn mô hình cuối và chính sách là phần bước 5–6 của leader theo bảng phân công.

Để thử OLAP trên máy có SSAS: nạp mapping bằng `sqlcmd -S <server> -E -b -d <database_đích> -i artifacts/seller_kmeans/load_seller_segments.sql`; kiểm tra kết quả; chỉnh Data Source/Deployment đúng máy; build, deploy, Process Full source SSAS đã cập nhật; chạy `04_seller_segments.mdx`. Các nhãn hiện là `KMeans C0..C4`, không phải mô hình cuối. Nếu chạy lại script tạo bảng, phải nạp lại mapping trước Process Full.

Ghi chú để leader cập nhật tab St: SSIS kiểm chứng xong; DM bước 1–3 cập nhật theo đề xuất mới xong, chờ leader review; K-Means bước 4 xong, chờ so sánh. 10 câu MDX đã chọn và báo cáo Power BI của Tzy chưa được thực hiện trong lượt này; cần đầu vào/cube đã sẵn sàng. Không tự đánh dấu toàn bộ đồ án của Tzy đã hoàn tất.

Mã và kết quả bàn giao nằm trên nhánh tzy/seller-features-kmeans. Trạng thái trong Google Sheet cần leader cập nhật theo kết quả review.
