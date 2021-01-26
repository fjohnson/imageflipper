import os
import threading
import time
import logging


class ImageCleaner(threading.Thread):

    def __init__(self, image_lock, image_set, max_file_age, image_clean_interval):
        super(self.__class__, self).__init__()
        self.daemon = True
        self.logger = logging.getLogger('main_logger')
        self.images_lock = image_lock
        self.image_set = image_set
        self.image_clean_interval = image_clean_interval
        self.max_file_age = max_file_age

    def run(self):

        while True:
            self.images_lock.acquire()
            images = set(self.image_set)
            self.images_lock.release()

            to_erase = set()

            for image in images:
                age_seconds = os.stat(image).st_mtime
                time_now = time.time()
                if time_now - age_seconds > self.max_file_age:
                    to_erase.add(image)

            for img in to_erase:
                self.images_lock.acquire()
                self.image_set.remove(img)
                self.images_lock.release()
                os.unlink(img)

            if to_erase:
                self.logger.info("Erased images :{}".format(to_erase))

            time.sleep(self.image_clean_interval)