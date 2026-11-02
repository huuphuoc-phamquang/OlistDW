# Phần SSAS: Cube, Dimension và truy vấn MDX (Olist DW)

> Môi trường: SQL Server 2025 Enterprise Developer, SSAS Multidimensional (instance `DESKTOP-AJ19VOT\SSAS_ENT`), Visual Studio 18 + SSAS Projects. Nguồn dữ liệu: database `OlistDW` (nạp từ `data/processed/*.csv` bằng SSIS, xem README ở thư mục gốc).

## 1. Mục tiêu và mô hình

- Xây cube **Olist DW** trên schema đã thiết kế: bảng sự kiện `fact_order_items` (grain: 1 dòng = 1 món hàng trong đơn) và các dimension `dim_customer`, `dim_seller`, `dim_product`, `dim_product_category`, `dim_location`.
- Cube có **3 measure**: `Price` (SUM), `Freight Value` (SUM), `Fact Order Items Count` (COUNT dòng).
- **2 hierarchy** phục vụ roll-up/drill-down: `Location Hierarchy` (State → City) và `Product Hierarchy` (Product Category Name → Product Id).
- Kết quả đối chiếu: tổng cube = **13.591.643,70** (price), **112.650** dòng, khớp SQL.

## 2. Các bước tạo project SSAS

1. **Cài đặt**: SQL Server (tick *Analysis Services*, chọn **Multidimensional Mode**, **Add Current User**). Dùng edition **Enterprise Developer** (Standard Developer bị lỗi `StandardDeveloper64` với client cũ). Cài extension *Microsoft Analysis Services Projects* trong Visual Studio.
2. **New Project** → *Analysis Services Multidimensional Project* (tên `SSAS`).
3. **Data Source**: chuột phải *Data Sources* → New → Microsoft OLE DB Driver for SQL Server, Server `DESKTOP-AJ19VOT`, Database `OlistDW`; tab *Impersonation Information*: **Use the service account**. Cấp quyền đọc cho tài khoản `NT Service\MSOLAP$SSAS_ENT` (login + `db_datareader` trên OlistDW).
4. **Data Source View**: chọn các bảng `dim_customer, dim_seller, dim_product, dim_product_category, dim_location, dim_review, fact_order_items`. Đặt logical primary key cho mỗi bảng dim và tạo quan hệ (**New Relationship**): `fact_order_items.customer_id → dim_customer`, `seller_id → dim_seller`, `product_id → dim_product`, `dim_customer.location_id → dim_location.location_id`, `dim_seller.location_id → dim_location`, `dim_product.product_category_name → dim_product_category`.
5. **Dimensions** (chuột phải *Dimensions* → New Dimension → Use an existing table): tạo từng dimension rồi thêm thuộc tính/hierarchy như mục 3.
6. **Cube**: chuột phải *Cubes* → New Cube → Use existing tables; bảng measure group = `fact_order_items`; chọn measure `price`, `freight_value` và `Fact Order Items Count`; chọn các dimension đã tạo.
7. **Deploy**: Project → Properties → Deployment: Server = `DESKTOP-AJ19VOT\SSAS_ENT`, Database = `SSAS`; chuột phải project → **Deploy** (deploy kèm process).

## 3. Các dimension

| Dimension | Khóa | Thuộc tính | Hierarchy |
|---|---|---|---|
| Dim Customer | Customer Id | Customer Unique Id, Location Id | – |
| Dim Seller | Seller Id | Location Id | – |
| Dim Product | Product Id | Product Category Name, kích thước/cân nặng/ảnh… | **Product Hierarchy**: Product Category Name → Product Id |
| Dim Product Category | Product Category Name | – | – |
| Dim Location | Location Id | Geolocation State, Geolocation City, Geolocation Zip Code Prefix | **Location Hierarchy**: Geolocation State → Geolocation City |
| Dim Review | Review Id | (chưa đưa vào cube) | – |
| Dim Payment Type | Payment Type | – | – |
| Dim Lead Origin | Origin | – | – |
| Dim Contact Date | Contact Month (tên dạng `2018-02`) | Contact Year | **Contact Date Hierarchy**: Contact Year → Contact Month |

Cách tạo hierarchy trong Dimension Designer:
- Kéo cột `geolocation_state`, `geolocation_city`, `geolocation_zip_code_prefix` từ DSV sang khung *Attributes* của `Dim Location`.
- Thuộc tính **Geolocation City**: *KeyColumns* = (`geolocation_state`, `geolocation_city`) để tránh trùng tên thành phố giữa các bang; *NameColumn* = `geolocation_city`.
- Kéo `Geolocation State` rồi `Geolocation City` vào khung *Hierarchies* → đổi tên thành **Location Hierarchy**.
- Tab *Attribute Relationships*: `Location Id → Geolocation City → Geolocation State` và `Location Id → Geolocation Zip Code Prefix`.
- Làm tương tự cho `Dim Product`: kéo `Product Category Name` rồi `Product Id` vào Hierarchies → **Product Hierarchy**.

## 4. Cube và Dimension Usage

Tab *Dimension Usage*:

| Dimension | Quan hệ với Fact Order Items |
|---|---|
| Dim Customer, Dim Seller, Dim Product | **Regular** (khóa ngoại trên fact) |
| Dim Location | **Referenced** qua **Dim Customer** (Intermediate dimension = Dim Customer, Intermediate attribute = `Location Id`, Reference dimension attribute = `Location Id`, tick *Materialize*) |

Mỗi dòng fact chỉ có 1 khách hàng nên địa lý được tra qua khách hàng (địa lý của người mua). Địa lý người bán có thể thêm tương tự bằng một cube dimension thứ hai (role-playing) nếu cần.

## 5. Chạy truy vấn

Mở SSMS → *Connect* → Server type **Analysis Services**, Server name `DESKTOP-AJ19VOT\SSAS_ENT` → chuột phải database `SSAS` → **New Query → MDX** (hoặc chuột phải cube → Browse). Chạy **từng câu một** (bôi đen rồi F5). File đầy đủ: `ssas/mdx/01_olist_mdx_queries.mdx`.

Tóm tắt cú pháp:
- `SELECT <tập> ON COLUMNS, <tập> ON ROWS FROM [Olist DW] WHERE (<lát cắt>)`.
- Thành viên: `[Dim Location].[Location Hierarchy].[Geolocation State].&[SP]` (`&[...]` là khóa thành viên).
- Hàm chính: `MEMBERS`, `CHILDREN`, `PARENT`, `TOPCOUNT`, `ORDER`, `FILTER`, `NONEMPTY`, `DRILLDOWNLEVELTOP`.

## 6.1 Roll-up (gop tu muc chi tiet len muc tong quat)

### Q1 - Doanh thu theo bang (cap State)

```mdx
SELECT { [Measures].[Price], [Measures].[Freight Value], [Measures].[Fact Order Items Count] } ON COLUMNS,
       NON EMPTY [Dim Location].[Location Hierarchy].[Geolocation State].MEMBERS ON ROWS
FROM [Olist DW]
```

**Ket qua mau:** AC 15.982,95 | AL 80.314,81 | ... | BA 511.349,99 | ... (27 bang)

### Q2 - Doanh thu theo nhom san pham (cap Category, tu Product len Category)

```mdx
SELECT { [Measures].[Price], [Measures].[Fact Order Items Count] } ON COLUMNS,
       NON EMPTY ORDER([Dim Product].[Product Hierarchy].[Product Category Name].MEMBERS, [Measures].[Price], BDESC) ON ROWS
FROM [Olist DW]
```

**Ket qua mau:** beleza_saude 1.258.681,34 | relogios_presentes 1.205.005,68 | cama_mesa_banho 1.036.988,68 | ... (74 nhom)

### Q3 - Gop tu thanh pho len bang roi len toan quoc bang .PARENT

```mdx
SELECT { [Measures].[Price], [Measures].[Fact Order Items Count] } ON COLUMNS,
       { [Dim Location].[Location Hierarchy].[Geolocation City].&[SP]&[campinas],
         [Dim Location].[Location Hierarchy].[Geolocation City].&[SP]&[campinas].PARENT,
         [Dim Location].[Location Hierarchy].[Geolocation City].&[SP]&[campinas].PARENT.PARENT } ON ROWS
FROM [Olist DW]
```

**Ket qua mau:** campinas 187.844,53 -> SP 5.202.955,05 -> All 13.591.643,70 (112.650 dong hang)

### Q4 - Cong don doanh thu cac bang tu lon den nho (tong luy ke bang SUM tren tap da sap xep)

```mdx
WITH SET [S] AS ORDER(NONEMPTY([Dim Location].[Location Hierarchy].[Geolocation State].MEMBERS, [Measures].[Price]), [Measures].[Price], BDESC)
MEMBER [Measures].[Luy Ke Price] AS SUM(HEAD([S], RANK([Dim Location].[Location Hierarchy].CURRENTMEMBER, [S])), [Measures].[Price])
SELECT { [Measures].[Price], [Measures].[Luy Ke Price] } ON COLUMNS,
       TOPCOUNT([S], 8) ON ROWS
FROM [Olist DW]
```

**Ket qua mau:** SP 5.202.955,05 | RJ 7.027.047,72 (luy ke) | MG 8.612.355,75 | RS 9.362.659,77 | ...

## 6.2 Drill-down (khoet tu muc tong quat xuong chi tiet)

### Q5 - Tu bang SP, RJ, MG khoet xuong 3 thanh pho doanh thu cao nhat cua moi bang

```mdx
SELECT { [Measures].[Price], [Measures].[Fact Order Items Count] } ON COLUMNS,
       DRILLDOWNLEVELTOP({ [Dim Location].[Location Hierarchy].[Geolocation State].&[SP],
                           [Dim Location].[Location Hierarchy].[Geolocation State].&[RJ],
                           [Dim Location].[Location Hierarchy].[Geolocation State].&[MG] }, 3, , [Measures].[Price]) ON ROWS
FROM [Olist DW]
```

**Ket qua mau:** SP -> sao paulo 1.914.924,54 / campinas 187.844,53 / guarulhos 144.268,39; RJ -> rio de janeiro 992.538,86 ...

### Q6 - Tu nhom cama_mesa_banho khoet xuong 10 san pham doanh thu cao nhat

```mdx
SELECT { [Measures].[Price], [Measures].[Fact Order Items Count] } ON COLUMNS,
       TOPCOUNT([Dim Product].[Product Hierarchy].[Product Category Name].&[cama_mesa_banho].CHILDREN, 10, [Measures].[Price]) ON ROWS
FROM [Olist DW]
```

**Ket qua mau:** 10 san pham, cao nhat 43.025,56 (488 dong hang)

### Q7 - Top 3 nhom san pham, moi nhom khoet xuong 3 san pham ban chay nhat

```mdx
SELECT { [Measures].[Price] } ON COLUMNS,
       DRILLDOWNLEVELTOP(TOPCOUNT([Dim Product].[Product Hierarchy].[Product Category Name].MEMBERS, 3, [Measures].[Price]), 3, , [Measures].[Price]) ON ROWS
FROM [Olist DW]
```

**Ket qua mau:** beleza_saude -> 3 san pham (63.885 / 54.730,20 / 22.717,22); relogios_presentes -> 3 san pham ...

## 6.3 Slice and dice (cat lat va cat khoi con)

### Q8 - Cat theo bang SP (WHERE): top 10 nhom san pham ban chay o SP

```mdx
SELECT { [Measures].[Price], [Measures].[Fact Order Items Count] } ON COLUMNS,
       TOPCOUNT([Dim Product].[Product Hierarchy].[Product Category Name].MEMBERS, 10, [Measures].[Price]) ON ROWS
FROM [Olist DW]
WHERE ( [Dim Location].[Location Hierarchy].[Geolocation State].&[SP] )
```

**Ket qua mau:** cama_mesa_banho 478.284,52 | beleza_saude 462.305,22 | relogios_presentes 435.009,92 | ...

### Q9 - Cat 2 chieu cung luc: bang SP va nhom beleza_saude (ket qua la mot "lat cat" 1 hang)

```mdx
SELECT { [Measures].[Price], [Measures].[Freight Value], [Measures].[Fact Order Items Count] } ON COLUMNS
FROM [Olist DW]
WHERE ( [Dim Location].[Location Hierarchy].[Geolocation State].&[SP],
        [Dim Product].[Product Hierarchy].[Product Category Name].&[beleza_saude] )
```

**Ket qua mau:** Price 462.305,22 | Freight 57.341,58 | Count 4.204 (khop SQL)

### Q10 - Khoi con (sub-cube): 3 bang x 3 nhom san pham, nhom bang subselect

```mdx
SELECT { [Measures].[Price], [Measures].[Fact Order Items Count] } ON COLUMNS,
       NON EMPTY [Dim Location].[Location Hierarchy].[Geolocation State].MEMBERS ON ROWS
FROM ( SELECT { [Dim Location].[Location Hierarchy].[Geolocation State].&[SP],
                [Dim Location].[Location Hierarchy].[Geolocation State].&[RJ],
                [Dim Location].[Location Hierarchy].[Geolocation State].&[MG] } ON COLUMNS
       FROM ( SELECT { [Dim Product].[Product Hierarchy].[Product Category Name].&[beleza_saude],
                       [Dim Product].[Product Hierarchy].[Product Category Name].&[cama_mesa_banho],
                       [Dim Product].[Product Hierarchy].[Product Category Name].&[esporte_lazer] } ON COLUMNS
              FROM [Olist DW] ) )
```

**Ket qua mau:** MG 399.921,47 | RJ 418.481,89 | SP 1.326.946,75

### Q11 - Loc theo dieu kien: thanh pho cua SP co doanh thu > 100000

```mdx
SELECT { [Measures].[Price], [Measures].[Fact Order Items Count] } ON COLUMNS,
       FILTER([Dim Location].[Location Hierarchy].[Geolocation State].&[SP].CHILDREN, [Measures].[Price] > 100000) ON ROWS
FROM [Olist DW]
```

**Ket qua mau:** campinas, guarulhos, sao bernardo do campo, sao paulo

## 6.4 Pivot (xoay truc)

### Q12 - Hang = nhom san pham (top 5), cot = bang (SP, RJ, MG)

```mdx
SELECT { [Dim Location].[Location Hierarchy].[Geolocation State].&[SP],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[RJ],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[MG] } ON COLUMNS,
       TOPCOUNT([Dim Product].[Product Hierarchy].[Product Category Name].MEMBERS, 5, [Measures].[Price]) ON ROWS
FROM [Olist DW]
WHERE ( [Measures].[Price] )
```

**Ket qua mau:** cot SP/RJ/MG; hang beleza_saude 462.305,22 | 145.298,62 | 157.558,30 ...

### Q13 - Xoay truc cua Q12: hang = bang, cot = nhom san pham

```mdx
SELECT TOPCOUNT([Dim Product].[Product Hierarchy].[Product Category Name].MEMBERS, 5, [Measures].[Price]) ON COLUMNS,
       { [Dim Location].[Location Hierarchy].[Geolocation State].&[SP],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[RJ],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[MG] } ON ROWS
FROM [Olist DW]
WHERE ( [Measures].[Price] )
```

**Ket qua mau:** hang SP/RJ/MG; cot beleza_saude, relogios_presentes, cama_mesa_banho, esporte_lazer, informatica_acessorios

### Q14 - Dua do do (Measures) xuong hang, bang len cot

```mdx
SELECT { [Dim Location].[Location Hierarchy].[Geolocation State].&[SP],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[RJ],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[MG] } ON COLUMNS,
       { [Measures].[Price], [Measures].[Freight Value], [Measures].[Fact Order Items Count] } ON ROWS
FROM [Olist DW]
```

**Ket qua mau:** Price 5.202.955,05 | 1.824.092,67 | 1.585.308,03; Count 47.449 | 14.579 | 13.129

### Q15 - Thanh vien tinh toan: gia trung binh moi dong hang, bang x nhom san pham

```mdx
WITH MEMBER [Measures].[Avg Price] AS IIF([Measures].[Fact Order Items Count] = 0, NULL, [Measures].[Price] / [Measures].[Fact Order Items Count]), FORMAT_STRING = '#,##0.00'
SELECT TOPCOUNT([Dim Product].[Product Hierarchy].[Product Category Name].MEMBERS, 4, [Measures].[Price]) ON COLUMNS,
       { [Dim Location].[Location Hierarchy].[Geolocation State].&[SP],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[RJ],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[MG] } ON ROWS
FROM [Olist DW]
WHERE ( [Measures].[Avg Price] )
```

**Ket qua mau:** SP 109,97 | 190,71 | 91,36 | 105,36; RJ 136,56 | 212,10 | 90,05 | 120,22; MG 145,08 | 194,28 | 97,40 | 116,69

### 4.1 Hai measure group bổ sung

| Measure group | Measure | Dimension (quan hệ) |
|---|---|---|
| Fact Order Payment | Payment Value, Payment Count | Dim Payment Type (Regular, khóa `payment_type`); Dim Customer (Regular, qua cột tính `customer_id`); Dim Location (Referenced qua Dim Customer) |
| Fact Seller Lead | Lead Count, Won Leads, Declared Monthly Revenue | Dim Lead Origin (Regular, `origin`); Dim Contact Date (Regular, `contact_ym`); Dim Seller (Regular, qua cột tính `seller_key`) |

Các điểm cần biết:
- `fact_order_payment` không có khóa khách hàng. Trong Data Source View thêm *Named Calculation* `customer_id` lấy từ `fact_order_items` theo `order_id` (mỗi đơn chỉ có một khách hàng). 830 dòng thanh toán thuộc đơn không có dòng hàng (162.591,95) nên rơi vào thành viên **Unknown** của Dim Customer, không bị mất khỏi tổng.
- `fact_seller_lead` có thêm các Named Calculation: `won_flag` (1 nếu `is_won`, để cộng được thành Won Leads), `contact_year`, `contact_ym`, `contact_ym_name` (từ `first_contact_date`) và `seller_key` (= `seller_id` nếu seller có trong `dim_seller`, ngược lại NULL). Trong 842 lead thắng chỉ 380 seller đã có đơn hàng; 462 lead thắng và 7.158 lead chưa thắng vào **Unknown** của Dim Seller.
- Dim Customer, Dim Seller, Dim Location đặt *UnknownMember = Visible*; khóa NULL ở fact đặt *NullProcessing = UnknownMember*.
- `declared_monthly_revenue` bằng 0 ở các seller có trong `dim_seller`, nên Declared Monthly Revenue chỉ có ý nghĩa theo kênh tiếp thị và thời gian (Q23), không theo seller.
- Truy vấn: `ssas/mdx/03_olist_mdx_payment_lead.mdx` (Q16 đến Q23).

## 7. Đối chiếu với SQL

| Kiểm tra | MDX | SQL |
|---|---|---|
| Tổng Price / số dòng | 13.591.643,70 / 112.650 | 13.591.643,70 / 112.650 |
| Bang SP, nhóm beleza_saude (Q9) | 462.305,22 / 4.204 | 462.305,22 / 4.204 |
| Tổng Payment Value / Payment Count | 16.008.872,12 / 103.886 | 16.008.872,12 / 103.886 |
| Payment Value credit_card (Q16) | 12.542.084,19 / 76.795 | 12.542.084,19 / 76.795 |
| Lead Count / Won Leads | 8.000 / 842 | 8.000 / 842 |

```sql
SELECT SUM(f.price), COUNT(*)
FROM dbo.fact_order_items f
JOIN dbo.dim_customer c ON c.customer_id = f.customer_id
JOIN dbo.dim_location l ON l.location_id = c.location_id
JOIN dbo.dim_product  p ON p.product_id  = f.product_id
WHERE l.geolocation_state = 'SP' AND p.product_category_name = 'beleza_saude';
```

## 8. Lỗi thường gặp

| Lỗi | Nguyên nhân / cách xử lý |
|---|---|
| `edition 'StandardDeveloper64' ... not supported by the client` | Client cũ không nhận edition Standard Developer. Cài SSAS bằng **Enterprise Developer**. |
| `A connection cannot be made` khi Deploy | Sai tên server (instance có tên phải là `Máy\Instance`) hoặc SSAS chưa chạy. |
| `A connection could not be made to the data source` | Tài khoản SSAS chưa có quyền đọc OlistDW. Cấp `db_datareader` hoặc dùng Impersonation = service account. |
| `Granularity is not defined` (Referenced dimension) | Thiếu thuộc tính granularity của dimension tham chiếu. Thiết lập trong *Dimension Usage* (Define Relationship → Referenced) thay vì sửa tay. |
| Giá trị bị nhân 10/100 | Nạp CSV sai locale. Đặt `LocaleID = 1033` (English - US) trong Flat File Connection. |
| `Multiple statements are not allowed` | Chạy mỗi lần một câu MDX. |
| Tổng chỉ còn ~10% sau khi thêm Dim Location | `location_id` trong `dim_customer`/`dim_seller` bị nhân 10 (nạp trước khi sửa locale) nên không khớp `dim_location`. Sửa: `UPDATE ... SET location_id = location_id/10` hoặc nạp lại bằng SSIS. |
