"""Application settings loaded from environment variables via environs."""

import environs

env = environs.Env()
env.read_env()

DEBUG = env.bool("DEBUG", default=False)
TELEGRAM_BOT_TOKEN = env.str("TELEGRAM_BOT_TOKEN", default="")

SEAWEEDFS_FILER_URL = env.str("SEAWEEDFS_FILER_URL", default="http://localhost:8888")
SEAWEEDFS_PUBLIC_URL = env.str("SEAWEEDFS_PUBLIC_URL", default="")
MEILISEARCH_URL = env.str("MEILISEARCH_URL", default="http://localhost:7700")
MEILISEARCH_API_KEY = env.str("MEILISEARCH_API_KEY", default="")
