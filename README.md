# Olist Data Warehouse (IS217)

Kho dữ liệu cho bộ dữ liệu thương mại điện tử Olist: tiền xử lý (Python) → nạp SQL Server (SSIS) → cube SSAS Multidimensional → truy vấn MDX.

## Cấu trúc thư mục

```
Olist_DW/
├── data/
│   ├── raw/                 olist.sqlite + csv/ (dữ liệu gốc Olist)
│   └── processed/           9 file CSV sau tiền xử lý (dim_*, fact_*) - đầu vào của SSIS
├── notebooks/               tiền xử lý: olist_preprocessing.ipynb (Colab), *_kaggle.ipynb, *_kaggle_en.ipynb
├── sql/
│   ├── 01_create_tables.sql     tạo database OlistDW và các bảng rỗng
│   ├── 02_post_load_checks.sql  khóa chính dim_location, đếm dòng, kiểm tra khóa ngoại
│   └── 03_compare_with_cube.sql đối chiếu số liệu với MDX
├── ssis/
│   ├── Olist_SSIS.slnx          mở bằng Visual Studio
│   └── Project/Package.dtsx     nạp 9 CSV vào OlistDW
├── ssas/
│   ├── Olist_SSAS.slnx          mở bằng Visual Studio
│   ├── SSAS/                    project cube (Data Source, DSV, 6 dimension, cube Olist DW)
│   └── mdx/                     01_olist_mdx_queries.mdx (15 truy vấn), 02_compare_with_sql.mdx
└── docs/                    lược đồ (drawio/png/svg/pdf), báo cáo LaTeX, huong_dan_ssas_mdx.md
```

## Thứ tự chạy

| Bước | Việc | Công cụ |
|---|---|---|
| 0 | Tạo `data/processed/*.csv` từ `data/raw` (đã có sẵn, chỉ chạy lại khi cần) | `notebooks/` |
| 1 | Tạo database và bảng | SSMS: chạy `sql/01_create_tables.sql` |
| 2 | Nạp dữ liệu | Visual Studio: mở `ssis/Olist_SSIS.slnx`, chuột phải `Package.dtsx` → Execute |
| 3 | Khóa chính và kiểm tra | SSMS: chạy `sql/02_post_load_checks.sql` |
| 4 | Tạo cube | Visual Studio: mở `ssas/Olist_SSAS.slnx` → Deploy |
| 5 | Truy vấn | SSMS (Analysis Services): chạy từng câu trong `ssas/mdx/01_olist_mdx_queries.mdx` |
| 6 | Đối chiếu | `sql/03_compare_with_cube.sql` và `ssas/mdx/02_compare_with_sql.mdx` |

Kết quả đúng: `fact_order_items` có 112.650 dòng, tổng `price` 13.591.643,70, `freight_value` 2.251.909,54.

## Đường dẫn và tên server cần chỉnh khi chuyển máy

| Ở đâu | Giá trị hiện tại | Cách sửa |
|---|---|---|
| SSIS: 9 Flat File Connection (`ssis/Project/Package.dtsx`, `Project.dtproj`) | `D:\2_Tai_lieu\UIT\IS217\0.Do_an\Olist_DW\data\processed\*.csv` | Trong Visual Studio, từng Connection Manager → *ConnectionString*; hoặc tìm và thay chuỗi thư mục trong hai file |
| SSIS: kết nối SQL Server | `Data Source=.;Initial Catalog=OlistDW` | Connection Manager `TZY.OlistDWH` |
| SSAS: Data Source | `Data Source=DESKTOP-AJ19VOT` (SQL Server chứa OlistDW) | `ssas/SSAS/Olist DW.ds` → Connection String |
| SSAS: server triển khai | `DESKTOP-AJ19VOT\SSAS_ENT`, database `SSAS` | Project SSAS → Properties → Deployment |

## Yêu cầu và lưu ý

- SQL Server 2025 và SSAS **Multidimensional**, edition **Enterprise Developer** (Standard Developer báo lỗi `StandardDeveloper64` với client của Visual Studio). Extension: *SQL Server Integration Services Projects* và *Analysis Services Projects*.
- Tài khoản chạy SSAS (`NT Service\MSOLAP$<instance>`) cần quyền `db_datareader` trên OlistDW, và Data Source dùng *Use the service account*.
- Flat File Connection phải đặt `LocaleID = 1033` (English - US) và code page 65001, nếu không giá trị số bị nhân 10/100.
- Chạy lại package SSIS trên database đã có dữ liệu sẽ lỗi trùng khóa ở các task DIM_*; chạy lại `sql/01_create_tables.sql` trước.
- Hướng dẫn chi tiết cube, dimension và 15 truy vấn MDX: `docs/huong_dan_ssas_mdx.md`.
