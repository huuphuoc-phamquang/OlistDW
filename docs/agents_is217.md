# agents_is217.md — Context cho agents đồ án IS217 (Olist DW)

> File context chung cho mọi agent làm việc trên đồ án. Đọc hết file này trước khi làm bất kỳ task nào.
> Nếu thông tin ở đây mâu thuẫn với code trong repo, **code trong repo là nguồn đúng**: báo lại cho người điều phối và cập nhật file này.

---

## 1. Tổng quan dự án

| Mục | Giá trị |
|---|---|
| Môn | IS217 – Kho dữ liệu và OLAP |
| Đề tài | Xây dựng Data Warehouse cho Olist (e-commerce Brazil), phân tích OLAP và khai phá dữ liệu |
| Repo | https://github.com/huuphuoc-phamquang/OlistDW |
| Phân công | Google Sheet "(IS217) Phân công": tab `St` (task), tab `mdx` (câu truy vấn) |
| Dữ liệu gốc | Kaggle "E-commerce dataset by Olist as an SQLite database" (terencicp) |
| Thành viên | **Phu0c** (leader), **Tzy** |
| Deadline chính | 30/11/2026 (SSAS cube, report BI/Excel, MDX) |

Stack: SQL Server (DW) → SSIS (ETL) → SSAS Multidimensional (cube `[Olist DW]`) → MDX → Power BI + Excel. Data mining viết bằng Python (Jupyter, pandas, scikit-learn).

---

## 2. Trạng thái task (theo sheet phân công, cập nhật 27/11/2026)

| Task | Người làm | DL | Trạng thái |
|---|---|---|---|
| Data preprocessing | Phu0c | – | Xong |
| SSIS | Tzy | 25/11 | Đang kiểm lại |
| SSAS: tạo cube | Phu0c | 30/11 | Chưa xong |
| Chọn lại 10 truy vấn MDX, thao tác bằng tay | Phu0c | 30/11 | Chưa xong |
| Chạy 10 câu MDX | Tzy | – | Chưa xong |
| Report trên Power BI | Tzy | 30/11 | Chưa xong |
| Report trên Excel | Phu0c | – | Chưa xong |
| DM bước 1–3 (chuẩn bị dữ liệu, tạo đặc trưng, tiền xử lý) | Tzy | 26/11 | Đã làm, **leader cần check lại** |
| DM bước 4: K-Means (Elbow + Silhouette) | Tzy | 28/11 | Chưa xong |
| DM bước 4: GMM (BIC/AIC + Silhouette) | Phu0c | 28/11 | Chưa xong |
| DM bước 4: DBSCAN (k-distance chọn eps) | Phu0c | 28/11 | Chưa xong |
| DM bước 5–6: so sánh, PCA 2D, radar, đặt tên phân khúc, đề xuất chính sách | Phu0c | 28/11 | Chưa xong |
| Chụp lại notebook | Cả 2 | – | Chưa xong |

Lưu ý: sheet ghi "4 thuật toán phân cụm" nhưng chỉ liệt kê 3 (K-Means, GMM, DBSCAN). Agent không tự thêm thuật toán thứ 4; hỏi lại người điều phối.

---

## 3. Cấu trúc cube `[Olist DW]` (suy ra từ các câu MDX đã viết)

Khi viết MDX, dùng **đúng tên** dưới đây. Nếu deploy báo lỗi tên, mở cube trong SSDT để đối chiếu rồi sửa file này.

**Dimensions và hierarchy**

| Dimension | Hierarchy / Attribute | Level |
|---|---|---|
| `[Dim Location]` | `[Location Hierarchy]` | `[Geolocation State]` → `[Geolocation City]` (key city dạng `&[SP]&[campinas]`) |
| `[Dim Product]` | `[Product Hierarchy]` | `[Product Category Name]` → sản phẩm (`.CHILDREN`) |
| `[Dim Payment Type]` | `[Payment Type]` | `[Payment Type]` (vd `&[credit_card]`, `&[boleto]`) |
| `[Dim Lead Origin]` | `[Origin]` | `[Origin]` |
| `[Dim Contact Date]` | `[Contact Date Hierarchy]` | `[Contact Year]` → tháng |

**Measures**

| Nhóm fact | Measures |
|---|---|
| Order items | `[Price]`, `[Freight Value]`, `[Fact Order Items Count]` |
| Payments | `[Payment Value]`, `[Payment Count]` |
| Marketing funnel (leads) | `[Lead Count]`, `[Won Leads]`, `[Declared Monthly Revenue]` |

Calculated members đã dùng: `[Avg Price]` = Price / Fact Order Items Count; `[Ty Le Thang]` = Won Leads / Lead Count; `[Luy Ke Price]` (lũy kế theo RANK).

**Bộ MDX hiện có:** Q1–Q23 trong tab `mdx`, phân loại Roll-up, Drill-down, Slice, Dice, Pivot. Cần chọn ra **10 câu** cho báo cáo, ưu tiên phủ đủ 5 loại thao tác và đủ 3 nhóm fact.

---

## 4. Data mining: Seller Segmentation

**Mục tiêu:** phân khúc nhà bán hàng (seller) của Olist, đặt tên từng phân khúc và đề xuất chính sách quản trị.

**Quy trình 6 bước** (giữ đúng thứ tự trong sheet):

1. Chuẩn bị dữ liệu (join order_items, orders, products, sellers, reviews, geolocation).
2. Tạo đặc trưng cấp seller.
3. Tiền xử lý: `log1p` cho biến lệch phải, chuẩn hóa (StandardScaler/RobustScaler), kiểm tra tương quan.
4. Huấn luyện K-Means, GMM, DBSCAN.
5. Đánh giá, so sánh (Silhouette, Davies-Bouldin, Calinski-Harabasz), trực quan bằng PCA 2D.
6. Chọn mô hình tốt nhất, bảng trung bình/trung vị và radar chart từng cụm, đặt tên phân khúc, đề xuất chính sách.

**Đặc trưng ngành hàng đã thống nhất đề xuất** (thay cho one-hot category):

| Đặc trưng | Ý nghĩa |
|---|---|
| `n_categories` | Số ngành seller tham gia |
| `hot_score` | Trung bình có trọng số (theo doanh thu seller) của tỉ trọng doanh thu ngành |
| `HHI` (hoặc entropy) | Mức tập trung doanh thu của seller theo ngành |
| `market_share_in_cat` | Thị phần của seller trong ngành, trung bình có trọng số |
| `price_index` | Giá TB của seller / giá TB của ngành |
| `growth_exposure` (tùy chọn) | Mức tiếp xúc với ngành đang tăng trưởng; chưa chốt có đưa vào không |

**Đặc trưng địa lý/vận hành:**

1. Đưa vào phân cụm: `avg_ship_distance` (haversine), `pct_interstate`, `freight_ratio`, `n_customer_states`, `tenure_days`, `orders_per_active_month`.
2. **Chỉ dùng mô tả cụm, không đưa vào K-Means:** vùng (5 vùng Brazil / `is_SP`), dữ liệu `closed_deals` (chỉ ~840/~3.000 seller có).

**Bẫy dữ liệu:**

1. `geolocation` nhiều dòng mỗi zip prefix → lấy median lat/lng theo prefix trước khi join.
2. Zip không có tọa độ → fallback tọa độ trung tâm city/state.
3. Tên city không chuẩn (dấu, hoa thường, "sao paulo"/"são paulo") → chuẩn hóa.
4. Seller quá ít đơn (vd < 3 đơn) làm nhiễu → quyết định lọc hay giữ phải ghi rõ trong notebook.

**Gắn ngược vào cube:** sau khi có nhãn, thêm `Seller Segment`, `Seller Region` làm attribute của Dim Seller để viết MDX theo phân khúc.

---

## 5. Danh sách agent và phạm vi

Mỗi agent chỉ làm trong phạm vi của mình; việc ngoài phạm vi thì ghi vào mục "Bàn giao" ở cuối output.

| Agent | Việc | Đầu vào | Đầu ra |
|---|---|---|---|
| `etl-agent` | Rà soát package SSIS, kiểm tra số dòng nguồn vs DW, phát hiện lỗi key/null | Repo (thư mục SSIS), SQLite gốc | Báo cáo đối soát số dòng, danh sách lỗi và cách sửa |
| `cube-agent` | Kiểm tra thiết kế SSAS: dimension, hierarchy, attribute relationship, measure group | Project SSAS trong repo | Danh sách vấn đề thiết kế + đề xuất sửa |
| `mdx-agent` | Chọn 10 câu MDX từ Q1–Q23, sửa lỗi cú pháp, viết mô tả + ý nghĩa nghiệp vụ | Tab `mdx`, mục 3 file này | Bảng 10 câu: loại thao tác, MDX, mô tả, insight mong đợi |
| `feature-agent` | Viết code bước 1–3, kiểm tra lại phần Tzy đã làm | SQLite gốc, mục 4 | Notebook/`.py` tạo bảng `seller_features`, báo cáo phân phối & tương quan |
| `cluster-agent` | Bước 4–5: K-Means, GMM, DBSCAN, metric, PCA 2D | `seller_features` đã chuẩn hóa | Bảng so sánh metric, biểu đồ Elbow/Silhouette/BIC/k-distance/PCA |
| `insight-agent` | Bước 6: profile cụm, radar, đặt tên, đề xuất chính sách | Nhãn cụm + đặc trưng gốc (chưa scale) | Bảng profile, radar chart, đoạn mô tả từng phân khúc |
| `report-agent` | Viết nội dung báo cáo LaTeX | Output của các agent trên | Các section `.tex` |
| `reviewer-agent` | Đọc lại output agent khác như người chấm khó tính: sai số liệu, sai tên cube, lập luận yếu | Output bất kỳ | Danh sách lỗi theo mức độ |

---

## 6. Quy ước chung cho mọi agent

1. **Ngôn ngữ:** viết tiếng Việt; tên biến, tên cột, code, MDX giữ tiếng Anh.
2. **Không bịa số liệu.** Mọi con số trong báo cáo phải chạy ra từ code/MDX; nếu chưa chạy được thì ghi `TODO: chạy lại`.
3. **Reproducible:** cố định `random_state=42`; ghi phiên bản thư viện chính.
4. **Không sửa trực tiếp nhánh `main`** của repo; làm trên branch riêng, mô tả thay đổi rõ ràng.
5. **Báo cáo LaTeX:** **không dùng bullet** (`itemize`) vì trông "AI quá"; vẫn giữ cấu trúc thụt đầu dòng lồng nhau cho từng khái niệm (dùng `enumerate` lồng nhau hoặc `\paragraph`/`description` có thụt lề), không viết thành một đoạn văn xuôi liền.
6. **Tên phân khúc** phải gắn với số liệu (ví dụ "Seller chủ lực đa ngành: doanh thu trung vị cao gấp X lần"), không đặt tên cảm tính.
7. Khi một task trong sheet đổi trạng thái, ghi chú lại để leader cập nhật tab `St`.

---

## 7. Định dạng output chuẩn của agent

```
## Kết quả
<nội dung chính: bảng, code, kết luận>

## Giả định đã dùng
<những gì agent tự quyết khi thiếu thông tin>

## Vấn đề / rủi ro
<lỗi, chỗ chưa chắc>

## Bàn giao
<việc cần agent khác hoặc thành viên làm tiếp>
```

---

## 8. Câu hỏi còn mở

1. Có đưa `growth_exposure` vào bộ đặc trưng phân cụm không?
2. Thuật toán phân cụm thứ 4 là gì (sheet ghi 4 nhưng liệt kê 3)?
3. Ngưỡng lọc seller ít đơn là bao nhiêu?
4. 10 câu MDX cuối cùng chọn những câu nào trong Q1–Q23?
