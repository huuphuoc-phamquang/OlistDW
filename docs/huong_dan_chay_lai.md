# Hướng dẫn chạy lại kho dữ liệu và cube

Dùng khi cần nạp lại `OlistDW` và deploy lại cube `SSAS` từ đầu: chuyển sang máy khác, sửa schema, hoặc cập nhật nhãn phân khúc seller. Quy trình này đã chạy trên máy `DESKTOP-AJ19VOT` ngày 28/11/2026.

**Cảnh báo:** bước 2 xóa và tạo lại toàn bộ bảng trong `OlistDW`. Từ bước 2 đến hết bước 6, cube và mọi report Power BI hoặc Excel nối vào cube sẽ lỗi hoặc trống. Báo cho cả nhóm trước khi chạy.

## 1. Chuẩn bị

| Cần có | Kiểm tra |
|---|---|
| Branch có đủ thay đổi (fact 11 cột, Dim Order Date, Seller Segment) | `git log --oneline` có commit `feat(ssas): add order date dimension to the Olist DW cube` |
| `data/processed/fact_order_items.csv` có **11 cột** | Dòng đầu kết thúc bằng `order_estimated_delivery_date`. Nếu chỉ có 7 cột, chạy lại `notebooks/olist_preprocessing.ipynb` |
| Đường dẫn CSV và tên server đúng máy | Xem mục "Đường dẫn và tên server cần chỉnh khi chuyển máy" trong `README.md` |
| Công cụ | `sqlcmd`, `DTExec.exe` (SQL Server 170), Visual Studio có extension Analysis Services, SSAS Multidimensional |

Backup trước khi chạy:

```sql
BACKUP DATABASE OlistDW TO DISK = N'OlistDW_truoc_khi_chay_lai.bak' WITH INIT, CHECKSUM;
```

Backup cube: SSMS → kết nối Analysis Services → chuột phải database `SSAS` → Back Up.

## 2. Các bước

Chạy từ thư mục gốc repo (`Olist_DW/`). Mỗi lệnh phải báo thành công rồi mới chạy lệnh sau.

| Bước | Việc | Lệnh |
|---|---|---|
| 2 | Tạo lại bảng rỗng | `sqlcmd -S . -E -C -b -i sql/01_create_tables.sql` |
| 3 | Nạp 9 CSV bằng SSIS | Trong `ssis/Project/`: `DTExec.exe /F Package.dtsx`, phải in `DTSER_SUCCESS` |
| 4 | Khóa chính, khóa ngoại và kiểm tra | `sqlcmd -S . -E -C -b -i sql/02_post_load_checks.sql` |
| 5 | Nạp phân khúc seller v3 vào `dim_seller` | `sqlcmd -S . -E -C -b -d OlistDW -f 65001 -i artifacts/seller_clustering_v3/load_seller_segments.sql` |
| 6 | Deploy và Process Full cube | Visual Studio: mở `ssas/Olist_SSAS.slnx` → Build → Deploy. Nếu chỉ process: SSMS → chuột phải database `SSAS` → Process → Process Full |
| 7 | Kiểm tra bằng MDX | Chạy `ssas/mdx/05_order_date.mdx` và `ssas/mdx/04_seller_segments.mdx` trong SSMS (Analysis Services) |

Bước 5 phải chạy **sau** bước 2, vì bước 2 tạo lại `dim_seller` không có cột `seller_segment` và `seller_region`. Thiếu bước 5 thì bước 6 lỗi do cube không tìm thấy hai cột này.

Script ở bước 5 chạy trong một transaction: nếu seller trong file và trong `dim_seller` không khớp, script dừng và không ghi gì.

## 3. Kết quả đúng

| Kiểm tra | Giá trị |
|---|---|
| `fact_order_items` | 112.650 dòng, 11 cột, tổng `price` 13.591.643,70, tổng `freight_value` 2.251.909,54 |
| `02_post_load_checks.sql` | `payment_khong_co_order` 830, `review_khong_co_order` 725, `lead_khong_co_seller` 462 |
| Bước 5 | Bảng đếm theo phân khúc và `missing_mapping` = 0 |
| MDX doanh số theo năm (Dim Order Date) | 2016: 49.785,92; 2017: 6.155.806,98; 2018: 7.386.050,80; cộng lại bằng tổng `price` |
| MDX doanh số theo Seller Segment | 7 nhóm, cộng lại bằng tổng `price` và 112.650 món |

Số seller theo phân khúc sau bước 5:

| Phân khúc | Seller |
|---|---:|
| C0 Chủ lực đa ngành | 539 |
| C1 Giá cao, giao xa | 274 |
| C2 Ngưng hoạt động | 526 |
| C3 Mới, bán gần | 575 |
| C4 Giao trễ, review thấp | 215 |
| Ít đơn (dưới 3 đơn) | 841 |
| Chưa có đơn delivered | 125 |

## 4. Cập nhật nhãn phân khúc

Khi chạy lại phân cụm (`notebooks/seller_clustering_v3.ipynb`) và nhãn thay đổi:

1. Sửa tên phân khúc trong `V3_NAMES` của `mining/prepare_segment_handoff.py` nếu thứ tự hoặc ý nghĩa cụm đổi.
2. Chạy `python mining/prepare_segment_handoff.py` để sinh lại `artifacts/seller_clustering_v3/load_seller_segments.sql`.
3. Chạy lại bước 5, rồi Process Full cube (bước 6). Không cần chạy lại bước 2 đến 4.
4. Cập nhật tên phân khúc trong `ssas/mdx/04_seller_segments.mdx` và mục 3 của `docs/agents_is217.md`.

## 5. Lỗi đã gặp

| Lỗi | Nguyên nhân | Cách xử lý |
|---|---|---|
| Bước 3 lỗi chuyển kiểu ở `freight_value` | Chạy package cũ 7 cột với CSV 11 cột | Chạy package trên branch có thay đổi fact 11 cột |
| Bước 3 lỗi trùng khóa ở các task DIM_* | Chưa chạy bước 2, bảng còn dữ liệu cũ | Chạy bước 2 trước |
| Bước 5 báo `Cannot resolve the collation conflict` | `OlistDW` có collation khác server | Đã sửa trong script (bảng tạm dùng `COLLATE DATABASE_DEFAULT`). Nếu gặp lại, sinh lại file SQL bằng `prepare_segment_handoff.py` |
| Process cube báo `Login failed for user 'NT Service\MSOLAP$SSAS_ENT'` | Tài khoản dịch vụ SSAS chưa có quyền đọc database | `CREATE USER [NT Service\MSOLAP$SSAS_ENT] FOR LOGIN [NT Service\MSOLAP$SSAS_ENT]; ALTER ROLE db_datareader ADD MEMBER [NT Service\MSOLAP$SSAS_ENT];` trong database nguồn |
| Process cube báo thiếu cột `seller_segment` | Bỏ qua bước 5 | Chạy bước 5 rồi process lại |
| Chữ tiếng Việt hiện sai dấu trong cửa sổ `sqlcmd` | Console không hiển thị UTF-8 | Chỉ là hiển thị; dữ liệu vẫn đúng. Kiểm tra bằng SSMS |
| Chạy `devenv` từ Git Bash mở giao diện Visual Studio rồi đứng | Git Bash đổi tham số `/Build` thành đường dẫn | Chạy `devenv.com ... /Build Development` từ PowerShell hoặc cmd |

## 6. Khôi phục khi có sự cố

```sql
USE master;
ALTER DATABASE OlistDW SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
RESTORE DATABASE OlistDW FROM DISK = N'OlistDW_truoc_khi_chay_lai.bak' WITH REPLACE;
ALTER DATABASE OlistDW SET MULTI_USER;
```

Cube: SSMS → Analysis Services → chuột phải Databases → Restore → chọn file `.abf` đã backup.

Backup của lần chạy ngày 28/11/2026 trên `DESKTOP-AJ19VOT`:
- **SQL Server:** `C:\Program Files\Microsoft SQL Server\MSSQL17.MSSQLSERVER\MSSQL\Backup\OlistDW_before_cube_20261128.bak`.
- **SSAS:** `SSAS_before_cube_20261128.abf`, nằm trong thư mục Backup mặc định của instance `SSAS_ENT`.
