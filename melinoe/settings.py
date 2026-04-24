import environs

env = environs.Env()
env.read_env()

DEBUG = env.bool("DEBUG", default=False)
TELEGRAM_BOT_TOKEN = env.str("TELEGRAM_BOT_TOKEN", default="")
