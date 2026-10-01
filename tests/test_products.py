import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from products import parse_listing,safe_link,measured,product_image

class ProductTests(unittest.TestCase):
    def test_real_price_currency_stock_and_dimensions(self):
        p={'@type':'Product','name':'Walnut chair','image':'/chair.jpg','offers':{'price':'12345','priceCurrency':'INR','availability':'https://schema.org/InStock'},'width':{'value':65,'unitText':'cm'}}
        r=parse_listing('<script type="application/ld+json">'+json.dumps({'@graph':[p]})+'</script>','https://shop.example/chair')
        self.assertEqual(r['price'],12345);self.assertEqual(r['currency'],'INR');self.assertEqual(r['availability'],'InStock');self.assertIn('65 cm',r['dimensions']);self.assertEqual(r['image'],'https://shop.example/chair.jpg')
    def test_missing_offer_never_claims_buyable_or_price(self):
        r=parse_listing('<script type="application/ld+json">{"@type":"Product","name":"Inspiration"}</script>','https://shop.example/look')
        self.assertFalse(r['verified_listing']);self.assertIsNone(r['price']);self.assertEqual(r['availability'],'Not supplied')
    def test_inspiration_not_a_product(self):
        with self.assertRaises(ValueError):parse_listing('<h1>Pretty lounge</h1>','https://example.com')
    def test_script_url_rejected(self):self.assertEqual(safe_link('javascript:alert(1)','https://example.com'),'')
    def test_gallery_and_explicit_dimensions_are_preserved(self):
        p={'@type':'Product','name':'Chair','image':['/one.jpg',{'url':'/two.jpg'},'/one.jpg'],'width':{'value':65,'unitCode':'CMT'},'depth':'28 inches','height':'0.9 m'}
        r=parse_listing('<script type="application/ld+json">'+json.dumps(p)+'</script>','https://shop.example/chair')
        self.assertEqual(len(r['images']),2);self.assertAlmostEqual(r['dimensions_m']['width']['metres'],.65);self.assertAlmostEqual(r['dimensions_m']['depth']['metres'],.7112)
        self.assertEqual(product_image(r,1),'https://shop.example/two.jpg')
        with self.assertRaises(ValueError):product_image(r,3)
    def test_ambiguous_dimensions_not_guessed(self):
        self.assertIsNone(measured('60 x 70 x 90'));self.assertIsNone(measured('60'));self.assertIsNone(measured('-2 cm'))
        p={'@type':'Product','name':'Variants','description':'Width: 65 cm. Large variant width: 85 cm. Depth: 70 cm.'}
        r=parse_listing('<script type="application/ld+json">'+json.dumps(p)+'</script>','https://shop.example/chair')
        self.assertNotIn('width',r['dimensions_m']);self.assertAlmostEqual(r['dimensions_m']['depth']['metres'],.7)
    def test_embedded_retailer_data_and_variant_discrepancy(self):
        slug='synthetic-sectional-121'
        record={'slug':slug,'name':'Example Sectional (121")','media':[{'type':'image','url':'https://cdn.example/sofa.jpg'},{'type':'video','url':'https://example/video'}],'sizes':{'sellable':True,'size_details':[{'dimension':{'length':285,'width':168,'height':77,'unit':'cm'}}]}}
        page='<script>window.APP_DATA = {"product_details":'+json.dumps(record)+',"unused":undefined}; doNotExecute();</script>'
        p=parse_listing(page,'https://shop.example/product/'+slug)
        self.assertEqual(len(p['images']),1);self.assertEqual(p['dimensions_m']['length']['metres'],2.85)
        self.assertTrue(any('discrepancy' in v for v in p['dimension_notes']))
        with self.assertRaises(ValueError):parse_listing(page,'https://shop.example/product/other-product')
