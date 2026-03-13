from __future__ import annotations

import logging
import time


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("scoring-core worker scaffold running in idle mode")
    try:
        while True:
            time.sleep(30)
    except KeyboardInterrupt:
        logging.info("scoring-core worker stopped")


if __name__ == "__main__":
    main()
