import json

from db_utils import get_db_connection, logger

# Initialize database connection at the module level
# This allows the connection to be reused across Lambda invocations
conn = None


def handler(event, context):
    """
    Handler for the /alerts endpoint that returns an array of stressed users.

    This function queries the database for users who have been identified as stressed
    and returns their information in a JSON response.

    Args:
        event: The event dict that contains the request parameters
        context: The context object that provides methods and properties about the invocation

    Returns:
        dict: A response containing the list of stressed users
    """
    global conn
    if conn is None:
      conn = get_db_connection()

    with conn.cursor() as cur:
        try:
            # Query the HighStressUsers table for stressed users
            # Join with users table to get the user name as record_id
            # Format the timestamp to ISO 8601 format
            query = """
                SELECT u.name AS record_id,
                       h.stress_score,
                       TO_CHAR(h.created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS timestamp
                FROM
                  HighStressUsers h
                  JOIN
                  users u
                ON h.user_id = u.id
                WHERE
                  h.is_stressed = TRUE
                ORDER BY
                  h.created_at DESC \
            """

            logger.debug(f"Executing query: {query}")
            cur.execute(query)

            # Fetch all records
            records = cur.fetchall()
            logger.info("Found stressed user records", extra={"count": len(records)})

            # Format the records as an array of objects
            result = []
            for record in records:
                result.append({
                    "record_id": record[0],
                    "stress_score": float(record[1]),
                    "timestamp": record[2]
                })

            # Return the response
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(result),
            }

        except Exception as e:
            logger.error("Error processing alerts", extra={"error": str(e)})
            return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
