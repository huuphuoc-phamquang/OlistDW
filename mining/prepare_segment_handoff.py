"""Generate transaction-safe SQL and add Segment/Region bindings to SSAS source."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/seller_clustering_v3'
# Nhãn v3 (K-Means k=5, notebooks/seller_clustering_v3.ipynb); số cụm đã đánh lại theo doanh số giảm dần
V3_NAMES={0:'C0 Chủ lực đa ngành',1:'C1 Giá cao, giao xa',2:'C2 Ngưng hoạt động',3:'C3 Mới, bán gần',4:'C4 Giao trễ, review thấp'}
OUTSIDE={'Insufficient orders':'Ít đơn (dưới 3 đơn)','No eligible delivered sales':'Chưa có đơn delivered'}
# Bảng của Tzy có đủ 3.095 seller và vùng; seller ngoài cohort giữ lý do loại
base=pd.read_csv(ROOT/'artifacts/seller_kmeans/seller_segment_dimension.csv',dtype=str)
v3=pd.read_csv(OUT/'seller_assignments.csv',dtype={'seller_id':str}).set_index('seller_id')['kmeans'].map(V3_NAMES)
data=base[['seller_id','seller_region']].assign(seller_segment=base.seller_id.map(v3).fillna(base.seller_segment.map(OUTSIDE)))
assert set(v3.index)<=set(base.seller_id) and data.seller_segment.isin(V3_NAMES.values()).sum()==len(v3)
assert data.seller_id.is_unique and not data.isna().any().any()
def literal(v):return "N'"+v.replace("'","''")+"'"
parts=["""-- Phân khúc seller v3 (K-Means k=5), sinh bởi mining/prepare_segment_handoff.py.
-- Run with sqlcmd -S <server> -E -b -d <explicit_target_database> -i <this_file>
-- SQL Server database must already contain dbo.dim_seller. No source rows are deleted.
SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRY
BEGIN TRANSACTION;
-- COLLATE DATABASE_DEFAULT: bảng tạm theo collation của database đích, không theo tempdb
CREATE TABLE #segments(seller_id nvarchar(255) COLLATE DATABASE_DEFAULT NOT NULL PRIMARY KEY,
 seller_segment nvarchar(100) COLLATE DATABASE_DEFAULT NOT NULL, seller_region nvarchar(50) COLLATE DATABASE_DEFAULT NOT NULL);
"""]
for start in range(0,len(data),500):
    values=[ '('+','.join(literal(row[c]) for c in ['seller_id','seller_segment','seller_region'])+')'
            for _,row in data.iloc[start:start+500].iterrows()]
    parts.append('INSERT INTO #segments VALUES\n'+',\n'.join(values)+';\n')
parts.append("""
IF EXISTS (SELECT 1 FROM #segments s WHERE NOT EXISTS (SELECT 1 FROM dbo.dim_seller d WHERE d.seller_id=s.seller_id))
 THROW 50001, 'Mapping contains sellers absent from target dim_seller', 1;
IF EXISTS (SELECT 1 FROM dbo.dim_seller d WHERE NOT EXISTS (SELECT 1 FROM #segments s WHERE s.seller_id=d.seller_id))
 THROW 50002, 'Target dim_seller has sellers absent from mapping; no partial update', 1;
IF COL_LENGTH('dbo.dim_seller','seller_segment') IS NULL
 EXEC(N'ALTER TABLE dbo.dim_seller ADD seller_segment nvarchar(100) NULL');
IF COL_LENGTH('dbo.dim_seller','seller_region') IS NULL
 EXEC(N'ALTER TABLE dbo.dim_seller ADD seller_region nvarchar(50) NULL');
EXEC(N'UPDATE d SET seller_segment=s.seller_segment,seller_region=s.seller_region
 FROM dbo.dim_seller d JOIN #segments s ON s.seller_id=d.seller_id');
EXEC(N'SELECT seller_segment, COUNT(*) AS sellers FROM dbo.dim_seller GROUP BY seller_segment ORDER BY seller_segment;
 SELECT COUNT(*) AS missing_mapping FROM dbo.dim_seller WHERE seller_segment IS NULL OR seller_region IS NULL');
COMMIT TRANSACTION;
END TRY
BEGIN CATCH
 IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
 THROW;
END CATCH;
""")
(OUT/'load_seller_segments.sql').write_text(''.join(parts),encoding='utf-8')

ns={'a':'http://schemas.microsoft.com/analysisservices/2003/engine','xs':'http://www.w3.org/2001/XMLSchema'}
folder=ROOT/'ssas/SSAS'
dimpath=folder/'Dim Seller.dim';text=dimpath.read_text(encoding='utf-8')
for title,col,size in [('Seller Segment','seller_segment',100),('Seller Region','seller_region',50)]:
    if f'<ID>{title}</ID>' not in text:
        attr=f'''    <Attribute>
      <ID>{title}</ID><Name>{title}</Name>
      <KeyColumns><KeyColumn><DataType>WChar</DataType><DataSize>{size}</DataSize>
        <Source xsi:type="ColumnBinding"><TableID>dbo_dim_seller</TableID><ColumnID>{col}</ColumnID></Source>
      </KeyColumn></KeyColumns>
      <OrderBy>Key</OrderBy>
    </Attribute>
'''
        text=text.replace('  </Attributes>',attr+'  </Attributes>')
        relation=f'<AttributeRelationship><AttributeID>{title}</AttributeID><Name>{title}</Name></AttributeRelationship>'
        text=text.replace('      </AttributeRelationships>',f'        {relation}\n      </AttributeRelationships>',1)
ET.fromstring(text);dimpath.write_text(text,encoding='utf-8')

dsvpath=folder/'Olist DW.dsv';text=dsvpath.read_text(encoding='utf-8')
match=re.search(r'(<xs:element name="dbo_dim_seller".*?<xs:sequence>)(.*?)(</xs:sequence>)',text,re.S)
if not match:raise ValueError('Seller DSV sequence not found')
body=match.group(2)
for col,size in [('seller_segment',100),('seller_region',50)]:
    if f'name="{col}"' not in body:
        body+=f'''                  <xs:element name="{col}" msprop:FriendlyName="{col}" msprop:DbColumnName="{col}" minOccurs="0">
                    <xs:simpleType><xs:restriction base="xs:string"><xs:maxLength value="{size}" /></xs:restriction></xs:simpleType>
                  </xs:element>
                '''
text=text[:match.start(2)]+body+text[match.end(2):]
ET.fromstring(text);dsvpath.write_text(text,encoding='utf-8')

cubepath=folder/'Olist DW.cube';text=cubepath.read_text(encoding='utf-8')
match=re.search(r'(<DimensionID>Dim Seller</DimensionID>\s*<Attributes>)(.*?)(</Attributes>)',text,re.S)
if not match:raise ValueError('Cube seller attributes not found')
body=match.group(2)
for title in ['Seller Segment','Seller Region']:
    if f'<AttributeID>{title}</AttributeID>' not in body:
        body+=f'        <Attribute><AttributeID>{title}</AttributeID></Attribute>\n      '
text=text[:match.start(2)]+body+text[match.end(2):]
ET.fromstring(text);cubepath.write_text(text,encoding='utf-8')

# Validate bindings across the three files, not just XML well-formedness.
dim=ET.parse(dimpath);dsv=ET.parse(dsvpath);cube=ET.parse(cubepath)
cols={e.attrib['name'] for e in dsv.findall('.//xs:element[@name="dbo_dim_seller"]/xs:complexType/xs:sequence/xs:element',ns)}
attrs={a.findtext('a:ID',namespaces=ns):a for a in dim.findall('./a:Attributes/a:Attribute',ns)}
cube_ids=[a.text for a in cube.findall('./a:Dimensions/a:Dimension[a:DimensionID="Dim Seller"]/a:Attributes/a:Attribute/a:AttributeID',ns)]
for title,col in [('Seller Segment','seller_segment'),('Seller Region','seller_region')]:
    assert col in cols and title in attrs and title in cube_ids
    assert attrs[title].findtext('.//a:ColumnID',namespaces=ns)==col
print(f'Generated mapping SQL for {len(data)} sellers; DSV/dimension/cube bindings validated')
