from rq import Worker

from app.workers.queue import get_redis_connection


def main() -> None:
    worker = Worker(["ingestion"], connection=get_redis_connection())
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
