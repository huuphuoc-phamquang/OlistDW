"""Leader proposal: audited seller features and shared clustering cohort (Tzy)."""
from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from seller_segmentation import load_sources, prepare_data, create_features, file_sha256

SEED = 42
CANDIDATES = [
    'order_count', 'avg_order_value', 'recency_days', 'tenure_days',
    'late_delivery_rate', 'delivery_days_mean', 'cancel_rate',
    'review_score_mean', 'low_star_rate', 'category_count', 'category_hhi',
    'price_index', 'avg_ship_distance_km', 'repeat_customer_rate', 'hot_score',
]
# Prefer interpretable representatives when |Pearson r| >= .75 after log/imputation.
PRIORITY = ['order_count', 'avg_order_value', 'recency_days', 'tenure_days',
            'late_delivery_rate', 'review_score_mean', 'category_count',
            'avg_ship_distance_km', 'repeat_customer_rate', 'cancel_rate',
            'price_index', 'hot_score', 'delivery_days_mean', 'category_hhi', 'low_star_rate']
LOG = ['order_count', 'avg_order_value', 'recency_days', 'tenure_days',
       'delivery_days_mean', 'category_count', 'price_index', 'avg_ship_distance_km']
REGIONS = {**dict.fromkeys(['SP','RJ','MG','ES'], 'Sudeste'),
           **dict.fromkeys(['PR','SC','RS'], 'Sul'),
           **dict.fromkeys(['BA','SE','AL','PE','PB','RN','CE','PI','MA'], 'Nordeste'),
           **dict.fromkeys(['AM','RR','AP','PA','TO','RO','AC'], 'Norte'),
           **dict.fromkeys(['MT','MS','GO','DF'], 'Centro-Oeste')}


def normalize_city(series):
    def norm(value):
        if pd.isna(value):
            return pd.NA
        return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', str(value).lower())
                               if not unicodedata.combining(c)).split())
    return series.map(norm).astype('string')


def load_extended(source):
    tables, manifest = load_sources(source)
    source = Path(source)
    extra = ['customers', 'geolocation', 'order_payments', 'leads_closed']
    if source.is_file():
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro', uri=True)) as con:
            names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for name in extra:
                if name not in names:
                    raise ValueError(f'Missing extended source table: {name}')
                tables[name] = pd.read_sql_query(f'SELECT * FROM "{name}"', con)
    else:
        for name in extra:
            paths = [source/f'{name}.csv', source/f'olist_{name}_dataset.csv']
            found = [p for p in paths if p.exists()]
            if len(found) != 1:
                raise ValueError(f'Expected one CSV for {name}: {found}')
            tables[name] = pd.read_csv(found[0])
            manifest[name] = {'name':found[0].name, 'sha256':file_sha256(found[0])}
    return tables, manifest


def validate_unique(frame, keys, name):
    if frame[keys].isna().any().any() or frame.duplicated(keys).any():
        raise ValueError(f'{name}: null or conflicting duplicate key {keys}')


def geo_lookup(geo):
    """One coordinate per zip, then equal-zip-weight city/state fallback."""
    g = geo.copy()
    g['zip'] = pd.to_numeric(g.geolocation_zip_code_prefix, errors='coerce')
    g['city'] = normalize_city(g.geolocation_city)
    g['state'] = g.geolocation_state.astype('string').str.strip().str.upper()
    g['lat'] = pd.to_numeric(g.geolocation_lat, errors='coerce')
    g['lng'] = pd.to_numeric(g.geolocation_lng, errors='coerce')
    # Brazil bounding box: do not average implausible international coordinates.
    valid = g.lat.between(-34, 6) & g.lng.between(-74, -34)
    bad = int((~valid).sum())
    g.loc[~valid, ['lat','lng']] = np.nan
    z = g.groupby('zip')[['lat','lng']].median()
    cities = g.groupby(['state','city','zip'])[['lat','lng']].median().groupby(['state','city']).median()
    states = g.groupby(['state','zip'])[['lat','lng']].median().groupby('state').median()
    return z, cities, states, bad


def resolve_locations(frame, prefix, lookup):
    z, cities, states, _ = lookup
    r = frame.copy()
    r['city'] = normalize_city(r[f'{prefix}_city'])
    r['state'] = r[f'{prefix}_state'].astype('string').str.strip().str.upper()
    r['zip'] = pd.to_numeric(r[f'{prefix}_zip_code_prefix'], errors='coerce')
    r = r.join(z, on='zip')
    r['coordinate_source'] = np.where(r.lat.notna() & r.lng.notna(), 'zip', 'missing')
    for level, keys, values in [('city',['state','city'],cities), ('state',['state'],states)]:
        fill = r[keys].join(values, on=keys)
        missing = r.lat.isna() | r.lng.isna()
        usable = missing & fill.lat.notna() & fill.lng.notna()
        r.loc[usable,['lat','lng']] = fill.loc[usable,['lat','lng']]
        r.loc[usable,'coordinate_source'] = level
    return r


def haversine(lat1, lng1, lat2, lng2):
    a,b,c,d = [np.radians(pd.to_numeric(x, errors='coerce').astype(float)) for x in [lat1,lng1,lat2,lng2]]
    x = np.sin((c-a)/2)**2 + np.cos(a)*np.cos(c)*np.sin((d-b)/2)**2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(x,0,1)))


def extend_features(tables, sales, profiles):
    """All order ratios use unique seller-order rows, never joined item counts."""
    t = {k:v.drop_duplicates().copy() for k,v in tables.items()}
    for name, keys in [('customers',['customer_id']),('order_payments',['order_id','payment_sequential']),
                       ('leads_closed',['mql_id'])]:
        validate_unique(t[name],keys,name)
    f = profiles.set_index('seller_id').copy()
    s = sales.copy()
    so = s.drop_duplicates(['seller_id','order_id']).copy()
    all_so = t['order_items'][['seller_id','order_id']].drop_duplicates().merge(
        t['orders'][['order_id','order_status']],on='order_id',validate='many_to_one')
    status = all_so.assign(cancel=lambda x:x.order_status.isin(['canceled','unavailable']),
                           undelivered=lambda x:x.order_status.isin(['shipped','invoiced','processing','approved']))
    f = f.join(status.groupby('seller_id').agg(all_order_count=('order_id','size'),
                                              cancel_rate=('cancel','mean'),undelivered_rate=('undelivered','mean')))
    f['items_per_order'] = f.item_count/f.order_count
    so['month'] = so.order_purchase_timestamp.dt.to_period('M').astype(str)
    f['active_months'] = so.groupby('seller_id').month.nunique()
    f['orders_per_active_month'] = f.order_count/f.active_months
    price = s.groupby('seller_id').price
    f['avg_item_price'] = price.mean()
    f['price_cv'] = price.std(ddof=0)/price.mean().replace(0,np.nan)
    product_rev = s.groupby(['seller_id','product_id']).price.sum()
    f['top_product_share'] = product_rev.groupby(level=0).max()/f.total_sales.replace(0,np.nan)
    for name, mask in [('weekend_sales_share',s.order_purchase_timestamp.dt.dayofweek.ge(5)),
                       ('q4_sales_share',s.order_purchase_timestamp.dt.quarter.eq(4))]:
        f[name] = s.assign(amount=s.price.where(mask,0)).groupby('seller_id').amount.sum()/f.total_sales.replace(0,np.nan)
    # Use twelve fully observed calendar months; exclude final partial August 2018.
    cutoff = s.order_purchase_timestamp.max().to_period('M').start_time
    prev_start, recent_start = cutoff-pd.DateOffset(months=12),cutoff-pd.DateOffset(months=6)
    prev=s.loc[s.order_purchase_timestamp.ge(prev_start)&s.order_purchase_timestamp.lt(recent_start)].groupby('seller_id').price.sum()
    recent=s.loc[s.order_purchase_timestamp.ge(recent_start)&s.order_purchase_timestamp.lt(cutoff)].groupby('seller_id').price.sum()
    f['sales_growth'] = recent.reindex(f.index,fill_value=0)/prev.reindex(f.index,fill_value=0).replace(0,np.nan)-1

    # Missing categories explicitly retained as unknown; weights always sum to one.
    s['category'] = s.product_category_name.astype('string').fillna('__unknown__')
    f['known_category_count'] = f.category_count
    f['category_count'] = s.groupby('seller_id').category.nunique()
    sc=s.groupby(['seller_id','category']).agg(revenue=('price','sum'),mean_price=('price','mean')).reset_index()
    cat=s.groupby('category').agg(revenue=('price','sum'),mean_price=('price','mean'),n_sellers=('seller_id','nunique'))
    sc=sc.join(cat,on='category',rsuffix='_cat').join(f[['total_sales']],on='seller_id')
    sc['weight']=sc.revenue/sc.total_sales.replace(0,np.nan)
    sc['hhi']=sc.weight**2
    sc['entropy']=np.where(sc.weight.gt(0),-sc.weight*np.log(sc.weight.clip(lower=1e-300)),0)
    sc.loc[sc.weight.isna(),'entropy']=np.nan
    sc['hot']=sc.weight*sc.revenue_cat/cat.revenue.sum()
    sc['market']=sc.weight*sc.revenue/sc.revenue_cat.replace(0,np.nan)
    sc['price_index']=sc.weight*sc.mean_price/sc.mean_price_cat.replace(0,np.nan)
    sc['competition']=sc.weight*sc.n_sellers
    sc['top10']=sc.weight*sc.category.isin(cat.revenue.nlargest(10).index)
    for target,col in [('category_hhi','hhi'),('category_entropy','entropy'),('hot_score','hot'),
                       ('market_share_in_cat','market'),('price_index','price_index'),
                       ('competition_exposure','competition'),('pct_rev_top10_cat','top10')]:
        f[target]=sc.groupby('seller_id')[col].sum(min_count=1)
    f['top_category_share']=sc.groupby('seller_id').weight.max()
    f['unknown_category_share']=sc.loc[sc.category.eq('__unknown__')].set_index('seller_id').weight.reindex(f.index,fill_value=0)
    # Same complete months in both years. With this source: January-July 2017/2018.
    latest_year=cutoff.year
    month_limit=cutoff.month-1
    if month_limit==0:
        latest_year-=1;month_limit=12
    cy=s.loc[s.order_purchase_timestamp.dt.month.le(month_limit)].assign(year=lambda x:x.order_purchase_timestamp.dt.year)
    base=cy.loc[cy.year.eq(latest_year-1)].groupby('category').price.sum()
    curr=cy.loc[cy.year.eq(latest_year)].groupby('category').price.sum()
    cat['growth']=curr.reindex(cat.index,fill_value=0)/base.reindex(cat.index,fill_value=0).replace(0,np.nan)-1
    sc['cat_growth']=sc.category.map(cat.growth)
    sc['growth_weight']=sc.weight.where(sc.cat_growth.notna(),0)
    sc['growth_contribution']=sc.weight*sc.cat_growth
    gw=sc.groupby('seller_id').growth_weight.sum()
    f['growth_exposure']=sc.groupby('seller_id').growth_contribution.sum(min_count=1)/gw.replace(0,np.nan)
    f['growth_exposure_coverage']=gw
    order_cat=s[['seller_id','order_id','category','review_score']].drop_duplicates()
    cat_review=order_cat.drop_duplicates(['order_id','category']).groupby('category').review_score.mean()
    seller_cat_review=order_cat.groupby(['seller_id','category']).review_score.mean()
    sc=sc.join(seller_cat_review.rename('seller_cat_review'),on=['seller_id','category'])
    sc['review_ratio']=sc.seller_cat_review/sc.category.map(cat_review)
    sc['review_w']=sc.weight.where(sc.review_ratio.notna(),0)
    sc['review_weighted']=sc.weight*sc.review_ratio
    f['review_index']=sc.groupby('seller_id').review_weighted.sum(min_count=1)/sc.groupby('seller_id').review_w.sum().replace(0,np.nan)

    days=(so.order_delivered_customer_date-so.order_purchase_timestamp).dt.total_seconds()/86400
    so['duration']=days.where(days.ge(0))
    promise=(so.order_estimated_delivery_date.dt.normalize()-so.order_purchase_timestamp.dt.normalize()).dt.days
    so['promised']=promise.where(promise.ge(0))
    delta=(so.order_delivered_customer_date.dt.normalize()-so.order_estimated_delivery_date.dt.normalize()).dt.days
    delta=delta.where(so.duration.notna()&so.promised.notna())
    so['late_days']=delta.where(delta.gt(0))
    so['early_days']=(-delta).where(delta.lt(0))
    for target,col,method in [('delivery_days_std','duration','std'),('promised_days_mean','promised','mean'),
                              ('days_late_mean','late_days','mean'),('days_early_mean','early_days','mean')]:
        f[target]=so.groupby('seller_id')[col].agg(method)
    f['freight_per_item']=f.total_freight/f.item_count
    f['review_score_std']=so.groupby('seller_id').review_score.std(ddof=0)
    # Mean of within-order review fractions; each seller-order gets one vote.
    reviews=t['order_reviews'].copy()
    score=pd.to_numeric(reviews.review_score,errors='coerce').where(lambda x:x.between(1,5))
    reviews['five']=score.eq(5).astype(float).where(score.notna())
    reviews['low']=score.le(2).astype(float).where(score.notna())
    reviews['comment']=reviews.review_comment_message.fillna('').str.strip().ne('').astype(float)
    delay=(pd.to_datetime(reviews.review_answer_timestamp,format='mixed',errors='coerce')-
           pd.to_datetime(reviews.review_creation_date,format='mixed',errors='coerce')).dt.total_seconds()/3600
    reviews['answer_hours']=delay.where(delay.ge(0))
    review_order=reviews.groupby('order_id')[['five','low','comment','answer_hours']].mean()
    so=so.join(review_order,on='order_id')
    for target,col in [('five_star_rate','five'),('low_star_rate','low'),('comment_rate','comment'),('review_answer_hours','answer_hours')]:
        f[target]=so.groupby('seller_id')[col].mean()

    # Customer and geographic joins are many-to-one, so item multiplicity cannot leak in.
    lookup=geo_lookup(t['geolocation'])
    seller_locs=resolve_locations(t['sellers'],'seller',lookup).set_index('seller_id')
    cust_locs=resolve_locations(t['customers'],'customer',lookup).set_index('customer_id')
    so=so.merge(t['orders'][['order_id','customer_id']],on='order_id',validate='many_to_one')
    if not so.customer_id.isin(cust_locs.index).all():
        raise ValueError('orders.customer_id: unmatched customers')
    so=so.join(cust_locs[['customer_unique_id','city','state','lat','lng','coordinate_source']],on='customer_id')
    so=so.join(seller_locs[['state','lat','lng','coordinate_source']],on='seller_id',rsuffix='_seller')
    so['distance']=haversine(so.lat_seller,so.lng_seller,so.lat,so.lng)
    so['interstate']=so.state.ne(so.state_seller).astype(float).where(so.state.notna()&so.state_seller.notna())
    so['state_city']=so.state.astype('string')+'|'+so.city.astype('string')
    f['avg_ship_distance_km']=so.groupby('seller_id').distance.mean()
    f['distance_coverage']=so.groupby('seller_id').distance.count()/f.order_count
    f['interstate_rate']=so.groupby('seller_id').interstate.mean()
    f['n_customer_states']=so.groupby('seller_id').state.nunique()
    f['n_customer_cities']=so.groupby('seller_id').state_city.nunique()
    customer_orders=so.groupby(['seller_id','customer_unique_id']).order_id.nunique()
    f['unique_customers']=customer_orders.groupby(level=0).size()
    f['repeat_customer_rate']=customer_orders.ge(2).groupby(level=0).mean()
    f['seller_city']=seller_locs.city
    f['seller_state']=seller_locs.state
    f['seller_region']=f.seller_state.map(REGIONS).fillna('Unknown')
    f['is_sp']=f.seller_state.eq('SP')
    f['seller_coordinate_source']=seller_locs.coordinate_source

    pay=t['order_payments'].copy()
    if not pay.order_id.isin(t['orders'].order_id).all():
        raise ValueError('order_payments: unmatched orders')
    pay['payment_installments']=pd.to_numeric(pay.payment_installments,errors='coerce').where(lambda x:x.ge(0))
    payment=pay.groupby('order_id').payment_installments.mean().to_frame('installments')
    for kind in ['credit_card','boleto','voucher']:
        payment[kind]=pay.assign(flag=pay.payment_type.eq(kind)).groupby('order_id').flag.max().astype(float)
    so=so.join(payment,on='order_id')
    for target,col in [('avg_installments','installments'),('credit_card_rate','credit_card'),('boleto_rate','boleto'),('voucher_rate','voucher')]:
        f[target]=so.groupby('seller_id')[col].mean()
    f['payment_coverage']=so.groupby('seller_id').installments.count()/f.order_count
    products=t['products'].copy()
    physical=['product_weight_g','product_length_cm','product_height_cm','product_width_cm','product_photos_qty','product_description_lenght']
    for col in physical:
        products[col]=pd.to_numeric(products[col],errors='coerce').where(lambda x:x.ge(0))
    products['volume']=products[physical[1:4]].prod(axis=1,min_count=3)
    item_extra=s[['seller_id','product_id']].merge(products,on='product_id',validate='many_to_one')
    for target,col in [('avg_weight_g','product_weight_g'),('avg_volume_cm3','volume'),('avg_photos','product_photos_qty'),('avg_description_len','product_description_lenght')]:
        f[target]=item_extra.groupby('seller_id')[col].mean()
    # Most recent won lead per seller, descriptive only; no imputation of funnel attributes.
    leads=t['leads_closed'].dropna(subset=['seller_id']).copy()
    leads['won_date']=pd.to_datetime(leads.won_date,errors='coerce',format='mixed')
    leads=leads.sort_values(['won_date','mql_id'],na_position='first').drop_duplicates('seller_id',keep='last').set_index('seller_id')
    for col in ['business_segment','business_type','lead_type','declared_monthly_revenue']:
        f[col]=leads[col]
    f['has_marketing_profile']=f.index.isin(leads.index)
    audit={
        'geo_invalid_rows':lookup[3], 'geo_unique_zip_count':len(lookup[0]),
        'seller_coordinate_sources':seller_locs.coordinate_source.value_counts().to_dict(),
        'customer_coordinate_sources':cust_locs.coordinate_source.value_counts().to_dict(),
        'seller_orders_missing_distance':int(so.distance.isna().sum()),
        'sellers_only_unknown_category':int(f.known_category_count.eq(0).sum()),
        'single_category_sellers':int(f.category_count.eq(1).sum()),
        'marketing_matched_eligible_sellers':int(f.has_marketing_profile.sum()),
        'growth_periods':{'sales_previous':[str(prev_start.date()),str(recent_start.date())],
                          'sales_recent':[str(recent_start.date()),str(cutoff.date())],
                          'category_years':[latest_year-1,latest_year],'category_months':[1,month_limit],
                          'end_bound_exclusive':True},
    }
    assert np.isclose(f.total_sales.sum(),s.price.sum())
    assert len(so)==int(f.order_count.sum())
    assert np.allclose(sc.loc[sc.total_sales.gt(0)].groupby('seller_id').weight.sum(),1)
    return f.reset_index(),audit,cat.reset_index()


def select_preprocess(profiles, selected=None):
    raw=profiles.set_index('seller_id')[CANDIDATES].astype(float).replace([np.inf,-np.inf],np.nan)
    if (raw<0).any().any():
        raise ValueError('Negative candidate feature')
    medians=raw.median()
    if medians.isna().any():
        raise ValueError('Entirely missing candidate feature')
    transformed=raw.fillna(medians)
    transformed[LOG]=np.log1p(transformed[LOG])
    corr=transformed.corr()
    decisions=[]
    if selected is None:
        selected=[]
        for name in PRIORITY:
            conflicts=[c for c in selected if abs(corr.loc[name,c])>=.75]
            if transformed[name].nunique()<2:
                decisions.append({'feature':name,'decision':'drop','reason':'constant'})
            elif conflicts:
                decisions.append({'feature':name,'decision':'drop','reason':'correlation >= 0.75','with':conflicts})
            else:
                selected.append(name);decisions.append({'feature':name,'decision':'keep'})
    scaler=StandardScaler()
    matrix=pd.DataFrame(scaler.fit_transform(transformed[selected]),index=raw.index,columns=selected)
    assert np.isfinite(matrix.to_numpy()).all()
    metadata={'feature_order':selected,'candidate_features':CANDIDATES,'log1p_features':[c for c in LOG if c in selected],
              'medians':medians[selected].to_dict(),'mean':dict(zip(selected,scaler.mean_)),
              'scale':dict(zip(selected,scaler.scale_)),'selection_decisions':decisions,
              'selection_rule':'Priority representatives; absolute Pearson >= 0.75 after imputation/log; no forced padding',
              'excluded_by_design':['freight_to_price_ratio','seller_state','seller_region','is_sp','marketing attributes'],
              'random_state':SEED,'outlier_policy':'retain; compare cohort sensitivity; no clipping',
              'missing_before_imputation':raw.isna().sum().to_dict()}
    return matrix,metadata,corr,transformed


def run_extended(source, output, min_orders=3):
    tables,manifest=load_extended(source)
    # Legacy validator receives its five base tables only.
    from seller_segmentation import REQUIRED
    sales,sellers,audit=prepare_data({k:tables[k] for k in REQUIRED})
    profiles,excluded,details=create_features(sales,sellers)
    profiles,extra,category=extend_features(tables,sales,profiles)
    profiles['model_eligible']=profiles.order_count.ge(min_orders)
    cohort=profiles.loc[profiles.model_eligible].copy()
    matrix,metadata,corr,transformed=select_preprocess(cohort)
    sensitivity,sensmeta,_,_=select_preprocess(profiles,selected=metadata['feature_order'])
    excluded=pd.concat([excluded,profiles.loc[~profiles.model_eligible,['seller_id','seller_city','seller_state']].assign(reason=f'Fewer than {min_orders} delivered orders')],ignore_index=True)
    audit.update(details);audit.update(extra)
    audit['source_rows'].update({name:len(tables[name]) for name in ['customers','geolocation','order_payments','leads_closed']})
    import platform,sklearn
    audit.update(source_manifest=manifest,minimum_delivered_orders=min_orders,model_shape=list(matrix.shape),
                 low_order_sellers=int((~profiles.model_eligible).sum()),
                 eligible_total_sales=float(profiles.total_sales.sum()),
                 main_cohort_total_sales=float(cohort.total_sales.sum()),
                 versions={'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__})
    audit['model_excluded_sellers']=len(excluded)
    audit['main_cohort_sales_coverage']=float(cohort.total_sales.sum()/profiles.total_sales.sum())
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    for name,frame,index in [('seller_features',profiles,False),('seller_model_input',matrix,True),
                              ('seller_model_input_all',sensitivity,True),('excluded_sellers',excluded,False),
                              ('candidate_correlations',corr,True),('category_statistics',category,False),
                              ('feature_summary',profiles.select_dtypes('number').describe().T,True)]:
        frame.to_csv(output/f'{name}.csv',index=index,float_format='%.12g')
    pairs=[{'feature_a':a,'feature_b':b,'pearson':corr.loc[a,b]} for i,a in enumerate(corr) for b in corr.columns[i+1:] if abs(corr.loc[a,b])>.5]
    pd.DataFrame(pairs).to_csv(output/'correlation_pairs.csv',index=False)
    for name,value in [('data_quality',audit),('preprocessing',metadata),('preprocessing_all',sensmeta)]:
        (output/f'{name}.json').write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    assert len(matrix)+len(excluded)==len(sellers)
    assert matrix.index.tolist()==cohort.seller_id.tolist()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(12,10),layout='constrained')
    im=ax.imshow(corr,vmin=-1,vmax=1,cmap='RdBu_r')
    ax.set_xticks(range(len(corr)),corr.columns,rotation=70,ha='right',fontsize=8)
    ax.set_yticks(range(len(corr)),corr.columns,fontsize=8)
    fig.colorbar(im,ax=ax);ax.set_title('Candidate correlations after imputation and log1p')
    fig.savefig(output/'candidate_correlations.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(4,4,figsize=(14,11),layout='constrained')
    for ax,col in zip(axes.flat,CANDIDATES):
        ax.hist(transformed[col],bins=35);ax.set_title(col,fontsize=9)
    axes.flat[-1].set_visible(False)
    fig.savefig(output/'feature_distributions.png',dpi=160);plt.close(fig)
    return profiles,matrix,audit,metadata


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--output',type=Path,default=Path('artifacts/seller_segmentation_v2'))
    parser.add_argument('--min-orders',type=int,default=3)
    args=parser.parse_args()
    if args.min_orders<1:parser.error('--min-orders must be positive')
    _,matrix,audit,meta=run_extended(args.source,args.output,args.min_orders)
    print(json.dumps({'shape':list(matrix.shape),'features':meta['feature_order'],'audit':audit},ensure_ascii=False,indent=2))
