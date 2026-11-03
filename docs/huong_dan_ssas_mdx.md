# Phần SSAS: Cube, Dimension và Truy Vấn MDX (Olist DW)

> **Môi trường:** SQL Server 2025 Enterprise Developer, SSAS Multidimensional (instance `DESKTOP-AJ19VOT\SSAS_ENT`), Visual Studio + extension *SSAS Projects*.  
> **Nguồn dữ liệu:** Database `OlistDW` (nạp từ `data/processed/*.csv` qua SSIS, xem `README.md`).

---

## 1. Mục tiêu và mô hình

* **Ý tưởng thiết kế:** Xây dựng một Cube duy nhất (`Olist DW`) gom **3 Measure Group** đại diện cho 3 quy trình nghiệp vụ thương mại điện tử:
  1. `Fact Order Items`: Chi tiết đơn hàng (Grain: **1 dòng = 1 món hàng trong đơn**).
  2. `Fact Order Payment`: Giao dịch thanh toán (Grain: **1 dòng = 1 lần thanh toán**).
  3. `Fact Seller Lead`: Phễu tiếp thị người bán (Grain: **1 dòng = 1 lead tiềm năng MQL**).
* **Các Dimension:** Gồm 6 dimension bảng (`dim_customer`, `dim_seller`, `dim_product`, `dim_product_category`, `dim_location`, `dim_review`) và 3 dimension tạo từ cột fact (`Dim Payment Type`, `Dim Lead Origin`, `Dim Contact Date`).
* **Measures cốt lõi:**
  * `Fact Order Items`: `Price` (SUM), `Freight Value` (SUM), `Fact Order Items Count` (COUNT).
  * `Fact Order Payment`: `Payment Value` (SUM), `Payment Count` (COUNT).
  * `Fact Seller Lead`: `Lead Count` (COUNT), `Won Leads` (SUM `won_flag`), `Declared Monthly Revenue` (SUM).
* **3 Phân cấp (Hierarchy) phục vụ Roll-up / Drill-down:**
  * `Location Hierarchy`: `Geolocation State` (Bang) → `Geolocation City` (Thành phố).
  * `Product Hierarchy`: `Product Category Name` (Nhóm sản phẩm) → `Product Id` (Mã sản phẩm).
  * `Contact Date Hierarchy`: `Contact Year` (Năm) → `Contact Month` (Tháng).
* **Kết quả đối chiếu chuẩn (khớp 100% với SQL):**
  * `Fact Order Items`: Doanh thu `Price` = **13.591.643,70** | Số dòng = **112.650**.
  * `Fact Order Payment`: Tổng thanh toán `Payment Value` = **16.008.872,12** | Số lượt = **103.886**.
  * `Fact Seller Lead`: Tổng số **8.000** leads | **842** leads chuyển đổi thành công (Won).

---

## 2. Các bước tạo project SSAS (7 bước nhanh)

1. **Chuẩn bị môi trường:** Cài SQL Server chọn **Analysis Services (Multidimensional Mode)**, bản **Enterprise Developer** (tránh lỗi `StandardDeveloper64` của bản Standard). Cài extension *Microsoft Analysis Services Projects* trong Visual Studio.
2. **Tạo Project:** Visual Studio → *New Project* → *Analysis Services Multidimensional Project* (đặt tên `SSAS`).
3. **Data Source:** Chuột phải *Data Sources* → *New Data Source* → Kết nối OLE DB tới database `OlistDW`. Tab *Impersonation Information* chọn **Use the service account**.  
   *(Lưu ý: Mở SSMS gán quyền `db_datareader` trên database OlistDW cho user `NT Service\MSOLAP$SSAS_ENT`)*.
4. **Data Source View (DSV):** Đưa các bảng `dim_*` và `fact_*` vào DSV. Khai báo Logical Primary Key cho các bảng dim và kéo quan hệ (Relationship):
   * `fact_order_items` liên kết tới `dim_customer`, `dim_seller`, `dim_product`.
   * `dim_customer` và `dim_seller` liên kết tới `dim_location` (qua `location_id`).
   * `dim_product` liên kết tới `dim_product_category` (qua `product_category_name`).
5. **Dimensions:** Chuột phải *Dimensions* → *New Dimension* → Chọn bảng tương ứng, cấu hình thuộc tính và Hierarchy như Mục 3.
6. **Cube:** Chuột phải *Cubes* → *New Cube* → Tạo 3 Measure Group từ 3 bảng fact. Thêm các Named Calculation ở Mục 4.1 vào DSV trước khi tạo cube. Kiểm tra quan hệ tại tab *Dimension Usage*.
7. **Deploy:** Project Properties → *Deployment* → Server: `DESKTOP-AJ19VOT\SSAS_ENT`, Database: `SSAS` → Chuột phải project chọn **Deploy** (hệ thống sẽ tự nạp và process dữ liệu).

---

## 3. Các Dimension và Phân cấp (Hierarchies)

| Dimension | Khóa chính | Thuộc tính chính | Hierarchy (Phân cấp) |
|---|---|---|---|
| **Dim Customer** | Customer Id | Customer Unique Id, Location Id | – |
| **Dim Seller** | Seller Id | Location Id | – |
| **Dim Product** | Product Id | Product Category Name, kích thước, cân nặng... | **Product Hierarchy**: `Product Category Name` → `Product Id` |
| **Dim Product Category** | Product Category Name | Product Category Name English | – |
| **Dim Location** | Location Id | Geolocation State, Geolocation City, Zip Code | **Location Hierarchy**: `Geolocation State` → `Geolocation City` |
| **Dim Review** | Review Id | Review Score, Creation Date (chưa đưa vào cube) | – |
| **Dim Payment Type** | Payment Type | – | – |
| **Dim Lead Origin** | Origin | – | – |
| **Dim Contact Date** | Contact Month (`2018-02`) | Contact Year | **Contact Date Hierarchy**: `Contact Year` → `Contact Month` |

### 💡 Idea cốt lõi khi tạo Hierarchy trong Dimension Designer:
* **Tránh lỗi trùng tên thành phố giữa các bang:** Tại thuộc tính `Geolocation City`, chọn **KeyColumns** là cặp `(geolocation_state, geolocation_city)` và **NameColumn** là `geolocation_city`.
* **Tối ưu quan hệ phân cấp:** Tại tab *Attribute Relationships*, cấu hình quan hệ dạng chuỗi:  
  `Location Id` ➔ `Geolocation City` ➔ `Geolocation State` (và nhánh riêng `Location Id` ➔ `Zip Code`).
* **Product Hierarchy:** Cấu hình quan hệ `Product Id` ➔ `Product Category Name`.

---

## 4. Cube và Dimension Usage

### Thiết lập quan hệ với `Fact Order Items` (Tab Dimension Usage):

| Dimension | Kiểu quan hệ | Bản chất kỹ thuật |
|---|:---:|---|
| **Dim Customer, Dim Seller, Dim Product** | **Regular** | Nối trực tiếp qua khóa ngoại có sẵn trên bảng Fact. |
| **Dim Location** | **Referenced** | Bảng Fact không có `location_id`, nên tham chiếu gián tiếp qua **Dim Customer** (`Intermediate dimension = Dim Customer`, liên kết qua `Location Id`, tích chọn *Materialize*). |

> **Idea nghiệp vụ:** Địa lý trong `Fact Order Items` phản ánh **địa chỉ của khách mua hàng**.

---

### 4.1 Hai Measure Group bổ sung và xử lý Unknown Member

| Measure Group | Measures | Dimension & Kiểu quan hệ |
|---|---|---|
| **Fact Order Payment** | `Payment Value`, `Payment Count` | `Dim Payment Type` (Regular), `Dim Customer` (Regular qua cột tính `customer_id`), `Dim Location` (Referenced qua `Dim Customer`). |
| **Fact Seller Lead** | `Lead Count`, `Won Leads`, `Declared Monthly Revenue` | `Dim Lead Origin` (Regular qua `origin`), `Dim Contact Date` (Regular qua `contact_ym`), `Dim Seller` (Regular qua cột tính `seller_key`). |

### 💡 Idea xử lý dữ liệu ngoại lệ nghiệp vụ (Unknown Member):
1. **830 đơn thanh toán không có dòng hàng:** Đơn bị hủy vẫn có bản ghi thanh toán nhưng không có trong `fact_order_items`. Thêm *Named Calculation* `customer_id` trên `fact_order_payment` (lấy từ order). 830 dòng này rơi vào thành viên **Unknown** của `Dim Customer`, giúp tổng thanh toán giữ trọn vẹn 16.008.872,12 R$ mà không bị mất.
2. **462 lead thắng chưa phát sinh đơn bán:** Trong 842 lead chốt hợp đồng, chỉ 380 người bán đã có đơn hàng (có trong `dim_seller`). Thêm *Named Calculation* `seller_key` trên `fact_seller_lead` (bằng `seller_id` nếu có trong `dim_seller`, ngược lại NULL). 462 lead này sẽ quy về thành viên **Unknown** của `Dim Seller`.
3. **Cấu hình:** Đặt `UnknownMember = Visible` trên `Dim Customer`, `Dim Seller`, `Dim Location`; các cột khóa cho phép NULL đặt `NullProcessing = UnknownMember`.
4. **Lưu ý:** `declared_monthly_revenue` bằng 0 ở các seller đã có đơn, nên chỉ số này có ý nghĩa khi phân tích theo kênh tiếp thị và thời gian (Q23), không theo từng seller.

---

## 5. Hướng dẫn chạy truy vấn MDX

* **Thao tác:** Mở SSMS → Kết nối Server type **Analysis Services** (`DESKTOP-AJ19VOT\SSAS_ENT`) → Chuột phải database `SSAS` → **New Query → MDX**.
* **Nguyên tắc chạy:** Bôi đen **từng câu đơn lẻ rồi nhấn F5**. Không chạy cùng lúc nhiều câu vì SSAS không hỗ trợ đa lệnh trong một batch.
* **Khung cú pháp cơ bản:**
  ```mdx
  SELECT <Tập thuộc tính trên Cột> ON COLUMNS,
         <Tập thuộc tính trên Hàng> ON ROWS
  FROM [Olist DW]
  WHERE ( <Thành viên lát cắt Slice> )
  ```
* **Các hàm chính cần nắm:** `MEMBERS` (lấy toàn bộ thành viên), `CHILDREN` (lấy cấp con trực tiếp), `.PARENT` (đi ngược lên cấp cha), `TOPCOUNT` (lấy top đầu), `ORDER` (sắp xếp), `FILTER` (lọc điều kiện), `NON EMPTY` (bỏ dòng/cột rỗng), `DRILLDOWNLEVELTOP` / `DRILLDOWNMEMBER` (mở rộng phân cấp).

---

## 6. Bộ 23 Truy Vấn MDX Phân Tích Nghiệp Vụ

File nguồn: `ssas/mdx/01_olist_mdx_queries.mdx` (Q1 - Q15) và `03_olist_mdx_payment_lead.mdx` (Q16 - Q23).

---

### 6.1 Roll-up (Gộp từ mức chi tiết lên mức tổng quát)

> **Idea:** Tổng hợp số liệu từ cấp nhỏ lên cấp cao hơn dọc theo phân cấp phân tích.

#### Q1 — Doanh thu theo Bang (Cấp State)
* **Idea:** Cuộn toàn bộ chi tiết đơn hàng lên 27 bang của Brazil để xem phân bổ doanh thu và cước vận chuyển.
```mdx
SELECT { [Measures].[Price], [Measures].[Freight Value], [Measures].[Fact Order Items Count] } ON COLUMNS,
       NON EMPTY [Dim Location].[Location Hierarchy].[Geolocation State].MEMBERS ON ROWS
FROM [Olist DW]
```
* **Kết quả mẫu:** AC: 15.982,95 | AL: 80.314,81 | BA: 511.349,99 | SP: 5.202.955,05 | ... (27 bang).

#### Q2 — Doanh thu theo Nhóm sản phẩm (Category Level)
* **Idea:** Gộp từ mức sản phẩm lên danh mục ngành hàng, sắp xếp giảm dần theo doanh thu bằng `ORDER(..., BDESC)`.
```mdx
SELECT { [Measures].[Price], [Measures].[Fact Order Items Count] } ON COLUMNS,
       NON EMPTY ORDER([Dim Product].[Product Hierarchy].[Product Category Name].MEMBERS, [Measures].[Price], BDESC) ON ROWS
FROM [Olist DW]
```
* **Kết quả mẫu:** Top 1 `beleza_saude` (1.258.681,34), top 2 `relogios_presentes` (1.205.005,68), top 3 `cama_mesa_banho` (1.036.988,68)...

#### Q3 — Gộp từ Thành phố lên Bang rồi lên Toàn quốc bằng `.PARENT`
* **Idea:** Dùng thuộc tính `.PARENT` để đi ngược từng bậc phân cấp địa lý: Thành phố `campinas` → Bang `SP` → Toàn quốc (`All`).
```mdx
SELECT { [Measures].[Price], [Measures].[Fact Order Items Count] } ON COLUMNS,
       { [Dim Location].[Location Hierarchy].[Geolocation City].&[SP]&[campinas],
         [Dim Location].[Location Hierarchy].[Geolocation City].&[SP]&[campinas].PARENT,
         [Dim Location].[Location Hierarchy].[Geolocation City].&[SP]&[campinas].PARENT.PARENT } ON ROWS
FROM [Olist DW]
```
* **Kết quả mẫu:** `campinas`: 187.844,53 ➔ `SP`: 5.202.955,05 ➔ `All`: 13.591.643,70 (112.650 dòng hàng).

#### Q4 — Cộng dồn doanh thu các Bang từ lớn đến nhỏ (Tổng lũy kế)
* **Idea:** Tính tổng tích lũy (Running Total) theo xếp hạng doanh thu bang để phân tích tỷ trọng đóng góp.
```mdx
WITH SET [S] AS ORDER(NONEMPTY([Dim Location].[Location Hierarchy].[Geolocation State].MEMBERS, [Measures].[Price]), [Measures].[Price], BDESC)
MEMBER [Measures].[Luy Ke Price] AS SUM(HEAD([S], RANK([Dim Location].[Location Hierarchy].CURRENTMEMBER, [S])), [Measures].[Price])
SELECT { [Measures].[Price], [Measures].[Luy Ke Price] } ON COLUMNS,
       TOPCOUNT([S], 8) ON ROWS
FROM [Olist DW]
```
* **Kết quả mẫu:** SP: 5.202.955,05 | RJ (lũy kế): 7.027.047,72 | MG (lũy kế): 8.612.355,75 | RS (lũy kế): 9.362.659,77...

---

### 6.2 Drill-down (Khoét từ mức tổng quát xuống chi tiết)

> **Idea:** Mở rộng từ nút phân cấp cha xuống các nút phân cấp con bên dưới để tìm ra chi tiết cấu thành.

#### Q5 — Từ 3 Bang lớn (SP, RJ, MG) khoét xuống Top 3 Thành phố của mỗi Bang
* **Idea:** Dùng `DRILLDOWNLEVELTOP` để tự động mở rộng từng bang cha và chỉ lấy ra 3 thành phố dẫn đầu của mỗi bang đó.
```mdx
SELECT { [Measures].[Price], [Measures].[Fact Order Items Count] } ON COLUMNS,
       DRILLDOWNLEVELTOP({ [Dim Location].[Location Hierarchy].[Geolocation State].&[SP],
                           [Dim Location].[Location Hierarchy].[Geolocation State].&[RJ],
                           [Dim Location].[Location Hierarchy].[Geolocation State].&[MG] }, 3, , [Measures].[Price]) ON ROWS
FROM [Olist DW]
```
* **Kết quả mẫu:**
  * `SP` ➔ `sao paulo` (1.914.924,54), `campinas` (187.844,53), `guarulhos` (144.268,39).
  * `RJ` ➔ `rio de janeiro` (992.538,86), `niteroi` (91.135,16), `nova iguacu` (27.240,65).
  * `MG` ➔ `belo horizonte` (410.024,50), `juiz de fora` (43.682,75), `uberlandia` (40.916,73).

#### Q6 — Từ nhóm 'cama_mesa_banho' khoét xuống 10 Sản phẩm doanh thu cao nhất
* **Idea:** Dùng `.CHILDREN` kết hợp `TOPCOUNT` để lấy 10 mã sản phẩm bán chạy nhất trong một danh mục ngành hàng.
```mdx
SELECT { [Measures].[Price], [Measures].[Fact Order Items Count] } ON COLUMNS,
       TOPCOUNT([Dim Product].[Product Hierarchy].[Product Category Name].&[cama_mesa_banho].CHILDREN, 10, [Measures].[Price]) ON ROWS
FROM [Olist DW]
```
* **Kết quả mẫu:** 10 sản phẩm cụ thể, sản phẩm dẫn đầu đạt 43.025,56 R$ (488 dòng hàng).

#### Q7 — Top 3 Nhóm sản phẩm, mỗi nhóm khoét xuống Top 3 Sản phẩm bán chạy nhất
* **Idea:** Lồng ghép `TOPCOUNT` vào `DRILLDOWNLEVELTOP` để tự động bung chi tiết sản phẩm cho 3 ngành hàng lớn nhất thị trường.
```mdx
SELECT { [Measures].[Price] } ON COLUMNS,
       DRILLDOWNLEVELTOP(TOPCOUNT([Dim Product].[Product Hierarchy].[Product Category Name].MEMBERS, 3, [Measures].[Price]), 3, , [Measures].[Price]) ON ROWS
FROM [Olist DW]
```
* **Kết quả mẫu:** `beleza_saude` bung ra 3 sản phẩm; `relogios_presentes` bung ra 3 sản phẩm; `cama_mesa_banho` bung ra 3 sản phẩm.

---

### 6.3 Slice and Dice (Cắt lát và Cắt khối con)

> **Idea:** Giới hạn không gian phân tích bằng cách cố định 1 chiều (Slice qua mệnh đề `WHERE`) hoặc cắt khối con đa chiều (Dice qua Subselect / `FILTER`).

#### Q8 — [Slice] Cắt theo Bang SP: Top 10 Nhóm sản phẩm bán chạy ở SP
* **Idea:** Cố định chiều địa lý tại bang São Paulo bằng `WHERE (...)` để xem cơ cấu tiêu dùng tại riêng bang này.
```mdx
SELECT { [Measures].[Price], [Measures].[Fact Order Items Count] } ON COLUMNS,
       TOPCOUNT([Dim Product].[Product Hierarchy].[Product Category Name].MEMBERS, 10, [Measures].[Price]) ON ROWS
FROM [Olist DW]
WHERE ( [Dim Location].[Location Hierarchy].[Geolocation State].&[SP] )
```
* **Kết quả mẫu:** Tại riêng SP: `cama_mesa_banho` (478.284,52), `beleza_saude` (462.305,22), `relogios_presentes` (435.009,92)...

#### Q9 — [Slice 2 Chiều] Cắt đồng thời tại Bang SP và Nhóm 'beleza_saude'
* **Idea:** Cắt lát giao giữa 1 bang và 1 ngành hàng cụ thể, kết quả trả về chính xác 1 dòng đo lường tổng hợp.
```mdx
SELECT { [Measures].[Price], [Measures].[Freight Value], [Measures].[Fact Order Items Count] } ON COLUMNS
FROM [Olist DW]
WHERE ( [Dim Location].[Location Hierarchy].[Geolocation State].&[SP],
        [Dim Product].[Product Hierarchy].[Product Category Name].&[beleza_saude] )
```
* **Kết quả mẫu:** Doanh thu `Price`: **462.305,22** | Cước `Freight`: **57.341,58** | Số lượng: **4.204** dòng (khớp 100% với SQL).

#### Q10 — [Dice] Khối con (Sub-cube): 3 Bang $\times$ 3 Nhóm sản phẩm bằng Subselect
* **Idea:** Dùng subselect lồng trong `FROM` để thu nhỏ không gian Cube thành ma trận giữa 3 bang (SP, RJ, MG) và 3 ngành hàng lớn.
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
* **Kết quả mẫu:** MG: 399.921,47 | RJ: 418.481,89 | SP: 1.326.946,75.

#### Q11 — [Dice] Lọc theo điều kiện logic: Các Thành phố của SP có doanh thu > 100.000 R$
* **Idea:** Dùng hàm `FILTER` để lọc các thành phố con thuộc bang SP thỏa mãn điều kiện ngưỡng doanh thu.
```mdx
SELECT { [Measures].[Price], [Measures].[Fact Order Items Count] } ON COLUMNS,
       FILTER([Dim Location].[Location Hierarchy].[Geolocation State].&[SP].CHILDREN, [Measures].[Price] > 100000) ON ROWS
FROM [Olist DW]
```
* **Kết quả mẫu:** 4 thành phố đạt điều kiện: `campinas`, `guarulhos`, `sao bernardo do campo`, `sao paulo`.

---

### 6.4 Pivot (Xoay trục) và Calculated Members

> **Idea:** Đổi chiều hiển thị giữa Cột và Hàng để thay đổi góc nhìn, hoặc tạo thêm chỉ số tính toán phát sinh (`WITH MEMBER`).

#### Q12 — Hàng = Top 5 Nhóm sản phẩm, Cột = 3 Bang lớn (SP, RJ, MG)
* **Idea:** Đặt nhóm ngành hàng trên hàng và các bang trên cột để so sánh doanh thu từng mặt hàng giữa các bang.
```mdx
SELECT { [Dim Location].[Location Hierarchy].[Geolocation State].&[SP],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[RJ],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[MG] } ON COLUMNS,
       TOPCOUNT([Dim Product].[Product Hierarchy].[Product Category Name].MEMBERS, 5, [Measures].[Price]) ON ROWS
FROM [Olist DW]
WHERE ( [Measures].[Price] )
```
* **Kết quả mẫu:** Cột SP/RJ/MG; Hàng: `beleza_saude` (SP 462.305,22 | RJ 145.298,62 | MG 157.558,30)...

#### Q13 — Xoay ngược trục của Q12: Hàng = Bang, Cột = Nhóm sản phẩm
* **Idea:** Hoán đổi trục: Chuyển Bang xuống hàng và Nhóm sản phẩm lên cột để nhìn cơ cấu giỏ hàng theo từng địa phương.
```mdx
SELECT TOPCOUNT([Dim Product].[Product Hierarchy].[Product Category Name].MEMBERS, 5, [Measures].[Price]) ON COLUMNS,
       { [Dim Location].[Location Hierarchy].[Geolocation State].&[SP],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[RJ],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[MG] } ON ROWS
FROM [Olist DW]
WHERE ( [Measures].[Price] )
```
* **Kết quả mẫu:** Hàng SP/RJ/MG; Cột: `beleza_saude`, `relogios_presentes`, `cama_mesa_banho`, `esporte_lazer`, `informatica_acessorios`.

#### Q14 — Đưa các Thước đo (Measures) xuống Hàng, Bang lên Cột
* **Idea:** Xoay các độ đo (`Price`, `Freight Value`, `Item Count`) xuống làm tiêu đề hàng của báo cáo so sánh bang.
```mdx
SELECT { [Dim Location].[Location Hierarchy].[Geolocation State].&[SP],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[RJ],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[MG] } ON COLUMNS,
       { [Measures].[Price], [Measures].[Freight Value], [Measures].[Fact Order Items Count] } ON ROWS
FROM [Olist DW]
```
* **Kết quả mẫu:** Hàng `Price`: SP 5.202.955,05 | RJ 1.824.092,67 | MG 1.585.308,03; Hàng `Count`: SP 47.449 | RJ 14.579 | MG 13.129.

#### Q15 — Thành viên tính toán: Giá trung bình mỗi món hàng (Avg Price)
* **Idea:** Dùng `WITH MEMBER` và hàm `IIF` tính đơn giá bình quân (`Price / Item Count`) trên ma trận Bang $\times$ Ngành hàng.
```mdx
WITH MEMBER [Measures].[Avg Price] AS 
    IIF([Measures].[Fact Order Items Count] = 0, NULL, [Measures].[Price] / [Measures].[Fact Order Items Count]), 
    FORMAT_STRING = '#,##0.00'
SELECT TOPCOUNT([Dim Product].[Product Hierarchy].[Product Category Name].MEMBERS, 4, [Measures].[Price]) ON COLUMNS,
       { [Dim Location].[Location Hierarchy].[Geolocation State].&[SP],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[RJ],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[MG] } ON ROWS
FROM [Olist DW]
WHERE ( [Measures].[Avg Price] )
```
* **Kết quả mẫu:**
  * Bang SP: `beleza_saude`: 109,97 | `relogios_presentes`: 190,71 | `cama_mesa_banho`: 91,36 | `esporte_lazer`: 105,36.
  * Bang RJ: `beleza_saude`: 136,56 | `relogios_presentes`: 212,10 | `cama_mesa_banho`: 90,05 | `esporte_lazer`: 120,22.
  * Bang MG: `beleza_saude`: 145,08 | `relogios_presentes`: 194,28 | `cama_mesa_banho`: 97,40 | `esporte_lazer`: 116,69.

---

### 6.5 Truy vấn trên Fact Order Payment và Fact Seller Lead (Q16 đến Q23)

> **Lưu ý:** Các dòng mồ côi rơi vào thành viên **Unknown** của các Dimension tương ứng (xem Mục 4.1).

#### Q16 — [Roll-up] Giá trị thanh toán theo hình thức thanh toán
* **Idea:** Tổng hợp doanh thu thanh toán theo từng phương thức (thẻ tín dụng, phiếu ngân hàng boleto, voucher, thẻ ghi nợ).
```mdx
SELECT { [Measures].[Payment Value], [Measures].[Payment Count] } ON COLUMNS,
       ORDER([Dim Payment Type].[Payment Type].[Payment Type].MEMBERS, [Measures].[Payment Value], BDESC) ON ROWS
FROM [Olist DW]
```
* **Kết quả mẫu:** `credit_card` chiếm áp đảo với 12.542.084,19 R$ / 76.795 lượt | `boleto` 2.869.361,27 / 19.784 | `voucher` 379.436,87 / 5.775 | `debit_card` 217.989,79 / 1.529.

#### Q17 — [Slice] Chỉ lấy thanh toán bằng thẻ tín dụng (credit_card) tại Top 8 Bang
* **Idea:** Lọc cố định phương thức `credit_card` qua `WHERE` và hiển thị 8 bang có giá trị cà thẻ cao nhất.
```mdx
SELECT { [Measures].[Payment Value], [Measures].[Payment Count] } ON COLUMNS,
       TOPCOUNT([Dim Location].[Location Hierarchy].[Geolocation State].MEMBERS, 8, [Measures].[Payment Value]) ON ROWS
FROM [Olist DW]
WHERE ( [Dim Payment Type].[Payment Type].&[credit_card] )
```
* **Kết quả mẫu:** SP: 4.625.784,80 / 31.927 lượt | RJ: 1.719.332,62 / 10.223 | MG: 1.460.905,12 / 9.004 | RS: 660.689,50 / 3.966...

#### Q18 — [Pivot] Hình thức thanh toán đưa lên Cột, Top 5 Bang trên Hàng
* **Idea:** Ma trận so sánh thói quen lựa chọn phương thức thanh toán của người tiêu dùng tại 5 bang dẫn đầu.
```mdx
SELECT [Dim Payment Type].[Payment Type].[Payment Type].MEMBERS ON COLUMNS,
       TOPCOUNT([Dim Location].[Location Hierarchy].[Geolocation State].MEMBERS, 5, [Measures].[Payment Value]) ON ROWS
FROM [Olist DW]
WHERE ( [Measures].[Payment Value] )
```
* **Kết quả mẫu:** Bang SP: `boleto` 1.071.968,52 | `credit_card` 4.625.784,80 | `debit_card` 85.898,49 | `voucher` 138.596,26...

#### Q19 — [Dice] Hai hình thức (credit_card, boleto) $\times$ Ba bang (SP, RJ, MG)
* **Idea:** Cắt ma trận kiểm tra tương quan giữa 2 hình thức thanh toán chủ chốt với 3 bang lớn nhất.
```mdx
SELECT { [Dim Payment Type].[Payment Type].&[credit_card], [Dim Payment Type].[Payment Type].&[boleto] } ON COLUMNS,
       { [Dim Location].[Location Hierarchy].[Geolocation State].&[SP],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[RJ],
         [Dim Location].[Location Hierarchy].[Geolocation State].&[MG] } ON ROWS
FROM [Olist DW]
WHERE ( [Measures].[Payment Value] )
```
* **Kết quả mẫu:** SP: 4.625.784,80 (thẻ) / 1.071.968,52 (boleto); RJ: 1.719.332,62 / 326.296,49; MG: 1.460.905,12 / 338.448,17.

#### Q20 — [Roll-up / Calculated Member] Số lead, lead thắng và Tỷ lệ chuyển đổi theo Kênh tiếp thị
* **Idea:** Dùng `WITH MEMBER` tính tỷ lệ chốt đơn (`Won Leads / Lead Count`) theo từng kênh thu hút người bán (`origin`).
```mdx
WITH MEMBER [Measures].[Ty Le Thang] AS 
    IIF([Measures].[Lead Count] = 0, NULL, [Measures].[Won Leads] / [Measures].[Lead Count]), 
    FORMAT_STRING = "Percent"
SELECT { [Measures].[Lead Count], [Measures].[Won Leads], [Measures].[Ty Le Thang] } ON COLUMNS,
       ORDER([Dim Lead Origin].[Origin].[Origin].MEMBERS, [Measures].[Lead Count], BDESC) ON ROWS
FROM [Olist DW]
```
* **Kết quả mẫu:** `organic_search`: 2.296 leads / 271 thắng / 11,80% | `paid_search`: 1.586 / 195 / 12,30% | `social`: 1.350 / 75 / 5,56%... (tổng: 8.000 leads / 842 thắng).

#### Q21 — [Drill-down] Từ Năm 2017 & 2018 khoét sâu xuống từng Tháng: Số lead và lead thắng
* **Idea:** Dùng `DRILLDOWNMEMBER` mở rộng phân cấp thời gian từ năm 2017, 2018 xuống chi tiết từng tháng liên hệ.
```mdx
SELECT { [Measures].[Lead Count], [Measures].[Won Leads] } ON COLUMNS,
       DRILLDOWNMEMBER({ [Dim Contact Date].[Contact Date Hierarchy].[Contact Year].MEMBERS },
                       { [Dim Contact Date].[Contact Date Hierarchy].[Contact Year].&[2017],
                         [Dim Contact Date].[Contact Date Hierarchy].[Contact Year].&[2018] }) ON ROWS
FROM [Olist DW]
```
* **Kết quả mẫu:** Năm 2017 có 2.002 leads / 61 thắng (tháng 06 đến tháng 12) | Năm 2018 có 5.998 leads / 781 thắng (tháng 01 đến tháng 05).

#### Q22 — [Pivot] Kênh tiếp thị trên Cột, 5 tháng năm 2018 trên Hàng
* **Idea:** Ma trận theo dõi diễn biến thu hút leads của các kênh marketing qua từng tháng trong năm 2018.
```mdx
SELECT [Dim Lead Origin].[Origin].[Origin].MEMBERS ON COLUMNS,
       [Dim Contact Date].[Contact Date Hierarchy].[Contact Year].&[2018].CHILDREN ON ROWS
FROM [Olist DW]
WHERE ( [Measures].[Lead Count] )
```
* **Kết quả mẫu:** Tháng 2018-01: `organic_search` 412, `paid_search` 170, `social` 162... (gồm 5 hàng từ tháng 01 đến tháng 05).

#### Q23 — [Slice] Doanh thu khai báo của lead thắng theo Kênh tiếp thị, chỉ xét năm 2018
* **Idea:** Lọc riêng năm 2018 bằng subselect để phân tích quy mô doanh thu tự khai báo (`Declared Monthly Revenue`) của người bán chốt thành công.
```mdx
SELECT { [Measures].[Won Leads], [Measures].[Declared Monthly Revenue] } ON COLUMNS,
       NON EMPTY ORDER([Dim Lead Origin].[Origin].[Origin].MEMBERS, [Measures].[Declared Monthly Revenue], BDESC) ON ROWS
FROM ( SELECT [Dim Contact Date].[Contact Date Hierarchy].[Contact Year].&[2018] ON COLUMNS FROM [Olist DW] )
```
* **Kết quả mẫu:** `organic_search`: 255 lead thắng / 51.016.000 R$ | `paid_search`: 175 / 9.044.000 R$ | `unknown`: 181 / 295.000 R$...

---

## 7. Đối Chiếu Kết Quả Với SQL

| Chỉ số kiểm tra | Kết quả MDX | Kết quả truy vấn SQL | Đánh giá |
|---|:---:|:---:|:---:|
| **Tổng Price / Số dòng hàng** | **13.591.643,70** / **112.650** | **13.591.643,70** / **112.650** | Khớp 100% |
| **Lát cắt Q9:** Bang SP $\times$ nhóm `beleza_saude` | **462.305,22** / **4.204** | **462.305,22** / **4.204** | Khớp 100% |
| **Tổng Payment Value / Số lượt thanh toán** | **16.008.872,12** / **103.886** | **16.008.872,12** / **103.886** | Khớp 100% |
| **Payment Value thẻ tín dụng (`credit_card`)** | **12.542.084,19** / **76.795** | **12.542.084,19** / **76.795** | Khớp 100% |
| **Tổng Leads / Số Leads chốt thành công** | **8.000** / **842** | **8.000** / **842** | Khớp 100% |

**Lệnh SQL kiểm tra lát cắt Q9:**
```sql
SELECT SUM(f.price), COUNT(*)
FROM dbo.fact_order_items f
JOIN dbo.dim_customer c ON c.customer_id = f.customer_id
JOIN dbo.dim_location l ON l.location_id = c.location_id
JOIN dbo.dim_product  p ON p.product_id  = f.product_id
WHERE l.geolocation_state = 'SP' AND p.product_category_name = 'beleza_saude';
-- Kết quả: 462305.22 / 4204
```

---

## 8. Các Lỗi Thường Gặp và Cách Xử Lý

| Lỗi gặp phải | Nguyên nhân gốc rễ | Cách xử lý |
|---|---|---|
| `edition 'StandardDeveloper64' ... not supported by the client` | Client Visual Studio cũ không hỗ trợ bản Standard Developer. | Cài đặt SSAS bằng bản **Enterprise Developer**. |
| `A connection cannot be made` khi Deploy | Sai tên server (named instance phải là `Máy\Instance`) hoặc service SSAS chưa chạy. | Kiểm tra lại tên server trong Project Properties → Deployment. Bật service trong `services.msc`. |
| `A connection could not be made to the data source` | Tài khoản SSAS chưa có quyền đọc database `OlistDW`. | Cấp quyền `db_datareader` trên database OlistDW cho `NT Service\MSOLAP$<instance>`. Tại Data Source, chọn *Use the service account*. |
| `Granularity is not defined` (trên Referenced Dimension) | Thiếu thuộc tính xác định mức chi tiết (granularity) của chiều tham chiếu `Dim Location`. | Thiết lập trong giao diện tab **Dimension Usage** (*Define Relationship* → loại *Referenced* qua `Dim Customer`), không sửa tay trong file XML. |
| `Multiple statements are not allowed` khi chạy MDX | Nhấn F5 khi đang chọn cùng lúc nhiều câu truy vấn MDX trong SSMS. | SSAS chỉ hỗ trợ thực thi từng câu đơn lẻ. **Bôi đen 1 câu duy nhất rồi nhấn F5.** |
