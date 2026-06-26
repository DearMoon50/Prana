import unittest
from prana.uhi_lookup import lookup_uhi_offset


class UHILookupTests(unittest.TestCase):
    def test_chennai_default(self):
        offset = lookup_uhi_offset("Chennai, Tamil Nadu, India")
        self.assertAlmostEqual(offset, 3.0)

    def test_chennai_district_match(self):
        offset = lookup_uhi_offset("T Nagar, Chennai, India")
        self.assertAlmostEqual(offset, 3.5)

    def test_dhaka_default(self):
        offset = lookup_uhi_offset("Dhaka")
        self.assertAlmostEqual(offset, 4.0)

    def test_dhaka_district(self):
        offset = lookup_uhi_offset("Old Dhaka, Bangladesh")
        self.assertAlmostEqual(offset, 4.5)

    def test_ho_chi_minh_default(self):
        offset = lookup_uhi_offset("Ho Chi Minh City, Vietnam")
        self.assertAlmostEqual(offset, 3.5)

    def test_ho_chi_minh_district(self):
        offset = lookup_uhi_offset("District 1, HCMC")
        self.assertAlmostEqual(offset, 4.0)

    def test_manila_district(self):
        offset = lookup_uhi_offset("Tondo, Manila, Philippines")
        self.assertAlmostEqual(offset, 4.0)

    def test_jakarta_district(self):
        offset = lookup_uhi_offset("Central Jakarta, Indonesia")
        self.assertAlmostEqual(offset, 4.5)

    def test_karachi_default(self):
        offset = lookup_uhi_offset("Karachi, Pakistan")
        self.assertAlmostEqual(offset, 3.0)

    def test_unknown_city_falls_back(self):
        offset = lookup_uhi_offset("Unknown City, Nowhere")
        self.assertAlmostEqual(offset, 3.0)

    def test_none_location_falls_back(self):
        offset = lookup_uhi_offset(None)
        self.assertAlmostEqual(offset, 3.0)

    def test_empty_location_falls_back(self):
        offset = lookup_uhi_offset("")
        self.assertAlmostEqual(offset, 3.0)


if __name__ == '__main__':
    unittest.main()
