import unittest
from unittest.mock import MagicMock, patch
import requests
from prana.data_fetcher import DataFetcher

class TestBug2OpenAQLatestShape(unittest.TestCase):
    def setUp(self):
        self.fetcher = DataFetcher(api_key="fake", openaq_api_key="fake")
        # Ensure we have a session to mock
        if not hasattr(self.fetcher, '_session'):
            self.fetcher._session = MagicMock()

    def test_openaq_latest_shape_joining(self):
        # Bug 2: OpenAQ /latest endpoint returns a shape that lacks the 'parameter' object.
        # This test confirms that we correctly join the /latest results with /sensors metadata.
        
        # Mock the session on the instance
        mock_session = MagicMock()
        self.fetcher._session = mock_session
        
        # 1. Mock locations search
        mock_loc_search = MagicMock()
        mock_loc_search.status_code = 200
        mock_loc_search.json.return_value = {
            "results": [{"id": 1234, "name": "Test Station"}]
        }
        
        # 2. Mock /sensors call (the metadata)
        mock_sensors = MagicMock()
        mock_sensors.status_code = 200
        mock_sensors.json.return_value = {
            "results": [
                {"id": 1, "parameter": {"name": "pm25", "units": "ug/m3"}},
                {"id": 2, "parameter": {"name": "o3", "units": "ppm"}}
            ]
        }
        
        # 3. Mock /latest call (the values, matching real OpenAQ v3 spec)
        mock_latest = MagicMock()
        mock_latest.status_code = 200
        mock_latest.json.return_value = {
            "results": [
                {"sensorsId": 1, "value": 15.5, "datetime": {"utc": "2024-01-01T00:00:00Z"}},
                {"sensorsId": 2, "value": 0.05, "datetime": {"utc": "2024-01-01T00:00:00Z"}}
            ]
        }
        
        # Setup side_effect to return mocks in order
        mock_session.get.side_effect = [mock_loc_search, mock_sensors, mock_latest]
        
        pollutants = self.fetcher._get_openaq_air_quality(12.97, 77.59) # Bangalore coords
        
        # Verify join worked
        self.assertIsNotNone(pollutants)
        self.assertIn('pm25', pollutants)
        self.assertEqual(pollutants['pm25']['value'], 15.5)
        self.assertEqual(pollutants['pm25']['unit'], 'ug/m3')
        
    def test_openaq_latest_graceful_fallback(self):
        # Confirm we don't crash if a sensorsId is missing from the map
        mock_session = MagicMock()
        self.fetcher._session = mock_session
        
        mock_loc_search = MagicMock(status_code=200)
        mock_loc_search.json.return_value = {"results": [{"id": 1234}]}
        
        mock_sensors = MagicMock(status_code=200)
        mock_sensors.json.return_value = {"results": []} # Empty metadata
        
        mock_latest = MagicMock(status_code=200)
        mock_latest.json.return_value = {"results": [{"sensorsId": 999, "value": 10}]}
        
        mock_session.get.side_effect = [mock_loc_search, mock_sensors, mock_latest]
        
        pollutants = self.fetcher._get_openaq_air_quality(12.97, 77.59)
        
        # Should return None if no pollutants resolved, but NOT crash
        self.assertIsNone(pollutants)

if __name__ == "__main__":
    unittest.main()
