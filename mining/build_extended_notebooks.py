"""Build portable notebooks for proposal steps 1-3 and Tzy's K-Means step 4."""
from pathlib import Path
import nbformat as nbf

ROOT=Path(__file__).resolve().parents[1]
md,code=nbf.v4.new_markdown_cell,nbf.v4.new_code_cell
base=(ROOT/'mining/seller_segmentation.py').read_text(encoding='utf-8').split('if __name__ == "__main__":')[0]
ext=(ROOT/'mining/seller_features_extended.py').read_text(encoding='utf-8').split("if __name__=='__main__':")[0]
ext=ext.replace('from __future__ import annotations','').replace('from seller_segmentation import load_sources, prepare_data, create_features, file_sha256','').replace('    from seller_segmentation import REQUIRED','')
kmeans=(ROOT/'mining/seller_kmeans.py').read_text(encoding='utf-8').split("if __name__=='__main__':")[0]
kmeans=kmeans.replace('    from seller_features_extended import REGIONS','')
regions=ext[ext.index('REGIONS = '):ext.index('\n\ndef normalize_city')]

def save(name,cells):
    nb=nbf.v4.new_notebook(cells=cells,metadata={'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'},
                                                     'language_info':{'name':'python','version':'3.12'}})
    nbf.validate(nb);nbf.write(nb,ROOT/'notebooks'/name)

save('seller_segmentation_features_v2.ipynb',[
md('''# Seller Segmentation theo đề xuất leader
**Tzy — bước 1 đến 3, cập nhật 27/11/2026.**

Tính toàn bộ đặc trưng đề xuất ở cấp seller, chọn bộ 12–15 cột bằng dữ liệu thật, xuất cùng ma trận cho K-Means/GMM/DBSCAN.
Nguồn CSV thô hoặc SQLite giữ nguyên lịch sử đơn; tỷ lệ hủy dùng cả đơn chưa giao có item xác định seller.
Notebook chứa đầy đủ mã, không yêu cầu import file trong repo. `SOURCE` phải chứa đủ chín bảng nguồn.
'''),
md('''## Bước 1 Chuẩn bị dữ liệu và bảo vệ mức chi tiết
Kiểm tra khóa và quan hệ, gom review trước nối. Chỉ đơn delivered có ngày mua hợp lệ tạo cohort bán hàng.
Geolocation gom median theo zip, fallback city/state; không nhân dòng item. Các chỉ số review, giao hàng, thanh toán được tính từ seller-order.
'''),code(base),code(ext),
code('''import os
ROOT=Path.cwd().parent if Path.cwd().name=='notebooks' else Path.cwd()
SOURCE=Path(os.environ.get('OLIST_SOURCE',str(ROOT/'data/raw/csv')))
OUTPUT=Path(os.environ.get('OLIST_FEATURE_OUTPUT',str(ROOT/'artifacts/seller_segmentation_v2')))
MIN_ORDERS=3
profiles,matrix,audit,metadata=run_extended(SOURCE,OUTPUT,MIN_ORDERS)
display(pd.DataFrame(list(audit['source_rows'].items()),columns=['Nguồn','Số dòng']))
print('Ngày tham chiếu:',audit['reference_date'])
print('Seller delivered:',len(profiles),'| Seller mô hình:',len(matrix))
display(pd.DataFrame(list(audit['seller_coordinate_sources'].items()),columns=['Fallback seller','Số lượng']))
'''),
md('''## Bước 2 Tạo đặc trưng và chọn cohort
Ngành thiếu được giữ trong `__unknown__`; `known_category_count` giữ lại để so baseline. HHI, entropy, hot_score, thị phần và price_index đều dùng tỷ trọng doanh thu.
Tăng trưởng so các tháng đầy đủ chung: không so cả năm 2017 với phần năm 2018. `growth_exposure` chỉ là mô tả, kèm coverage.
Seller dưới 3 đơn vẫn nằm trong bảng đặc trưng, chỉ tách khỏi mô hình chính; đã xuất ma trận toàn bộ seller để kiểm tra độ nhạy.
'''),code('''display(profiles.head())
display(profiles[['order_count','category_count','category_hhi','price_index','avg_ship_distance_km','cancel_rate','repeat_customer_rate']].describe().T)
print('Khoảng tăng trưởng:',audit['growth_periods'])
print('Marketing có đối ứng trong cohort:',audit['marketing_matched_eligible_sellers'])
print('Tỷ trọng doanh số giữ lại:',audit['main_cohort_sales_coverage'])
'''),
md('''## Bước 3 Tiền xử lý và kiểm tra tương quan
Median → log1p cho số đếm/giá/thời gian/khoảng cách → StandardScaler. Giữ đại diện theo thứ tự ưu tiên; bỏ cột có |Pearson| ≥ 0,75 với cột đã giữ.
Theo dõi các cặp |r| > 0,5. Không one-hot ngành/bang; không đưa marketing vào mô hình; giữ ngoại lệ để đánh giá độ nhạy.
'''),code('''display(pd.DataFrame(metadata['selection_decisions']))
display(pd.read_csv(OUTPUT/'correlation_pairs.csv'))
assert np.isfinite(matrix.to_numpy()).all()
np.testing.assert_allclose(matrix.mean(),0,atol=1e-10)
np.testing.assert_allclose(matrix.std(ddof=0),1,atol=1e-10)
cohort=profiles.loc[profiles.model_eligible].set_index('seller_id')
restored=cohort[metadata['feature_order']].fillna(metadata['medians']).astype(float)
restored[metadata['log1p_features']]=np.log1p(restored[metadata['log1p_features']])
restored=(restored-pd.Series(metadata['mean']))/pd.Series(metadata['scale'])
np.testing.assert_allclose(restored,matrix)
print('PASS: finite, zero mean, unit std, reproducible preprocessing:',matrix.shape)
from IPython.display import display,Image
display(Image(filename=str(OUTPUT/'candidate_correlations.png')))
display(Image(filename=str(OUTPUT/'feature_distributions.png')))
'''),md('''## Bàn giao
Dùng `seller_model_input.csv` và cùng thứ tự seller cho ba thuật toán. `seller_features.csv` chưa chuẩn hóa dùng diễn giải.
Các file JSON lưu hash nguồn, quyết định chọn cột, median/mean/scale và số liệu kiểm tra. `seller_model_input_all.csv` dùng kiểm tra độ nhạy với seller ít đơn.
`review_answer_hours` mô tả thời gian hoàn thành phản hồi khảo sát, không được dùng làm KPI phản hồi của seller.
''')])

save('seller_segmentation_kmeans.ipynb',[
md('''# K-Means Seller Segmentation
**Tzy — bước 4.** Dùng ma trận từ notebook đặc trưng v2; seed 42, n_init 30.
Đây là mô hình K-Means ứng viên để Phu0c so sánh GMM/DBSCAN, chưa chốt mô hình phân khúc cuối cùng.
'''),code(kmeans+'\n'+regions),
code('''import os
ROOT=Path.cwd().parent if Path.cwd().name=='notebooks' else Path.cwd()
INPUTS=Path(os.environ.get('OLIST_FEATURE_OUTPUT',str(ROOT/'artifacts/seller_segmentation_v2')))
OUTPUT=Path(os.environ.get('OLIST_KMEANS_OUTPUT',str(ROOT/'artifacts/seller_kmeans')))
details,metrics,summary=run_kmeans(INPUTS,OUTPUT)
display(metrics)
print('k được chọn:',details['selected_k'])
print('Quy tắc:',details['selection_rule'])
'''),md('''## Elbow và Silhouette
Quét k=2..10, tính Silhouette trên toàn bộ cohort. Chọn Silhouette cao nhất trong các k có mọi cụm ≥2% cohort; biểu đồ Elbow hỗ trợ kiểm tra, không khẳng định có điểm khuỷu rõ khi dữ liệu không cho thấy.
'''),code('''from IPython.display import display,Image
display(Image(filename=str(OUTPUT/'elbow_silhouette.png')))
display(pd.DataFrame([details['selected_metrics']]))
'''),md('''## Độ ổn định và ảnh hưởng của seller ít đơn
Chạy 10 seed và đối chiếu ARI với seed 42. Chạy cùng k trên cohort toàn bộ seller, fit lại scaler, rồi tính ARI trên seller chung. ARI khác nhau phản ánh cả thay đổi cohort lẫn chuẩn hóa.
'''),code('''display(pd.read_csv(OUTPUT/'kmeans_stability.csv'))
display(pd.read_csv(OUTPUT/'cohort_sensitivity_metrics.csv'))
print('ARI chung khi giữ seller ít đơn:',details['all_seller_same_k_ari_on_shared_sellers'])
print('Silhouette thấp nghĩa là cụm còn chồng lấn; ổn định theo seed không chứng minh các phân khúc tách biệt tốt.')
'''),md('''## Profile và bàn giao OLAP
PCA 2D chỉ để xem; K-Means được fit trên toàn bộ đặc trưng đã chọn. Mã C0..Ck là nhãn kỹ thuật, chưa phải tên phân khúc nghiệp vụ cuối cùng.
'''),code('''display(summary)
display(Image(filename=str(OUTPUT/'pca_kmeans.png')))
display(Image(filename=str(OUTPUT/'cluster_centroids.png')))
print('Variance PCA:',details['pca_explained_variance_ratio'])
print('Hạn chế:',*details['limitations'],sep='\\n- ')
dimension=pd.read_csv(OUTPUT/'seller_segment_dimension.csv')
assert dimension.seller_id.is_unique
print('Bàn giao dimension:',len(dimension),'seller')
'''),md('''## Phần leader tiếp tục
Chạy GMM và DBSCAN trên đúng ma trận v2; so ba mô hình, chọn mô hình cuối, đặt tên phân khúc dựa vào profile và chính sách kinh doanh. Dùng bảng mapping seller–segment–region cùng script SQL/SSAS để nối phân tích khai phá với OLAP. Chưa công bố K-Means là mô hình tốt nhất trong ba phương pháp.
''')])
print('Generated features_v2 and kmeans notebooks')
