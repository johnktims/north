import json
import os
import subprocess
import sys
import time
from unittest.mock import patch

import pytest

from lambdas.db_utils import get_db_connection

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambdas'))

# Import the Lambda handlers directly
from process_csv import handler as process_csv_handler
from alerts import handler as alerts_handler
import llm_utils


class TestIntegration:
    @classmethod
    def setup_class(cls):
        subprocess.run(["docker", "compose", "up", "-d", "postgres"], check=True)

        print("Waiting for services to start...")

        # Database connection details
        os.environ["PGHOST"] = "localhost"  # PostgreSQL host
        os.environ["PGUSER"] = "postgres"   # PostgreSQL user
        os.environ["PGPASSWORD"] = "example"  # PostgreSQL password
        os.environ["PGDATABASE"] = "users"  # PostgreSQL database name
        os.environ["PGPORT"] = "5432"       # PostgreSQL port

        # Wait for database to be ready
        max_retries = 30
        retry_interval = 1
        for i in range(max_retries):
          try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute('SELECT 1')
            cur.close()
            conn.close()
            print("Database is ready!")
            break
          except Exception as e:
            print(f"Waiting for database... ({i + 1}/{max_retries})")
            if i == max_retries - 1:
              raise Exception("Database connection timeout") from e
            time.sleep(retry_interval)

    # Ollama configuration
        # Note: We mock the Ollama API call, but these are still needed
        os.environ["OLLAMA_URL"] = "http://localhost:11434/api/generate"
        os.environ["OLLAMA_MODEL"] = "gemma3n:e2b"

        # Application settings
        os.environ["STRESS_THRESHOLD"] = "50.0"  # Threshold for determining stress
        os.environ["LOG_LEVEL"] = "DEBUG"        # Logging level

    def test_submit_csv_dataset(self):
        # Generate a unique dataset ID for this test to avoid conflicts
        dataset_id = f"test-dataset-{int(time.time())}"

        # Read the CSV file from the project root directory
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'university_mental_health_iot_dataset.csv')
        with open(csv_path, "rb") as f:
            csv_content = f.read()

        # Create the event object that simulates what API Gateway would send
        # This includes pathParameters, body, and isBase64Encoded flag
        event = {
            "pathParameters": {
                "id": dataset_id
            },
            "body": csv_content.decode('utf-8'),
            "isBase64Encoded": False
        }

        # Create a mock response for the Ollama API
        # This avoids the need for a running Ollama service
        mock_ollama_response = json.dumps({
            "stress_score": 75.5,
            "reason": "This is a mock stress analysis response for testing."
        })

        # Patch the query_ollama function in the process_csv module
        # This ensures our mock response is used instead of calling the actual API
        with patch('process_csv.query_ollama', return_value=mock_ollama_response):
            response = process_csv_handler(event, None)

            assert response["statusCode"] == 200, f"Expected status code 200, got {response['statusCode']} {response['body']}"

            # Check that the response is valid JSON
            try:
                data = json.loads(response["body"])
            except json.JSONDecodeError:
                pytest.fail("Response is not valid JSON")

            # Check the response structure
            assert "user_id" in data, "Missing 'user_id' field in response"
            assert "stress_analysis" in data, "Missing 'stress_analysis' field in response"

            stress_analysis = data["stress_analysis"]
            assert "stress_score" in stress_analysis, "Missing 'stress_score' field in stress_analysis"
            assert "analysis" in stress_analysis, "Missing 'analysis' field in stress_analysis"
            assert "threshold_exceeded" in stress_analysis, "Missing 'threshold_exceeded' field in stress_analysis"

            # Check data types
            assert isinstance(data["user_id"], str), f"Expected 'user_id' to be a string, got {type(data['user_id'])}"
            assert isinstance(stress_analysis["stress_score"], (int, float)), f"Expected 'stress_score' to be a number, got {type(stress_analysis['stress_score'])}"
            assert isinstance(stress_analysis["analysis"], str), f"Expected 'analysis' to be a string, got {type(stress_analysis['analysis'])}"
            assert isinstance(stress_analysis["threshold_exceeded"], bool), f"Expected 'threshold_exceeded' to be a boolean, got {type(stress_analysis['threshold_exceeded'])}"

            print(f"Response from process_csv_handler for dataset {dataset_id}: {data}")

    def test_alerts_endpoint(self):
        """
        Test the alerts Lambda function by directly invoking its handler.

        This test:
        1. Creates an empty event object (the alerts endpoint doesn't need any parameters)
        2. Calls the Lambda handler directly
        3. Verifies the response structure and data types

        Note: This test requires a PostgreSQL database to be running with the
        correct schema and some data in the HighStressUsers table. The database
        connection details are set in setup_class.

        The test_submit_csv_dataset test should be run first to populate the
        database with some data for this test to retrieve.
        """
        # Create an empty event object for the alerts handler
        # The alerts endpoint doesn't need any parameters
        event = {}

        # Call the Lambda handler directly
        response = alerts_handler(event, None)

        # Verify the response status code
        assert response["statusCode"] == 200, f"Expected status code 200, got {response['statusCode']}"

        # Check that the response is valid JSON
        try:
            data = json.loads(response["body"])
        except json.JSONDecodeError:
            pytest.fail("Response is not valid JSON")

        # Verify each item in the response has the expected structure
        for item in data:
            # Check required fields
            assert "record_id" in item, "Missing 'record_id' field"
            assert "stress_score" in item, "Missing 'stress_score' field"
            assert "timestamp" in item, "Missing 'timestamp' field"

            # Check data types
            assert isinstance(item["record_id"], str), f"Expected 'record_id' to be a string, got {type(item['record_id'])}"
            assert isinstance(item["stress_score"], (int, float)), f"Expected 'stress_score' to be a number, got {type(item['stress_score'])}"
            assert isinstance(item["timestamp"], str), f"Expected 'timestamp' to be a string, got {type(item['timestamp'])}"

        print(f"Response from alerts_handler: {data}")

    @classmethod
    def teardown_class(cls):
        print("Stopping Docker Compose services...")
        subprocess.run(["docker", "compose", "down"], check=True)
