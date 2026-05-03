import os

API_BASE_URL = "https://se-payment-verification-api.service.external.usea2.aws.prodigaltech.com/openapi"
MAX_VERIFICATION_ATTEMPTS = 3
MAX_PAYMENT_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = 30.0

# LLM Configuration
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_MODEL = "claude-sonnet-4-20250514"
LLM_MAX_TOKENS = 1024
LLM_RETRY_MAX_ATTEMPTS = 3
LLM_RETRY_BASE_DELAY = 1.0
LLM_TEMPERATURE = 0.0
