from demo.bootstrap import create_app
from demo.tasks import register_tasks


def main() -> None:
    with create_app() as app:
        register_tasks(app)
        app.run(interval=300)


if __name__ == "__main__":
    main()
