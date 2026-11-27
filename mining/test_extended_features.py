"""Regression tests for proposal-specific denominator, category and geography rules."""
import unittest
import numpy as np
import pandas as pd
from test_seller_segmentation import fixture
from seller_segmentation import prepare_data,create_features,REQUIRED
from seller_features_extended import extend_features,geo_lookup,resolve_locations,haversine,normalize_city


def extended_fixture():
    t=fixture()
    t['sellers']['seller_zip_code_prefix']=[1,2,3]
    t['sellers']['seller_city']=['São Paulo','Rio','No geo']
    t['sellers']['seller_state']=['SP','RJ','ZZ']
    t['orders']['customer_id']=['c1','c2','c3']
    # Cancellation belongs to a seller that also has delivered sales.
    t['order_items'].loc[t['order_items'].order_id.eq('cancel'),'seller_id']='a'
    t['customers']=pd.DataFrame([['c1','u1',1,'sao paulo','SP'],['c2','u1',2,'RIO','RJ'],['c3','u2',3,'x','SP']],
                               columns=['customer_id','customer_unique_id','customer_zip_code_prefix','customer_city','customer_state'])
    t['geolocation']=pd.DataFrame([[1,-23.,-46.,'São Paulo','SP'],[1,-25.,-48.,'sao paulo','SP'],[2,-22.,-43.,'Rio','RJ']],
                                  columns=['geolocation_zip_code_prefix','geolocation_lat','geolocation_lng','geolocation_city','geolocation_state'])
    t['order_reviews']['review_comment_message']=['text',None,'ok']
    t['order_reviews']['review_creation_date']='2018-01-07'
    t['order_reviews']['review_answer_timestamp']='2018-01-08'
    t['order_payments']=pd.DataFrame([['one',1,'credit_card',2],['one',2,'voucher',1],['two',1,'boleto',1]],
                                     columns=['order_id','payment_sequential','payment_type','payment_installments'])
    t['leads_closed']=pd.DataFrame([['m1','a','2017-01-01','retail','reseller','online',0]],
                                   columns=['mql_id','seller_id','won_date','business_segment','business_type','lead_type','declared_monthly_revenue'])
    for c in ['product_weight_g','product_length_cm','product_height_cm','product_width_cm','product_photos_qty','product_description_lenght']:
        t['products'][c]=10
    return t


class ExtendedTests(unittest.TestCase):
    def calculate(self,t):
        sales,sellers,_=prepare_data({k:t[k] for k in REQUIRED})
        f,_,_=create_features(sales,sellers)
        return extend_features(t,sales,f)[0].set_index('seller_id')

    def test_order_grain_cancel_reviews_payments_and_repeat_customers(self):
        f=self.calculate(extended_fixture());a=f.loc['a']
        self.assertEqual(a.order_count,2)
        self.assertAlmostEqual(a.cancel_rate,1/3)
        self.assertEqual(a.total_sales,60)
        self.assertEqual(a.low_star_rate,.25) # mean(mean(1,0),0), not item weighted
        self.assertEqual(a.five_star_rate,.75)
        self.assertEqual(a.repeat_customer_rate,1)
        self.assertEqual(a.unique_customers,1)
        self.assertEqual(a.credit_card_rate,.5)
        self.assertEqual(a.voucher_rate,.5)
        self.assertEqual(a.boleto_rate,.5)
        self.assertEqual(a.avg_installments,1.25)
        self.assertEqual(a.interstate_rate,.5)
        self.assertEqual(a.category_hhi,.5)
        self.assertAlmostEqual(a.category_entropy,np.log(2))

    def test_unknown_category_retained_without_losing_sales(self):
        t=extended_fixture();t['products']['product_category_name']=None
        f=self.calculate(t)
        self.assertTrue(f.category_count.eq(1).all())
        self.assertTrue(f.known_category_count.eq(0).all())
        self.assertTrue(f.unknown_category_share.eq(1).all())
        self.assertTrue(f.category_hhi.eq(1).all())
        self.assertEqual(f.total_sales.sum(),65)

    def test_geo_median_fallback_and_no_fanout(self):
        t=extended_fixture();lookup=geo_lookup(t['geolocation'])
        self.assertEqual(lookup[0].loc[1,'lat'],-24)
        seller=t['sellers'].copy();seller.loc[0,'seller_zip_code_prefix']=999
        loc=resolve_locations(seller,'seller',lookup)
        self.assertEqual(len(loc),3)
        self.assertEqual(loc.loc[0,'coordinate_source'],'city')
        self.assertEqual(loc.loc[2,'coordinate_source'],'missing')
        self.assertEqual(normalize_city(pd.Series([' SÃO   PAULO '])).iloc[0],'sao paulo')
        self.assertEqual(float(haversine(pd.Series([0]),pd.Series([0]),pd.Series([0]),pd.Series([0])).iloc[0]),0)

    def test_duplicate_customer_key_rejected(self):
        t=extended_fixture();t['customers']=pd.concat([t['customers'],t['customers'].iloc[[0]].assign(customer_city='conflict')])
        with self.assertRaisesRegex(ValueError,'duplicate key'):
            self.calculate(t)

    def test_zero_revenue_seller_does_not_get_false_category_concentration(self):
        t=extended_fixture()
        t['order_items'].loc[t['order_items'].seller_id.eq('b'),'price']=0.
        f=self.calculate(t)
        self.assertEqual(f.loc['b','total_sales'],0)
        self.assertTrue(pd.isna(f.loc['b','category_hhi']))
        self.assertTrue(pd.isna(f.loc['b','category_entropy']))


if __name__=='__main__':unittest.main()
