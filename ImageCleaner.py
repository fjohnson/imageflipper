import os
import threading
import time
import logging
from collections import namedtuple


class ImageCleaner(threading.Thread):

    def __init__(self, image_dir, image_lock, image_set, max_file_age, image_clean_interval, clean_event, clean_msg_event, clean_msg_buffer):
        super(self.__class__, self).__init__()
        self.daemon = True
        self.logger = logging.getLogger('main_logger')
        self.image_lock = image_lock
        self.image_set = image_set
        self.image_clean_interval = image_clean_interval
        self.max_file_age = max_file_age
        self.image_dir = image_dir
        self.clean_event = clean_event
        self.clean_msg_event = clean_msg_event
        self.clean_msg_buffer = clean_msg_buffer

    def clean_up(self):
        to_delete = set()
        report = set()
        DeletedItem = namedtuple('DeletedItem',['filename','age','space'])
        for term in os.listdir(self.image_dir):
            term_dir = os.path.join(self.image_dir, term)
            for image in os.listdir(term_dir):
                if image.endswith('.log'): # skip over log files
                    continue
                full_img_path = os.path.join(term_dir, image)
                file_age = time.time() - os.stat(full_img_path).st_mtime
                if file_age >= self.max_file_age:
                    to_delete.add(full_img_path)
                    report.add(DeletedItem(filename=os.path.join(term, image), age=file_age, space=os.stat(full_img_path).st_size))

        self.image_lock.acquire()
        for img in self.image_set & to_delete:
            self.image_set.remove(img)
        self.image_lock.release()

        for img in to_delete:
            os.unlink(img)

        if to_delete:
            msg = "Erased images :{}".format(to_delete)
            self.logger.info(msg)
            self.clean_msg_buffer.append(report)
            self.clean_msg_event.set()

    def run(self):
        while True:
            self.clean_event.wait(self.image_clean_interval)
            self.clean_event.clear()
            self.clean_up()

