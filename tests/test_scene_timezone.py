import unittest
from scene_sun import clean_site, solar_summary
from scene_timezone import resolve

class TimezoneTests(unittest.TestCase):
    def test_delhi_ignores_old_manual_offset(self):
        site=clean_site(dict(latitude=28.6,longitude=77.2,date='2026-09-30',time='09:00',utc_offset=-8))
        self.assertEqual(site['timezone'],'Asia/Kolkata')
        self.assertEqual(site['utc_offset'],5.5)
        self.assertTrue(solar_summary(site)['sunrise']['time'].startswith('06:'))

    def test_date_changes_daylight_saving(self):
        self.assertEqual(resolve(40.7128,-74.0060,'2026-01-15','12:00')['utc_offset'],-5)
        self.assertEqual(resolve(40.7128,-74.0060,'2026-07-15','12:00')['utc_offset'],-4)

    def test_fractional_zone(self):
        self.assertEqual(resolve(27.7172,85.3240,'2026-09-30','12:00')['utc_offset'],5.75)

    def test_skipped_and_repeated_clock_times(self):
        for date,time in [('2026-03-08','02:30'),('2026-11-01','01:30')]:
            with self.assertRaises(ValueError):resolve(40.7128,-74.0060,date,time)

    def test_empty_drawing_can_save_without_sun(self):
        self.assertFalse(clean_site({})['sun_enabled'])

if __name__=='__main__':unittest.main()
