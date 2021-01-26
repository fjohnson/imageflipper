import threading

from display import search_term_download, IMAGES, IMAGES_DOWNLOAD_INTERVAL, main_logger
from server import SearchTermServer


class ImageDownloader(threading.Thread):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.daemon = True
        self.display_images = False

    def run(self):

        while True:
            search_term_download()
            if IMAGES:
                self.display_images = True
            else:
                self.display_images = False
            SearchTermServer.new_term_event.wait(IMAGES_DOWNLOAD_INTERVAL)
            main_logger.info('image downloader woke up')