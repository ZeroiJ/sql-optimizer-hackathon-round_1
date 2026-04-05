try:
    from openenv.core.env_server.http_server import create_app
except ImportError:
    from openenv.core.env_server.http_server import create_app

try:
    from ..models import SQLAction, SQLObservation
    from .sql_optimizer_environment import SQLOptimizerEnvironment
except ImportError:
    from models import SQLAction, SQLObservation
    from server.sql_optimizer_environment import SQLOptimizerEnvironment


app = create_app(
    SQLOptimizerEnvironment, SQLAction, SQLObservation, env_name="sql_optimizer_env"
)


def main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
