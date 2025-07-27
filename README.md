## Setup Instructions
### Install dependencies
```
python -m venv .venv/
. .venv/bin/activate
pip install -r lambdas/requirements.txt

# if you plan to run the tests
pip install -r tests/requirements.txt
```

### Start postgres and ollama
```
docker compose up -d
```
:bulb: This downloads a 5GB model. I tried smaller ones and had a hard time getting meaningful responses, or they wouldn't follow instructions to craft the responses in json, or they were too slow for CPUs, so please use `docker compose logs ollama -f` to watch the logs and wait for the model to download.

### Build the SAM app
```bash
# need to export DOCKER_HOST because SAM can't reliably figure this out. https://github.com/aws/aws-sam-cli/issues/5646
export DOCKER_HOST="$(docker context inspect desktop-linux | jq -r '.[].Endpoints.docker.Host')"
sam build --use-container
```

### Start the app
```
sam local start-api
```

## Endpoints

- POST /datasets/{id}
- GET /alerts

### POST /datasets/{id} Endpoint

This endpoint accepts a CSV file upload, uses Ollama to determine if the student is stressed and saves it in postgres.
```
❯ curl -X POST -H "Content-Type: text/csv" --data-binary @university_mental_health_iot_dataset.csv http://127.0.0.1:3000/datasets/test$RANDOM | jq
{
  "user_id": "f689e3dd-ebce-418c-9ded-84c1b31337c5",
  "stress_analysis": {
    "stress_score": 55.0,
    "analysis": "Elevated stress levels are evident across multiple time points. Stress levels consistently exceed 40, indicating a significant stress burden. Sleep patterns are inconsistent, with some instances of insufficient sleep (less than 6 hours) and others showing adequate sleep.  Mood scores are generally low, with several instances reporting scores below 2.0, suggesting poor mood.  Mental health status is a recurring concern, with multiple entries explicitly mentioning mental health issues. The combination of elevated stress, poor mood, and mental health concerns points to a high level of stress and potential mental health challenges.  The inconsistency in sleep hours further exacerbates the stress, as sleep deprivation is a known stressor.  The data suggests a pattern of elevated stress coupled with negative emotional states and concerns about mental well-being.",
    "threshold_exceeded": true
  }
}
```

### GET /alerts Endpoint
This endpoint returns the list of students that have been flagged by the LLM as being stressed.

```
❯ curl  http://127.0.0.1:3000/alerts | jq
[
  {
    "record_id": "test424",
    "stress_score": 55.0,
    "timestamp": "2025-07-27T22:48:11Z"
  }
]
```

### Testing
```
pytest --doctest-modules -s
```
