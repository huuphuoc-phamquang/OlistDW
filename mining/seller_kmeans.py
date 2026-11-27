"""Tzy step 4: reproducible K-Means selection, stability and cohort sensitivity."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import hashlib

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score, adjusted_rand_score
from threadpoolctl import threadpool_limits


def evaluate(matrix, ks=range(2,11)):
    x=matrix.to_numpy(dtype=float)
    if not np.isfinite(x).all() or not matrix.index.is_unique:
        raise ValueError('Invalid clustering matrix')
    rows=[];models={}
    with threadpool_limits(limits=2):
        for k in ks:
            model=KMeans(n_clusters=k,random_state=42,n_init=30,algorithm='lloyd').fit(x)
            sizes=np.bincount(model.labels_,minlength=k)
            rows.append({'k':k,'inertia':model.inertia_,
                         'silhouette':silhouette_score(x,model.labels_),
                         'davies_bouldin':davies_bouldin_score(x,model.labels_),
                         'calinski_harabasz':calinski_harabasz_score(x,model.labels_),
                         'min_cluster_size':int(sizes.min()),'max_cluster_size':int(sizes.max()),
                         'min_cluster_share':float(sizes.min()/len(x))})
            models[k]=model
    return pd.DataFrame(rows),models


def run_kmeans(inputs,output):
    inputs,output=Path(inputs),Path(output);output.mkdir(parents=True,exist_ok=True)
    matrix=pd.read_csv(inputs/'seller_model_input.csv').set_index('seller_id')
    all_matrix=pd.read_csv(inputs/'seller_model_input_all.csv').set_index('seller_id')
    features=pd.read_csv(inputs/'seller_features.csv').set_index('seller_id')
    metrics,models=evaluate(matrix)
    # A tiny outlier cluster can inflate silhouette without useful seller segments.
    viable=metrics.loc[metrics.min_cluster_share.ge(.02)]
    if viable.empty:
        raise ValueError('No k with minimum cluster size >= 2%; inspect candidates rather than silently accepting')
    k=int(viable.sort_values(['silhouette','k'],ascending=[False,True]).iloc[0].k)
    model=models[k];labels=pd.Series(model.labels_,index=matrix.index,name='kmeans_cluster')
    with threadpool_limits(limits=2):
        stability=[]
        for seed in [0,1,7,21,42,84,123,256,512,1024]:
            other=KMeans(n_clusters=k,random_state=seed,n_init=30).fit(matrix.to_numpy())
            stability.append({'seed':seed,'ari_to_seed42':adjusted_rand_score(labels,other.labels_),'inertia':other.inertia_})
        sensitivity_metrics,sensitivity_models=evaluate(all_matrix)
    all_k_model=sensitivity_models[k]
    all_labels=pd.Series(all_k_model.labels_,index=all_matrix.index)
    shared=matrix.index.intersection(all_matrix.index)
    sensitivity_ari=adjusted_rand_score(labels.loc[shared],all_labels.loc[shared])
    # Separate cohort is fit/scaled independently; comparison includes that policy change.
    assignments=features.join(labels)
    assignments['segment_status']=np.where(assignments.kmeans_cluster.notna(),'KMeans candidate',
                                         'Insufficient delivered orders')
    assignments['seller_segment']=assignments.kmeans_cluster.map(lambda x:f'KMeans C{int(x)}' if pd.notna(x) else 'Insufficient orders')
    numeric=features.select_dtypes('number').columns
    grouped=assignments.dropna(subset=['kmeans_cluster']).groupby('kmeans_cluster')
    medians=grouped[list(numeric)].median()
    means=grouped[list(numeric)].mean()
    summary=grouped.agg(sellers=('order_count','size'),total_sales=('total_sales','sum'),
                        orders_median=('order_count','median'),aov_median=('avg_order_value','median'),
                        review_mean=('review_score_mean','mean'),late_rate_mean=('late_delivery_rate','mean'),
                        distance_median=('avg_ship_distance_km','median'))
    summary['seller_share']=summary.sellers/len(matrix)
    summary['sales_share']=summary.total_sales/summary.total_sales.sum()
    with threadpool_limits(limits=2):
        pca=PCA(n_components=2,random_state=42).fit(matrix)
        coords=pd.DataFrame(pca.transform(matrix),columns=['PC1','PC2'],index=matrix.index)
    coords['kmeans_cluster']=labels
    for name,frame,index in [('kmeans_metrics',metrics,False),('kmeans_stability',pd.DataFrame(stability),False),
                             ('cohort_sensitivity_metrics',sensitivity_metrics,False),('seller_assignments',assignments,True),
                             ('cluster_summary',summary,True),('cluster_medians',medians,True),('cluster_means',means,True),
                             ('pca_coordinates',coords,True)]:
        frame.to_csv(output/f'{name}.csv',index=index,float_format='%.12g')
    # Dimension handoff also includes sellers without delivered sales.
    dim=assignments[['seller_segment','seller_region','segment_status']].reset_index()
    excluded=pd.read_csv(inputs/'excluded_sellers.csv')
    absent=excluded.loc[~excluded.seller_id.isin(dim.seller_id)].copy()
    from seller_features_extended import REGIONS
    absent['seller_region']=absent.seller_state.map(REGIONS).fillna('Unknown')
    absent['seller_segment']='No eligible delivered sales';absent['segment_status']='Outside cohort'
    dim=pd.concat([dim,absent[dim.columns]],ignore_index=True).sort_values('seller_id')
    assert dim.seller_id.is_unique
    dim.to_csv(output/'seller_segment_dimension.csv',index=False)
    details={'selected_k':k,'selection_rule':'Maximum full-cohort silhouette over k=2..10 with minimum cluster share >= 2%; inspect elbow alongside',
             'random_state':42,'n_init':30,'model_shape':list(matrix.shape),'feature_order':matrix.columns.tolist(),
             'matrix_sha256':hashlib.sha256((inputs/'seller_model_input.csv').read_bytes()).hexdigest(),
             'selected_metrics':metrics.loc[metrics.k.eq(k)].iloc[0].to_dict(),
             'stability_ari_min':float(pd.DataFrame(stability).ari_to_seed42.min()),
             'stability_ari_mean':float(pd.DataFrame(stability).ari_to_seed42.mean()),
             'all_seller_same_k_ari_on_shared_sellers':float(sensitivity_ari),
             'all_seller_best_silhouette_k':int(sensitivity_metrics.sort_values('silhouette',ascending=False).iloc[0].k),
             'pca_explained_variance_ratio':pca.explained_variance_ratio_.tolist(),
             'status':'KMeans candidate; final comparison with GMM and DBSCAN belongs to Phu0c',
             'limitations':['Historical descriptive clustering, not out-of-sample validation',
                            'Geography uses zip centroids, not actual shipping route',
                            'Review and delivery shared by all sellers of an order',
                            'Review answer timestamp records customer survey response, not seller response',
                            'Cancellation denominator covers only orders with seller-attributable items']}
    (output/'kmeans_selection.json').write_text(json.dumps(details,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    import joblib
    joblib.dump(model,output/'kmeans_model.joblib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
    for ax,y,title in [(axes[0],'inertia','Elbow'),(axes[1],'silhouette','Silhouette (all observations)')]:
        ax.plot(metrics.k,metrics[y],'o-');ax.axvline(k,color='firebrick',ls='--',label=f'Selected k={k}')
        ax.set(title=title,xlabel='k',ylabel=y);ax.set_xticks(metrics.k);ax.legend()
    fig.savefig(output/'elbow_silhouette.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,6),layout='constrained')
    for cluster in range(k):
        part=coords.loc[coords.kmeans_cluster.eq(cluster)]
        ax.scatter(part.PC1,part.PC2,s=13,alpha=.5,label=f'C{cluster} (n={len(part)})')
    ax.set(xlabel=f'PC1 ({pca.explained_variance_ratio_[0]:.1%})',ylabel=f'PC2 ({pca.explained_variance_ratio_[1]:.1%})',
           title='K-Means in PCA view (fit uses all selected features)');ax.legend()
    fig.savefig(output/'pca_kmeans.png',dpi=180);plt.close(fig)
    centers=pd.DataFrame(model.cluster_centers_,columns=matrix.columns)
    centers.to_csv(output/'cluster_centers_scaled.csv',index_label='kmeans_cluster')
    fig,ax=plt.subplots(figsize=(12,4),layout='constrained')
    im=ax.imshow(centers,aspect='auto',cmap='RdBu_r',vmin=-2,vmax=2)
    ax.set_xticks(range(len(matrix.columns)),matrix.columns,rotation=60,ha='right',fontsize=8)
    ax.set_yticks(range(k),[f'C{i}' for i in range(k)]);fig.colorbar(im,ax=ax,label='z-score; color limit +/-2',extend='both')
    fig.savefig(output/'cluster_centroids.png',dpi=180);plt.close(fig)
    return details,metrics,summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=Path('artifacts/seller_segmentation_v2'))
    parser.add_argument('--output',type=Path,default=Path('artifacts/seller_kmeans'))
    args=parser.parse_args()
    details,_,summary=run_kmeans(args.inputs,args.output)
    print(json.dumps(details,indent=2,ensure_ascii=False));print(summary)
