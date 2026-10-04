import unittest
from review_state import transition

class ReviewStateTests(unittest.TestCase):
    def test_discard_keep_is_current_review_not_approval(self):
        a={'status':'rejected','review_note':'Discarded in revision comparison.'}
        transition(a,'kept')
        self.assertEqual(a['status'],'review')
        self.assertEqual(a['review_decision'],'kept')
        self.assertEqual(a['review_note'],'Kept for review — not approved.')
        self.assertEqual(a['review_history'][0]['note'],'Discarded in revision comparison.')
        transition(a,'rejected','Still needs changes')
        self.assertEqual(a['review_decision'],'rejected')
        transition(a,'approved')
        self.assertEqual(a['review_note'],'Approved.')
        self.assertEqual(len(a['review_history']),3)
    def test_unknown_decision_has_no_mutation(self):
        a={'status':'review'}
        with self.assertRaises(ValueError):transition(a,'unknown')
        self.assertEqual(a,{'status':'review'})
