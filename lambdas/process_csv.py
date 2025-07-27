import base64
import json
import logging
import os

from pydantic import ValidationError

from csv_utils import (
  parse_csv_to_models,
  StressAnalysisResult,
)
from db_utils import get_db_connection, logger
from llm_utils import (
  query_ollama
)

# Get environment variables for Ollama
OLLAMA_GENERATE_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL_NAME = os.environ.get("OLLAMA_MODEL", "llama3")

# Allow the connection to be reused across Lambda invocations
conn = None

log_level = os.environ.get('LOG_LEVEL', 'DEBUG').upper()
logger = logging.getLogger()
logger.setLevel(log_level)


def handler(event, _) -> dict:
    """
    Handler for processing CSV files uploaded to the /datasets/{id} endpoint.

    This function:
    1. Parses and validates the CSV data using Pydantic models
    2. Performs preliminary analysis on the mental health indicators
    3. Passes the analyzed data to Ollama for stress assessment
    4. Stores the results in the database if stress is detected

    The CSV data is expected to follow the structure defined in the MentalHealthRecord model.
    """
    global conn
    if conn is None:
      conn = get_db_connection()

    try:
        # Extract request parameters
        dataset_name = event.get("pathParameters", {}).get("id")
        logger.info(f"Processing request for dataset. name={dataset_name}")

        if not dataset_name:
            logger.error("Error: Missing dataset name in path")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing name in path"}),
            }

        # Insert the user record at the very beginning to avoid wasting time
        # on expensive operations if the user already exists
        logger.debug("Connecting to PostgreSQL database")
        with conn.cursor() as cur:
            logger.debug("Inserting record into users table")
            try:
                cur.execute(
                    "INSERT INTO users (id, name) VALUES (gen_random_uuid(), %s) RETURNING id",
                    (dataset_name,)
                )

                # Fetch the UUID from the database to ensure it was inserted correctly
                inserted_uuid = cur.fetchone()[0]
                logger.info("Successfully inserted user with UUID", extra={"uuid": inserted_uuid})

                # Note: We don't commit here so both insertions will be in the same transaction
            except Exception as e:
                # If a unique constraint violation occurs, rollback the transaction
                if conn:
                    conn.rollback()
                if "unique constraint" in str(e).lower():
                    logger.warning("Unique constraint violation", extra={"error": str(e)})
                    return {
                        "statusCode": 409,
                        "body": json.dumps(
                            {"error": f"A student with the ID '{dataset_name}' already exists. Please use a different student ID."})
                    }
                else:
                    # If any other error occurs, rollback the transaction
                    logger.error("Error during database operations", extra={"error": str(e)})
                    raise

        # Get the CSV file from the request body
        body = event.get("body", "")
        logger.debug(f"Request body size: {len(body)} characters")

        if not body:
            logger.error("Error: Missing CSV file in request body")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing CSV file in request body"}),
            }

        is_base64 = event.get("isBase64Encoded", False)
        if is_base64:
            logger.debug("Decoding base64 encoded body")
            body = base64.b64decode(body).decode('utf-8')

        try:
            logger.debug("Parsing CSV data into Pydantic models")
            mental_health_dataset = parse_csv_to_models(body)

            # Log basic information about the dataset
            record_count = len(mental_health_dataset.records)
            logger.debug(f"Successfully parsed {record_count} records from CSV")

            # Log a sample of the parsed data (first 2 records)
            if record_count > 0:
                logger.debug("Sample of parsed records:")
                for i, record in enumerate(mental_health_dataset.records[:2]):
                    logger.debug(f"Record {i + 1}: {record.dict()}")

        except ValidationError as e:
            logger.error(f"Validation error in CSV data: {str(e)}")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Invalid CSV data format: {str(e)}"}),
            }
        except Exception as e:
            logger.warning(f"Could not parse CSV structure: {str(e)}")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Could not parse CSV data: {str(e)}"}),
            }

        # Create a prompt for Ollama to analyze stress levels
        logger.debug("Creating prompt for Ollama")

        # Include our pre-analyzed stress indicators in the prompt
        prompt = f'''
                You are a mental health expert analyzing student stress levels.

                CRITICAL: You must respond with ONLY valid JSON in the exact format specified below. Do not include any other text, explanations, or formatting.

                Task: Analyze the following data to determine if there are signs of stress:
                {body}

                Analysis Guidelines:
                - Focus on stress_level, sleep_hours, mood_score, and mental_health_status indicators
                - stress_level > 40 indicates elevated stress
                - sleep_hours < 6 indicates insufficient sleep
                - mood_score < 2.0 indicates poor mood
                - mental_health_status concerns indicate mental health issues

                IMPORTANT: Write concisely. Avoid phrases like "After analyzing", "it is evident", "based on the data", "the analysis reveals". State facts directly.

                Return ONLY this JSON structure:
                {{
                    "stress_score": <number between 0 and 100, where 0 is no stress and 100 is extreme stress>,
                    "reason": "<Your assessment in 500 words or less, analyzing the key indicators: stress levels, sleep patterns, mood scores, and mental health status. Include specific data points and explain why they indicate stress or lack thereof.>"
                }}
            '''

        logger.info("Calling Ollama API for stress analysis")
        stress_analysis = query_ollama(prompt, url=OLLAMA_GENERATE_URL, model=OLLAMA_MODEL_NAME)

        try:
            # Parse the JSON response from Ollama and validate with Pydantic
            logger.debug("Parsing and validating Ollama response")
            analysis_data_raw = json.loads(stress_analysis)

            # Validate the response using our Pydantic model
            # This ensures the response contains the required fields (stress_score and reason)
            # and that they meet our validation rules (e.g., stress_score between 0-100)
            # If validation fails, a ValidationError will be raised and caught below
            logger.debug("Validating response structure with StressAnalysisResult model")
            analysis_data = StressAnalysisResult(**analysis_data_raw)

            # Extract the fields from the validated response
            # Since the response has been validated, we can safely access these fields
            stress_score = analysis_data.stress_score
            reason = analysis_data.reason

            # Determine if stressed based on threshold from environment variable
            stress_threshold = float(os.environ.get("STRESS_THRESHOLD", "50.0"))
            is_stressed = stress_score >= stress_threshold

            logger.info("Extracted data from Ollama response",
                        extra={"stress_score": stress_score, "threshold": stress_threshold, "is_stressed": is_stressed})

            with conn.cursor() as cur:
                if is_stressed:
                    logger.info("Stress score exceeds threshold, inserting into HighStressUsers table",
                                extra={"stress_score": stress_score, "threshold": stress_threshold})
                    cur.execute(
                        '''INSERT INTO HighStressUsers
                             (user_id, is_stressed, stress_score, analysis)
                           VALUES (%s, %s, %s, %s)''',
                        (inserted_uuid, is_stressed, stress_score, reason)
                    )
                else:
                    logger.info("Stress score below threshold, not inserting into HighStressUsers table",
                                extra={"stress_score": stress_score, "threshold": stress_threshold})

                # Now commit the entire transaction (both insertions)
                conn.commit()
                logger.info("Transaction committed successfully")

            # Return the LLM's overall stress score and reasoning
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "user_id": str(inserted_uuid),
                    "stress_analysis": {
                        "stress_score": stress_score,
                        "analysis": reason,
                        "threshold_exceeded": is_stressed
                    },
                }),
            }
        except ValidationError as e:
            logger.error("Validation error in Ollama response", extra={"error": str(e)})
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"Invalid response format from LLM: {str(e)}. SREs have been notified."}),
            }
        except json.JSONDecodeError as e:
            logger.error("Error parsing Ollama response", extra={"error": str(e)})
            logger.error("Raw Ollama response",
                        extra={"response": stress_analysis[:1000] + ("..." if len(stress_analysis) > 1000 else "")})
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"Invalid JSON response from LLM. SREs have been notified."}),
            }
        except Exception as e:
            logger.error("Error processing Ollama response", extra={"error": str(e)})
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"Error processing response: {str(e)}"}),
            }

    except Exception as e:
        logger.error(f"Error processing CSV error={str(e)})")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
