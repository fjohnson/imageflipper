import os
import threading
import time

from display import IMAGES_LOCK, MAX_FILE_AGE, main_logger, IMAGE_CLEAN_INTERVAL, IMAGES


class ImageCleaner(threading.Thread):

    def __init__(self, daemon=True):
        super(self.__class__, self).__init__()
        self.daemon = True

    def run(self):

        while True:
            IMAGES_LOCK.acquire()
            images = set(IMAGES)
            IMAGES_LOCK.release()

            erased_images = set()

            for image in images:
                age_seconds = os.stat(image).st_mtime
                time_now = time.time()
                if time_now - age_seconds > MAX_FILE_AGE:
                    os.unlink(image)
                    erased_images.add(image)

            if erased_images:
                main_logger.info("Erased images :{}".format(erased_images))

            IMAGES_LOCK.acquire()
            for img in erased_images:
                IMAGES.remove(img)
            IMAGES_LOCK.release()

            time.sleep(IMAGE_CLEAN_INTERVAL)